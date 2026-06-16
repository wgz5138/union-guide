#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 拆解【第 1 步】：先看「打開會發生什麼」。
這一步不抓資料，只回答最小的問題——
Playwright 打開 Google Flights，看到的是：
  (A) 搜尋結果？ (B) 同意/Cookie 視窗？ (C) 驗證碼？ (D) 空白/被擋？

跑法：
    pip install playwright
    playwright install chromium
    python gf_step1_open.py

跑完：看 data/gf_step1.png 這張截圖，以及畫面印出的標題/網址/偵測到的東西，
然後把【截圖 + 那幾行字】回報，我再給第 2 步。
"""

import os

from playwright.sync_api import sync_playwright

URL = ("https://www.google.com/travel/flights?"
       "q=Flights%20from%20KHH%20to%20NRT%20on%202026-09-15%20oneway"
       "&curr=TWD&hl=zh-TW&gl=TW")

SHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "data", "gf_step1.png")


def main():
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with sync_playwright() as p:
        # headless=False：開「看得到」的瀏覽器，這樣你能親眼看到 Google 給什麼
        browser = p.chromium.launch(headless=False)
        page = browser.new_context(locale="zh-TW").new_page()
        print("開啟中：", URL)
        page.goto(URL, timeout=60_000)
        page.wait_for_timeout(6000)        # 等 6 秒讓畫面長出來

        page.screenshot(path=SHOT, full_page=True)
        print("\n=== 結果 ===")
        print("頁面標題：", page.title())
        print("目前網址：", page.url)

        # 偵測常見狀況（看到哪個就印哪個）
        線索 = {
            "同意/Cookie 視窗": ["全部接受", "我同意", "Accept all",
                               "Before you continue", "接受全部"],
            "可能要驗證碼/被判機器人": ["reCAPTCHA", "unusual traffic",
                                  "我不是機器人", "異常流量"],
            "看起來有航班結果": ["小時", "直飛", "NT$", "轉機", "Nonstop"],
        }
        for 狀況, 關鍵字 in 線索.items():
            for k in 關鍵字:
                try:
                    if page.get_by_text(k, exact=False).count() > 0:
                        print(f"偵測到【{狀況}】：出現「{k}」")
                        break
                except Exception:
                    pass

        print(f"\n截圖已存：{SHOT}")
        input("看完截圖後，按 Enter 關閉瀏覽器…")
        browser.close()


if __name__ == "__main__":
    main()
