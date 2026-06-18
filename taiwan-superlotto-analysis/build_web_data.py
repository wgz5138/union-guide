#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產生網頁用的精簡資料檔 lottery-freq.json
==========================================

讀 data/superlotto638.json，輸出一個小檔到 repo 根目錄：lottery-freq.json，
內含第一區/第二區各號碼的出現次數、總期數、日期範圍。
lottery.html 載入時會抓這支檔，讓網頁上的冷熱底色與期數自動保持最新。

用法：python3 build_web_data.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
DATA_PATH = os.path.join(HERE, "data", "superlotto638.json")
OUT_PATH = os.path.join(REPO_ROOT, "lottery-freq.json")


def main():
    meta = json.load(open(DATA_PATH, encoding="utf-8"))
    draws = meta["draws"]
    f1 = {n: 0 for n in range(1, 39)}
    f2 = {n: 0 for n in range(1, 9)}
    for x in draws:
        for n in x["first_zone"]:
            f1[n] += 1
        f2[x["second_zone"]] += 1
    out = {
        "count": len(draws),
        "first_date": draws[0]["date"] if draws else None,
        "last_date": draws[-1]["date"] if draws else None,
        "last_period": draws[-1]["period"] if draws else None,
        "first_zone_freq": {str(k): v for k, v in f1.items()},
        "second_zone_freq": {str(k): v for k, v in f2.items()},
        "updated_at": meta.get("scraped_at"),
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"已輸出 {OUT_PATH}（{out['count']} 期，至 {out['last_date']}）")


if __name__ == "__main__":
    main()
