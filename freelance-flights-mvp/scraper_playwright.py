#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
動態網站版骨架（給 Google Flights 這種「資料靠 JavaScript 長出來」的網站）

什麼時候用這支？
  你用 scraper.py（requests）抓回來，發現 HTML 是空殼、看不到票價——
  代表資料是瀏覽器跑 JS 後才出現的。這時要用 Playwright 開一個「真的瀏覽器」
  去等畫面載入、（必要時）點擊、再讀資料。

安裝（比 requests 多一步，要下載瀏覽器核心）：
    pip install playwright
    playwright install chromium

這份一樣是骨架：穩定性結構（重試 / log / 等待）都搭好，
把 extract_flights() 換成真實選擇器即可。
"""

import logging
import random
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

log = logging.getLogger("flights")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

TARGET_URL = "https://example.com/REPLACE_ME"
MAX_RETRIES = 3
BACKOFF_BASE = 2
PAGE_TIMEOUT = 30_000  # 毫秒


def extract_flights(page, route):
    """從已載入的頁面讀資料。換成真實選擇器。

    動態網站的關鍵：先「等」目標元素出現，再讀，否則會讀到空的。
        page.wait_for_selector("REPLACE_ME", timeout=PAGE_TIMEOUT)
    """
    rows = []
    # page.wait_for_selector("REPLACE_ME", timeout=PAGE_TIMEOUT)
    # for card in page.query_selector_all("REPLACE_ME"):
    #     rows.append({
    #         "origin": route["origin"], "dest": route["dest"], "date": route["date"],
    #         "price": card.query_selector("REPLACE_ME").inner_text().strip(),
    #     })
    return rows


def scrape_route(route):
    """開瀏覽器抓一條航線，含重試。"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with sync_playwright() as p:
                # headless=True：背景跑、不開視窗（排程時用這個）
                # 除錯時改 headless=False 可以親眼看瀏覽器在做什麼
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                log.info("開瀏覽器抓取（第 %d/%d 次）：%s",
                         attempt, MAX_RETRIES, TARGET_URL)
                page.goto(TARGET_URL, timeout=PAGE_TIMEOUT)
                # TODO：這裡通常要選航線、日期、按搜尋鍵，例如：
                # page.fill("REPLACE_ME", route["origin"])
                # page.click("REPLACE_ME")
                rows = extract_flights(page, route)
                browser.close()
                return rows
        except PWTimeout as e:
            wait = BACKOFF_BASE ** attempt
            log.warning("逾時（第 %d 次）：%s → %d 秒後重試", attempt, e, wait)
            if attempt < MAX_RETRIES:
                time.sleep(wait)
    raise RuntimeError(f"重試 {MAX_RETRIES} 次仍失敗：{TARGET_URL}")


if __name__ == "__main__":
    routes = [{"origin": "TPE", "dest": "TYO", "date": "2026-08-01"}]
    for r in routes:
        data = scrape_route(r)
        log.info("抓到 %d 筆：%s", len(data), r)
        time.sleep(random.uniform(2, 5))
