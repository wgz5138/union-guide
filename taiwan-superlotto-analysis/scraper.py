#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
威力彩 (SuperLotto638) 官方開獎資料爬蟲
==========================================

資料來源：台灣彩券公司官方 API
    https://api.taiwanlottery.com/TLCAPIWeB/Lottery/SuperLotto638Result

做法：
    從威力彩首期所在月份 (2008-01) 開始，逐月向官方 API 索取該月所有開獎結果，
    解析後合併、去重、依期別排序，輸出成：
        data/superlotto638.json   （結構化、含原始抓取時間）
        data/superlotto638.csv    （試算表 / 分析用）

原則：
    * 100% 使用官方回傳的真實號碼，程式只負責「抓取 + 整理」，
      絕不自行產生、推測或填補任何開獎號碼。
    * 若某月抓取失敗，會明確記錄，不會用假資料補。

用法：
    python3 scraper.py                # 抓全部（2008-01 ~ 本月）
    python3 scraper.py --from 2024-01 # 指定起始月份
    python3 scraper.py --dump-raw 2024-01   # 只印出某月原始 JSON（用來核對欄位）
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time

import requests

API_URL = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/SuperLotto638Result"

# 威力彩首期：第 097000001 期，開獎日 2008-01-24
FIRST_MONTH = (2008, 1)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.taiwanlottery.com/",
    "Origin": "https://www.taiwanlottery.com",
}

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")


def month_range(start, end):
    """產生 (year, month) 序列，含頭尾。"""
    y, m = start
    ey, em = end
    while (y, m) <= (ey, em):
        yield (y, m)
        m += 1
        if m > 12:
            m = 1
            y += 1


def fetch_month(year, month, session, retries=4):
    """抓取某月所有威力彩開獎結果，回傳官方原始 JSON（dict）。"""
    params = {
        "period": "",
        "month": f"{year:04d}-{month:02d}",
        "pageNum": 1,
        "pageSize": 50,  # 一個月最多 ~10 期，50 綽綽有餘
    }
    last_err = None
    for attempt in range(retries):
        try:
            r = session.get(API_URL, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = 2 ** attempt
            print(f"  ! {year}-{month:02d} 第 {attempt+1} 次失敗：{e}，{wait}s 後重試",
                  file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"{year}-{month:02d} 連續 {retries} 次抓取失敗：{last_err}")


def _first_list(d):
    """從 dict 找出第一個 list 值（官方把開獎陣列放在 content 底下某個 key）。"""
    for v in d.values():
        if isinstance(v, list):
            return v
    return None


def parse_payload(payload):
    """把官方回傳解析成統一格式的開獎紀錄 list。

    每筆：{
        period: str,            # 期別，如 "113000050"
        date: "YYYY-MM-DD",     # 開獎日
        first_zone: [int x6],   # 第一區號碼，已排序 (1-38)
        first_zone_drawn: [int],# 第一區開出順序（若官方有提供）
        second_zone: int,       # 第二區號碼 (1-8)
    }
    解析時容錯：官方欄位名稱若調整，會嘗試多種可能 key。
    """
    content = payload.get("content")
    if not isinstance(content, dict):
        # 有些情況直接是 list 或在最上層
        content = payload if isinstance(payload, dict) else {}
    rows = None
    # 常見 key：superLotto638Res
    for key in ("superLotto638Res", "lotto638Res", "result", "data"):
        if isinstance(content.get(key), list):
            rows = content[key]
            break
    if rows is None:
        rows = _first_list(content) or []

    out = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        period = str(item.get("period") or item.get("Period") or "").strip()

        # 日期
        raw_date = (item.get("lotteryDate") or item.get("LotteryDate")
                    or item.get("openDate") or "")
        date = str(raw_date)[:10]  # 取 YYYY-MM-DD

        # 第一區（排序後）。官方常見：drawNumberAppear (排序), drawNumberSize (開出順序)
        sorted_nums = (item.get("drawNumberAppear") or item.get("DrawNumberAppear")
                       or item.get("openNumAppear") or [])
        drawn_nums = (item.get("drawNumberSize") or item.get("DrawNumberSize")
                      or item.get("openNumSize") or [])

        # 第二區
        second = (item.get("secondArea") or item.get("SecondArea")
                  or item.get("openNumSecondArea"))

        def to_ints(seq):
            res = []
            for x in seq:
                try:
                    res.append(int(x))
                except (TypeError, ValueError):
                    pass
            return res

        sorted_nums = to_ints(sorted_nums)
        drawn_nums = to_ints(drawn_nums)

        # 有些版本把第二區放在號碼陣列的最後一個
        first_zone = sorted_nums or sorted(drawn_nums[:6]) if drawn_nums else []
        if not first_zone and len(drawn_nums) >= 6:
            first_zone = sorted(drawn_nums[:6])

        try:
            second = int(second) if second is not None else None
        except (TypeError, ValueError):
            second = None

        # 若 second 仍缺，且 drawn_nums 有 7 個，取第 7 個當第二區
        if second is None and len(drawn_nums) == 7:
            second = drawn_nums[6]

        if not period or len(first_zone) != 6 or second is None:
            # 資料不完整就跳過（不亂補），但記錄下來
            print(f"  ? 略過不完整紀錄 period={period!r} first={first_zone} second={second}",
                  file=sys.stderr)
            continue

        out.append({
            "period": period,
            "date": date,
            "first_zone": sorted(first_zone),
            "first_zone_drawn": drawn_nums[:6] if len(drawn_nums) >= 6 else [],
            "second_zone": second,
        })
    return out


def scrape(start_month, end_month, delay=0.4):
    session = requests.Session()
    all_rows = {}
    failed = []
    for (y, m) in month_range(start_month, end_month):
        try:
            payload = fetch_month(y, m, session)
            rows = parse_payload(payload)
            for r in rows:
                all_rows[r["period"]] = r  # 以期別為 key 去重
            print(f"  {y}-{m:02d}: {len(rows)} 期 (累計 {len(all_rows)})")
        except Exception as e:  # noqa: BLE001
            print(f"  X {y}-{m:02d} 失敗：{e}", file=sys.stderr)
            failed.append(f"{y}-{m:02d}")
        time.sleep(delay)
    records = sorted(all_rows.values(), key=lambda r: r["period"])
    return records, failed


def save(records):
    os.makedirs(DATA_DIR, exist_ok=True)
    json_path = os.path.join(DATA_DIR, "superlotto638.json")
    csv_path = os.path.join(DATA_DIR, "superlotto638.csv")

    meta = {
        "source": "台灣彩券官方 API (api.taiwanlottery.com SuperLotto638Result)",
        "scraped_at": dt.datetime.now().astimezone().isoformat(),
        "count": len(records),
        "first_period": records[0]["period"] if records else None,
        "last_period": records[-1]["period"] if records else None,
        "draws": records,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["period", "date", "n1", "n2", "n3", "n4", "n5", "n6", "second_zone"])
        for r in records:
            w.writerow([r["period"], r["date"], *r["first_zone"], r["second_zone"]])

    print(f"\n已輸出：\n  {json_path}\n  {csv_path}\n共 {len(records)} 期")


def main():
    ap = argparse.ArgumentParser(description="威力彩官方開獎資料爬蟲")
    ap.add_argument("--from", dest="from_month", default=None,
                    help="起始月份 YYYY-MM（預設 2008-01）")
    ap.add_argument("--dump-raw", dest="dump_raw", default=None,
                    help="只抓某月並印出原始 JSON，用來核對官方欄位 (YYYY-MM)")
    args = ap.parse_args()

    if args.dump_raw:
        y, m = map(int, args.dump_raw.split("-"))
        payload = fetch_month(y, m, requests.Session())
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.from_month:
        y, m = map(int, args.from_month.split("-"))
        start = (y, m)
    else:
        start = FIRST_MONTH

    today = dt.date.today()
    end = (today.year, today.month)

    print(f"開始抓取威力彩官方開獎資料：{start[0]}-{start[1]:02d} ~ {end[0]}-{end[1]:02d}")
    records, failed = scrape(start, end)
    if not records:
        print("沒有抓到任何資料——可能是網路被擋或 API 變動。請檢查網路 egress 設定。",
              file=sys.stderr)
        sys.exit(1)
    save(records)
    if failed:
        print(f"\n⚠ 有 {len(failed)} 個月份抓取失敗（未用假資料補）：{', '.join(failed)}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
