#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""獨立補航班號工具（後處理）
=====================================================
不依賴爬蟲版本：直接讀 data/gflights.csv，把直飛班的 flight_no 補上後存回。
對照來源：①本檔內建對照（寫死，保證可用）②data/flight_no_map.csv（有就一起用）。

用法：在專案資料夾裡執行  python 補航班號.py
"""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(HERE, "data", "gflights.csv")
MAP_FILE = os.path.join(HERE, "data", "flight_no_map.csv")

# 內建對照（你親自從 Google 抓到的真資料；寫死，不怕對照表檔沒存對）
# key = (origin, dest, carrier_IATA, hhmm24)
BUILTIN = {
    ("KHH", "NRT", "BR", "07:00"): "BR108",
    ("KHH", "NRT", "IT", "08:15"): "IT280",
    ("KHH", "NRT", "UA", "09:55"): "UA838",
    ("KHH", "NRT", "CI", "12:55"): "CI126",
    ("KHH", "NRT", "GK", "14:00"): "GK18",
    ("KHH", "KIX", "IT", "06:55"): "IT284",
    ("KHH", "KIX", "AK", "08:30"): "AK170",
    ("KHH", "KIX", "MM", "14:10"): "MM32",
}

NAME_IATA = {
    "台灣虎航": "IT", "星宇航空": "JX", "長榮航空": "BR", "中華航空": "CI",
    "香港快運航空": "UO", "德威航空": "TW", "濟州航空": "7C", "真航空": "LJ",
    "釜山航空": "BX", "韓亞航空": "OZ", "大韓航空": "KE", "宿霧太平洋": "5J",
    "越捷航空": "VJ", "泰國獅子航空": "SL", "菲律賓航空": "PR", "樂桃航空": "MM",
    "捷星日本航空": "GK", "捷星": "GK", "酷航": "TR", "聯合航空": "UA",
    "全日空航空": "NH", "全日空": "NH", "日本航空": "JL", "國泰航空": "CX",
    "國泰": "CX", "亞洲航空": "AK", "達美": "DL",
}


def norm_time(s):
    """中文時段 → 24 小時 HH:MM。例：下午2:00→14:00、中午12:55→12:55、清晨7:00→07:00。"""
    s = s or ""
    m = re.search(r"(\d{1,2}):(\d{2})", s)
    if not m:
        return ""
    h, mi = int(m.group(1)), m.group(2)
    if ("下午" in s or "晚上" in s) and h != 12:
        h += 12
    elif "中午" in s:
        h = 12
    elif ("凌晨" in s or "上午" in s or "清晨" in s) and h == 12:
        h = 0
    return f"{h:02d}:{mi}"


def load_external_map(m):
    """有 data/flight_no_map.csv 就併進來（不蓋掉內建以外的也沒關係，後者較新）。"""
    if not os.path.exists(MAP_FILE):
        return 0
    n = 0
    try:
        with open(MAP_FILE, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    m[(r["origin"], r["dest"], r["carrier"], r["hhmm"])] = r["flight_no"]
                    n += 1
                except (KeyError, TypeError):
                    continue
    except OSError:
        pass
    return n


def main():
    if not os.path.exists(CSV_FILE):
        print(f"找不到 {CSV_FILE}　→　請先跑一次爬蟲產生 gflights.csv。")
        return

    m = dict(BUILTIN)
    ext = load_external_map(m)
    print(f"對照表：內建 {len(BUILTIN)} 筆"
          + (f"＋對照表檔 {ext} 筆（已合併，共 {len(m)} 筆）" if ext else "（未找到 flight_no_map.csv，只用內建）"))

    with open(CSV_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)
    if "flight_no" not in fields:
        fields = fields + ["flight_no"]

    filled = 0
    for r in rows:
        if r.get("flight_no"):                      # 已有就不動
            continue
        if str(r.get("transfers", "")).strip() not in ("0", ""):
            continue                                # 只補直飛
        carrier = NAME_IATA.get((r.get("airline") or "").strip(), "")
        hhmm = norm_time(r.get("depart_time", ""))
        fn = m.get((r.get("origin"), r.get("dest"), carrier, hhmm), "")
        if fn:
            r["flight_no"] = fn
            filled += 1

    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    total = len(rows)
    has = sum(1 for r in rows if r.get("flight_no"))
    print(f"完成：本次新補 {filled} 筆；全表 {total} 列中現有航班號 {has} 列。")
    print(f"已存回 → {CSV_FILE}")


if __name__ == "__main__":
    main()
