#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
讀取「台彩官方下載」的威力彩 CSV → 轉成分析用資料檔
=====================================================

當無法直接連官方 API（例如雲端沙箱被網路政策擋住）時，可改用此程式：
直接吃台灣彩券官網「各期開獎結果資料下載」匯出的 CSV（每年一檔），
解析後合併、去重、依期別排序，輸出與 scraper.py 相同格式的：
    data/superlotto638.json
    data/superlotto638.csv

官方 CSV 欄位：
    遊戲名稱,期別,開獎日期,銷售總額,銷售注數,總獎金,獎號1..獎號6,第二區

原則：只搬運官方真實號碼，不產生/推測任何號碼；欄位不全的列會跳過並記錄。
"""

import csv
import datetime as dt
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
SOURCE_DIR = os.path.join(DATA_DIR, "official_csv")


def parse_date(s):
    s = (s or "").strip().replace("-", "/")
    for fmt in ("%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s[:10]


def read_csv(path):
    rows = []
    # utf-8-sig 自動去掉 BOM
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # 欄名可能有前後空白，建立去空白對照
        for raw in reader:
            row = { (k or "").strip(): (v or "").strip()
                    for k, v in raw.items() if k is not None }
            if row.get("遊戲名稱") != "威力彩":
                continue
            period = row.get("期別", "").strip()
            date = parse_date(row.get("開獎日期", ""))
            try:
                first = [int(row[f"獎號{i}"]) for i in range(1, 7)]
            except (KeyError, ValueError):
                first = []
            try:
                second = int(row.get("第二區", "").strip())
            except (TypeError, ValueError):
                second = None

            if (not period or len(first) != 6
                    or any(not (1 <= n <= 38) for n in first)
                    or second is None or not (1 <= second <= 8)):
                print(f"  ? 跳過不完整列 period={period!r} first={first} second={second}"
                      f" ({os.path.basename(path)})", file=sys.stderr)
                continue
            rows.append({
                "period": period,
                "date": date,
                "first_zone": sorted(first),
                "first_zone_drawn": [],   # 官方下載僅提供大小順序，無開出順序
                "second_zone": second,
            })
    return rows


def main():
    files = sorted(glob.glob(os.path.join(SOURCE_DIR, "*.csv")))
    if not files:
        raise SystemExit(f"在 {SOURCE_DIR} 找不到任何 CSV。請把官方威力彩 CSV 放進去。")

    all_rows = {}
    per_file = []
    for path in files:
        rows = read_csv(path)
        per_file.append((os.path.basename(path), len(rows)))
        for r in rows:
            all_rows[r["period"]] = r   # 以期別去重（跨年也安全）

    # 注意：期別字串長度不一（2009-2010 為 8 碼 98/99，2011 起為 9 碼 100+），
    # 直接以字串排序會錯亂時間順序，故以「開獎日期」為主鍵排序。
    records = sorted(all_rows.values(), key=lambda r: (r["date"], r["period"]))
    if not records:
        raise SystemExit("沒有解析到任何威力彩開獎紀錄，請確認 CSV 內容。")

    meta = {
        "source": "台灣彩券官方「各期開獎結果資料下載」CSV（使用者提供）",
        "source_files": [os.path.basename(p) for p in files],
        "scraped_at": dt.datetime.now().astimezone().isoformat(),
        "count": len(records),
        "first_period": records[0]["period"],
        "last_period": records[-1]["period"],
        "first_date": records[0]["date"],
        "last_date": records[-1]["date"],
        "draws": records,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "superlotto638.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, "superlotto638.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["period", "date", "n1", "n2", "n3", "n4", "n5", "n6", "second_zone"])
        for r in records:
            w.writerow([r["period"], r["date"], *r["first_zone"], r["second_zone"]])

    print("各檔解析期數：")
    for name, c in per_file:
        print(f"  {name}: {c} 期")
    print(f"\n合併去重後共 {len(records)} 期"
          f"（{records[0]['period']} {records[0]['date']} ~ "
          f"{records[-1]['period']} {records[-1]['date']}）")
    print(f"已輸出 data/superlotto638.json 與 data/superlotto638.csv")


if __name__ == "__main__":
    main()
