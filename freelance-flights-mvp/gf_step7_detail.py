#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 拆解【第 7 步】：點進「詳情」看航班號 / 行李額度有沒有。
作法（拆解法）：先點開第一班的詳情 → 把展開的文字 dump 出來，
讓我們看清楚「航班號、行李」到底出不出現，再依真實內容寫解析（不盲猜）。

跑法：
    python gf_step7_detail.py
回報：把畫面印出的「展開後文字」整段貼給我，和 data/gf_step7.png 截圖。
"""

import os
import re

from playwright.sync_api import sync_playwright

URL = ("https://www.google.com/travel/flights?"
       "q=Flights%20from%20KHH%20to%20NRT%20on%202026-09-15%20oneway"
       "&curr=TWD&hl=zh-TW&gl=TW")
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "data", ".gf_profile")
SHOT = os.path.join(HERE, "data", "gf_step7.png")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
STEALTH_JS = """
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
Object.defineProperty(navigator,'languages',{get:()=>['zh-TW','zh','en']});
window.chrome = window.chrome || { runtime: {} };
"""
結果線索 = ["小時", "直達", "$"]
錯誤線索 = ["系統發生錯誤", "糟糕"]


def main():
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE, headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
            user_agent=UA, locale="zh-TW", timezone_id="Asia/Taipei",
            viewport={"width": 1366, "height": 850})
        ctx.add_init_script(STEALTH_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 載入（重試）
        for _ in range(8):
            page.goto(URL, timeout=60_000)
            page.wait_for_timeout(11000)
            body = page.inner_text("body")
            if any(k in body for k in 結果線索) and not any(e in body for e in 錯誤線索):
                break
        else:
            print("⚠ 沒載出結果，再跑一次試試。")

        # 找第一張航班卡並點開
        target = None
        for li in page.query_selector_all("li"):
            try:
                txt = li.inner_text()
            except Exception:
                continue
            if re.search(r"\$\s*[\d,]{3,}", txt) and "小時" in txt:
                target = li
                break

        if not target:
            print("⚠ 找不到航班卡。")
        else:
            print("找到第一張卡，嘗試點開詳情…")
            try:
                target.click(timeout=5000)
            except Exception as e:
                print("直接點失敗，試點卡內按鈕：", e)
                try:
                    target.query_selector("button").click(timeout=5000)
                except Exception as e2:
                    print("點按鈕也失敗：", e2)
            page.wait_for_timeout(4000)

        # dump 展開後的整頁文字（節錄），並偵測航班號/行李
        body = page.inner_text("body")
        print("\n=== 偵測 ===")
        航班號 = re.findall(r"\b[A-Z]{2}\s?\d{2,4}\b", body)
        print("可能的航班號（字母+數字）：", sorted(set(航班號))[:15])
        行李關鍵 = [w for w in ["行李", "手提", "託運", "隨身", "公斤", "kg",
                              "件", "免費", "需加購"] if w in body]
        print("出現的行李相關字：", 行李關鍵)

        print("\n=== 展開後頁面文字（節錄 1500 字，請整段貼給我）===")
        print(body[:1500])

        page.screenshot(path=SHOT, full_page=True)
        print("\n截圖：", SHOT)
        input("\n看完按 Enter 關閉…")
        ctx.close()


if __name__ == "__main__":
    main()
