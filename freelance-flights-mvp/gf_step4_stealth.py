#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 拆解【第 4 步】：對付反爬——隱藏「自動化特徵」(stealth)。
現象：程式開的瀏覽器會間歇被 Google 判定為機器人，丟「系統發生錯誤」。
假設：把自動化特徵藏起來、裝得更像真人，成功率會提高。

這支做的事：
  1) 啟動時移除自動化旗標（--enable-automation / AutomationControlled）
  2) 設真實 UA、時區、語系、視窗大小
  3) 注入 JS 把 navigator.webdriver 等破綻蓋掉
  4) 若還是錯，改用「整頁重新前往」(非按鈕) 重試，並等久一點

跑法：
    python gf_step4_stealth.py
回報：印出的判斷 + data/gf_step4.png
"""

import os

from playwright.sync_api import sync_playwright

URL = ("https://www.google.com/travel/flights?"
       "q=Flights%20from%20KHH%20to%20NRT%20on%202026-09-15%20oneway"
       "&curr=TWD&hl=zh-TW&gl=TW")
SHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "data", "gf_step4.png")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW','zh','en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = window.chrome || { runtime: {} };
"""

結果線索 = ["小時", "直飛", "NT$", "轉機", "Nonstop"]
錯誤線索 = ["系統發生錯誤", "糟糕", "Something went wrong"]


def main():
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-infobars", "--start-maximized"],
            ignore_default_args=["--enable-automation"],
        )
        ctx = browser.new_context(
            user_agent=UA, locale="zh-TW", timezone_id="Asia/Taipei",
            viewport={"width": 1366, "height": 850},
        )
        ctx.add_init_script(STEALTH_JS)        # 每頁載入前先注入偽裝
        page = ctx.new_page()

        ok = False
        for attempt in range(1, 5):
            print(f"\n第 {attempt} 次：前往頁面…")
            page.goto(URL, timeout=60_000)
            page.wait_for_timeout(9000)         # 等久一點讓結果跑出來
            body = page.inner_text("body")
            if any(k in body for k in 結果線索) and not any(e in body for e in 錯誤線索):
                print(f"✅ 第 {attempt} 次成功：看到航班結果！")
                ok = True
                break
            elif any(e in body for e in 錯誤線索):
                print(f"  仍是『系統發生錯誤』，重新前往再試…")
            else:
                print("  還在載入或畫面不明，再試…")
            page.wait_for_timeout(3000)

        page.screenshot(path=SHOT, full_page=True)
        print("\n=== 判斷 ===")
        print("成功看到結果？", "是 ✅" if ok else "否 ❌（stealth 仍不夠，需下一招）")
        print("截圖：", SHOT)
        print("\n頁面文字前 300 字：")
        print(page.inner_text("body")[:300])
        input("\n看完按 Enter 關閉…")
        browser.close()


if __name__ == "__main__":
    main()
