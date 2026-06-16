#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""穩定度壓力測試：連續跑 N 趟 gflights_scraper，統計『幾趟成功取得各航線清單』。
用來產出「成功率」實測數據（客主要的 9.5/10 就靠這個拿證據）。

用法（在本資料夾）：
    python 穩定度壓測.py            # 預設跑 10 趟、每趟間隔 10 分鐘
    python 穩定度壓測.py 5 120      # 跑 5 趟、每趟間隔 120 秒（快速煙霧測試）

說明：
  • 「成功」定義 = 該趟把 ROUTES 裡每一條航線都抓到 ≥1 班（行李逐班加值，不納入此判定）。
  • 間隔別設太短：連發太快比較像機器人、也較易踩到 Google 暫時錯誤。
  • 結果同時寫到 data/stability_test.csv，方便日後回看/貼給對方。
"""
import csv
import os
import sys
import time
from datetime import datetime

import gflights_scraper as gf

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
GAP_SEC = int(sys.argv[2]) if len(sys.argv) > 2 else 600

NEED = {(r["origin"], r["dest"], r["date"]) for r in gf.ROUTES}
OUT = os.path.join(gf.HERE, "data", "stability_test.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

succ = 0
print(f"=== 穩定度壓測：共 {N} 趟，間隔 {GAP_SEC} 秒，航線 {len(NEED)} 條 ===")
for i in range(1, N + 1):
    print(f"\n----- 第 {i}/{N} 趟 開始 -----")
    t0 = time.time()
    try:
        rows = gf.main() or []
    except Exception as e:                 # 整支崩潰也算這趟失敗，繼續下一趟
        print(f"  本趟拋例外：{e}")
        rows = []
    got = {(r["origin"], r["dest"], r["date"]) for r in rows}
    ok = bool(NEED) and NEED.issubset(got)
    succ += 1 if ok else 0
    secs = int(time.time() - t0)
    print(f"  → 本趟取得航線 {len(got & NEED)}/{len(NEED)}，共 {len(rows)} 班，"
          f"耗時 {secs}s → {'✅ 成功' if ok else '❌ 失敗'}")
    new = not os.path.exists(OUT)
    with open(OUT, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["時間", "趟次", "取得航線數", "需求航線數", "班數", "耗時秒", "成功"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    i, len(got & NEED), len(NEED), len(rows), secs, "Y" if ok else "N"])
    if i < N:
        print(f"  休息 {GAP_SEC} 秒…（要中止按 Ctrl+C）")
        try:
            time.sleep(GAP_SEC)
        except KeyboardInterrupt:
            print("  使用者中止。"); break

rate = succ / N * 100 if N else 0
print(f"\n=== 總結：{succ}/{N} 趟成功（{rate:.0f}%）；明細見 {OUT} ===")
