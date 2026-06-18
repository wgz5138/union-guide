#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
威力彩公平性（均勻性）檢定
============================

對 data/superlotto638.json 的全部開獎資料做卡方適配度檢定，
檢驗「搖球機是否公平、每個號碼出現機率是否均勻」。

- p > 0.05：無法拒絕『公平均勻』→ 與隨機無異，沒有號碼有優勢。
- p < 0.05：偵測到顯著偏差 → 某些號碼確實異常（值得進一步研究）。

這支程式的意義：讓任何人都能「自己重跑、自己驗證」，
不必相信任何人的口頭結論——相信程式碼與資料即可。

用法：python3 fairness_test.py
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "superlotto638.json")


def gammln(x):
    c = [76.18009172947146, -86.50532032941677, 24.01409824083091,
         -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5]
    y = x
    tmp = x + 5.5
    tmp -= (x + 0.5) * math.log(tmp)
    ser = 1.000000000190015
    for cj in c:
        y += 1
        ser += cj / y
    return -tmp + math.log(2.5066282746310005 * ser / x)


def gammq(a, x):
    """正規化上不完全 Gamma 函數 Q(a,x) = 1 - P(a,x)。"""
    if x < 0 or a <= 0:
        raise ValueError
    if x < a + 1:                          # 用級數展開算 P
        ap = a
        s = 1.0 / a
        dl = s
        for _ in range(1000):
            ap += 1
            dl *= x / ap
            s += dl
            if abs(dl) < abs(s) * 1e-12:
                break
        return 1.0 - s * math.exp(-x + a * math.log(x) - gammln(a))
    # 用連分數算 Q
    b = x + 1 - a
    c = 1e300
    dd = 1.0 / b
    h = dd
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        dd = an * dd + b
        if abs(dd) < 1e-300:
            dd = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        dd = 1.0 / dd
        de = dd * c
        h *= de
        if abs(de - 1) < 1e-12:
            break
    return math.exp(-x + a * math.log(x) - gammln(a)) * h


def chi_p(chi, df):
    return gammq(df / 2.0, chi / 2.0)


def main():
    if not os.path.exists(DATA_PATH):
        raise SystemExit(f"找不到 {DATA_PATH}，請先產生資料。")
    draws = json.load(open(DATA_PATH, encoding="utf-8"))["draws"]
    N = len(draws)
    o1 = [0] * 39
    o2 = [0] * 9
    for x in draws:
        for n in x["first_zone"]:
            o1[n] += 1
        o2[x["second_zone"]] += 1
    e1 = N * 6 / 38
    e2 = N / 8
    chi1 = sum((o1[n] - e1) ** 2 / e1 for n in range(1, 39))
    chi2 = sum((o2[n] - e2) ** 2 / e2 for n in range(1, 9))
    p1 = chi_p(chi1, 37)
    p2 = chi_p(chi2, 7)

    print(f"威力彩公平性（均勻性）卡方檢定　樣本 {N} 期")
    print("-" * 56)
    print(f"第一區 1~38：最常 {max(o1[1:])} 次、最少 {min(o1[1:39])} 次、期望 {e1:.1f}")
    print(f"  卡方 = {chi1:.2f}　df=37　臨界值(0.05)=52.19　p = {p1:.3f}")
    print(f"  → {'⚠ 偵測到顯著偏差' if p1 < 0.05 else '與公平隨機無異（無法拒絕均勻）'}")
    print(f"第二區 1~8 ：最常 {max(o2[1:])} 次、最少 {min(o2[1:9])} 次、期望 {e2:.1f}")
    print(f"  卡方 = {chi2:.2f}　df=7 　臨界值(0.05)=14.07　p = {p2:.3f}")
    print(f"  → {'⚠ 偵測到顯著偏差' if p2 < 0.05 else '與公平隨機無異（無法拒絕均勻）'}")
    print("-" * 56)
    print("p>0.05：沒有號碼有統計優勢；p<0.05：某些號碼異常，值得深究。")


if __name__ == "__main__":
    main()
