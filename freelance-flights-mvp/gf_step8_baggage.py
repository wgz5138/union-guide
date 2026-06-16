#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 拆解【第 8 步】：抓「行李額度」+ 驗證能否逐班抓。
第 7 步發現：詳情頁有行李說明（手提/託運），但沒有航班號。
這一步：點開前幾班 → 抓行李 → 返回列表 → 再點下一班，驗證迴圈可行。

跑法：
    python gf_step8_baggage.py
回報：印出的「每班行李」與「返回列表是否成功」。
"""

import os
import re

from playwright.sync_api import sync_playwright

URL = ("https://www.google.com/travel/flights?"
       "q=Flights%20from%20KHH%20to%20NRT%20on%202026-09-15%20oneway"
       "&curr=TWD&hl=zh-TW&gl=TW")
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "data", ".gf_profile")
SHOT = os.path.join(HERE, "data", "gf_step8.png")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
STEALTH_JS = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
結果線索 = ["小時", "直達", "$"]
錯誤線索 = ["系統發生錯誤", "糟糕"]


def parse_baggage(text):
    """從詳情文字抓行李說明（手提/託運那幾行）。"""
    found = []
    for line in text.split("\n"):
        s = line.strip()
        if ("手提行李" in s or "託運行李" in s) and 2 < len(s) < 40:
            found.append(s)
    # 去重保留順序
    return " / ".join(dict.fromkeys(found))


def 找卡(page):
    cards = []
    for li in page.query_selector_all("li"):
        try:
            t = li.inner_text()
        except Exception:
            continue
        if (re.search(r"\$\s*[\d,]{3,}", t) and "小時" in t
                and re.search(r"\d{1,2}:\d{2}", t)):
            cards.append(li)
    return cards


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

        loaded = False
        for i in range(1, 9):
            page.goto(URL, timeout=60_000)
            page.wait_for_timeout(11000)
            body = page.inner_text("body")
            if any(k in body for k in 結果線索) and not any(e in body for e in 錯誤線索):
                loaded = True
                print(f"第 {i} 次：結果已載出")
                break
            print(f"第 {i} 次：未載出，重試…")
        if not loaded:
            print("⚠ 沒載出，請再跑一次。")
            ctx.close(); return

        n = len(找卡(page))
        print(f"列表有 {n} 班，試前 3 班抓行李：")
        for idx in range(min(3, n)):
            cards = 找卡(page)              # 每次重新抓（返回後元素會失效）
            if idx >= len(cards):
                break
            try:
                cards[idx].click(timeout=5000)
                page.wait_for_timeout(3500)
                detail = page.inner_text("body")
                bag = parse_baggage(detail)
                print(f"  第 {idx+1} 班行李：{bag or '（沒抓到，可能版面不同）'}")
                page.go_back()              # 返回列表
                page.wait_for_timeout(3000)
                back_ok = len(找卡(page)) > 0
                print(f"    返回列表：{'成功' if back_ok else '失敗（go_back 無效）'}")
                if not back_ok:
                    print("    → 改用『重新前往列表頁』策略")
                    page.goto(URL, timeout=60_000); page.wait_for_timeout(9000)
            except Exception as e:
                print(f"  第 {idx+1} 班出錯：{e}")

        page.screenshot(path=SHOT, full_page=True)
        print("截圖：", SHOT)
        input("\n看完按 Enter 關閉…")
        ctx.close()


if __name__ == "__main__":
    main()
