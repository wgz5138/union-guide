#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 拆解【第 2 步】：突破「糟糕！系統發生錯誤」。
第 1 步已確認：頁面打得開、搜尋條件正確、沒驗證碼，但結果區報錯。
這一步要解的小問題：自動偵測錯誤 → 按「重新載入」→ 等真正的航班結果出現。

跑法：
    python gf_step2_results.py

跑完看 data/gf_step2.png，以及畫面印出的判斷，回報給我。
"""

import os

from playwright.sync_api import sync_playwright

URL = ("https://www.google.com/travel/flights?"
       "q=Flights%20from%20KHH%20to%20NRT%20on%202026-09-15%20oneway"
       "&curr=TWD&hl=zh-TW&gl=TW")

SHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "data", "gf_step2.png")

# 結果出現的線索（航班才會有的字）
結果線索 = ["小時", "直飛", "NT$", "轉機", "Nonstop"]
錯誤線索 = ["系統發生錯誤", "糟糕", "Something went wrong"]


def 有結果(body):
    return any(k in body for k in 結果線索) and not any(e in body for e in 錯誤線索)


def main():
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_context(locale="zh-TW").new_page()
        print("開啟中…")
        page.goto(URL, timeout=60_000)
        page.wait_for_timeout(5000)

        for attempt in range(1, 6):          # 最多試 5 次
            body = page.inner_text("body")
            if 有結果(body):
                print(f"✅ 第 {attempt} 次：偵測到航班結果！")
                break
            if any(e in body for e in 錯誤線索):
                print(f"第 {attempt} 次：偵測到『系統發生錯誤』→ 按『重新載入』再等…")
                try:
                    page.get_by_text("重新載入", exact=False).first.click(timeout=5000)
                except Exception:
                    page.reload(timeout=60_000)   # 按不到就整頁重載
            else:
                print(f"第 {attempt} 次：還在載入，再等等…")
            page.wait_for_timeout(7000)
        else:
            print("⚠ 試了 5 次仍沒看到結果（可能要換策略，回報截圖給我）。")

        page.screenshot(path=SHOT, full_page=True)
        print(f"\n截圖已存：{SHOT}")
        # 印出前幾百字，方便判斷頁面到底有什麼
        print("\n=== 頁面文字前 400 字 ===")
        print(page.inner_text("body")[:400])
        input("\n看完截圖後，按 Enter 關閉…")
        browser.close()


if __name__ == "__main__":
    main()
