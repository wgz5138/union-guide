#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 機票數據抓取（A2310 案 用 Playwright 開真瀏覽器爬）

⚠️ 重要前提（接案前務必知道）：
  1. Google Flights 整頁靠 JavaScript 渲染、class 名是亂碼且會變、且有反爬。
     → 本檔把「流程與穩定性結構」搭好，但【解析選擇器需對著實際頁面微調】。
        程式以「讀整段文字 + 正規表達式」為主，比抓亂碼 class 穩，但仍可能要調。
  2. 「行李額度」通常不在搜尋結果列表上，要點進票價詳情才看得到 →
     先標為 TODO（見 parse_card），列表能穩定拿到：票價、轉機次數、時間、航空。
  3. Google 服務條款（ToS）禁止自動抓取 → 正式接案請先告知客戶法律/封鎖風險，
     並評估改用官方/付費 API 或單一航空官網（較好爬）的可行性。

安裝：
    pip install playwright
    playwright install chromium

執行：
    python gflights_scraper.py
（除錯時把 HEADLESS 改 False，可親眼看瀏覽器在做什麼，方便調選擇器。）
"""

import csv
import json
import logging
import os
import random
import re
import time
import urllib.parse
from datetime import datetime
from logging.handlers import RotatingFileHandler

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─────────────────────────────────────────────────────────────
# 設定區
# ─────────────────────────────────────────────────────────────
# 要抓的航線（出發/抵達用 IATA 代碼；日期 YYYY-MM-DD）
ROUTES = [
    {"origin": "KHH", "dest": "NRT", "date": "2026-09-15"},  # 高雄→東京成田
    {"origin": "KHH", "dest": "KIX", "date": "2026-09-15"},  # 高雄→大阪關西
]

HEADLESS = True            # 除錯改 False 可看瀏覽器
PAGE_TIMEOUT = 45_000      # 毫秒
MAX_RETRIES = 3
BACKOFF_BASE = 2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "gflights.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "data", "gflights.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "gflights.log")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


# ─────────────────────────────────────────────────────────────
# log
# ─────────────────────────────────────────────────────────────
def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logger = logging.getLogger("gflights")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    con = logging.StreamHandler(); con.setFormatter(fmt); logger.addHandler(con)
    fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3,
                             encoding="utf-8")
    fh.setFormatter(fmt); logger.addHandler(fh)
    return logger


log = setup_logging()


# ─────────────────────────────────────────────────────────────
# 組 Google Flights 搜尋網址（用自然語言 q=，比手動填表單穩）
# ─────────────────────────────────────────────────────────────
def build_url(route):
    q = f"Flights from {route['origin']} to {route['dest']} on {route['date']} oneway"
    params = {"q": q, "curr": "TWD", "hl": "zh-TW", "gl": "TW"}
    return "https://www.google.com/travel/flights?" + urllib.parse.urlencode(params)


# ─────────────────────────────────────────────────────────────
# 解析一張結果卡：以「整段文字 + 正則」為主（比亂碼 class 穩）
# ─────────────────────────────────────────────────────────────
def parse_card(text, route):
    """text = 一個結果項目的 inner_text。回傳一筆資料 dict 或 None。"""
    # 票價：抓 NT$ 或 純數字（千分位逗號）
    m_price = re.search(r"(?:NT\$|＄|\$)?\s*([\d,]{3,})", text)
    price = int(m_price.group(1).replace(",", "")) if m_price else None
    if price is None:
        return None

    # 轉機次數：「直飛 / Nonstop」=0；「1 次轉機 / 1 stop」等
    if re.search(r"直飛|非直達.*0|[Nn]onstop", text):
        transfers = 0
    else:
        m_stop = re.search(r"(\d+)\s*(?:次轉機|stop)", text)
        transfers = int(m_stop.group(1)) if m_stop else None

    # 出發/抵達時間（HH:MM）：抓前兩個
    times = re.findall(r"\d{1,2}:\d{2}", text)
    depart_time = times[0] if len(times) >= 1 else ""
    arrive_time = times[1] if len(times) >= 2 else ""

    # 航空公司：抓常見字（這段最需要對實際頁面微調）
    m_air = re.search(r"(亞洲航空|台灣虎航|長榮|中華航空|星宇|樂桃|捷星|國泰|"
                      r"日本航空|全日空|大韓航空|酷航|[A-Z][A-Za-z ]{2,}? Air[A-Za-z]*)",
                      text)
    airline = m_air.group(1).strip() if m_air else ""

    return {
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "origin": route["origin"],
        "dest": route["dest"],
        "date": route["date"],
        "price_twd": price,
        "transfers": transfers,           # 0=直飛；None=沒解析到
        "depart_time": depart_time,
        "arrive_time": arrive_time,
        "airline": airline,
        # TODO：行李額度（baggage）通常要點進票價詳情才有 → 之後補點擊流程
        "baggage": "",
        # TODO：航班號（flight number）同樣多在詳情頁，列表少見 → 之後補
        "flight_no": "",
    }


def extract_flights(page, route):
    """從已載入的結果頁抓所有航班。選擇器以實際頁面為準，可能要微調。"""
    # Google Flights 結果通常在 role=list 裡的 listitem；用多個候選選擇器較保險
    候選 = ["ul li.pIav2d", "[role='list'] [role='listitem']", "ul.Rk10dc li"]
    items = []
    for sel in 候選:
        try:
            page.wait_for_selector(sel, timeout=PAGE_TIMEOUT)
            items = page.query_selector_all(sel)
            if items:
                log.info("　用選擇器 '%s' 找到 %d 筆", sel, len(items))
                break
        except PWTimeout:
            continue
    if not items:
        log.warning("　找不到結果項目（選擇器可能要調，或頁面要求互動/驗證）。")
        return []

    rows = []
    for it in items:
        try:
            row = parse_card(it.inner_text(), route)
            if row:
                rows.append(row)
        except Exception as e:
            log.warning("　某筆解析失敗（略過）：%s", e)
    return rows


# ─────────────────────────────────────────────────────────────
# 抓單一航線（含重試 + 反爬基本款）
# ─────────────────────────────────────────────────────────────
def scrape_route(route):
    url = build_url(route)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=HEADLESS)
                ctx = browser.new_context(
                    user_agent=UA, locale="zh-TW",
                    viewport={"width": 1366, "height": 900})
                page = ctx.new_page()
                log.info("[%d/%d] 開瀏覽器抓 %s→%s（%s）",
                         attempt, MAX_RETRIES, route["origin"],
                         route["dest"], route["date"])
                page.goto(url, timeout=PAGE_TIMEOUT)
                # 可能跳同意/Cookie 視窗：嘗試按「全部接受」之類（找不到就略過）
                for t in ["全部接受", "我同意", "Accept all", "I agree"]:
                    try:
                        page.get_by_text(t, exact=False).first.click(timeout=2500)
                        break
                    except Exception:
                        pass
                page.wait_for_timeout(random.randint(1500, 3500))  # 禮貌等待
                rows = extract_flights(page, route)
                browser.close()
                return rows
        except PWTimeout as e:
            wait = BACKOFF_BASE ** attempt
            log.warning("逾時（第 %d 次）：%s → %d 秒後重試", attempt, e, wait)
            if attempt < MAX_RETRIES:
                time.sleep(wait)
        except Exception as e:
            log.exception("抓取出錯（第 %d 次）：%s", attempt, e)
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE ** attempt)
    log.error("重試 %d 次仍失敗：%s→%s", MAX_RETRIES, route["origin"], route["dest"])
    return []


# ─────────────────────────────────────────────────────────────
# 結構化儲存：CSV + JSON
# ─────────────────────────────────────────────────────────────
def save(rows):
    if not rows:
        log.info("沒有資料可存。")
        return
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    fields = list(rows[0].keys())
    new = not os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    log.info("已存 %d 筆 → %s（與 .json）", len(rows), OUTPUT_CSV)


def main():
    log.info("=== Google Flights 抓取開始（%d 條航線）===", len(ROUTES))
    all_rows = []
    for route in ROUTES:
        all_rows.extend(scrape_route(route))
        time.sleep(random.uniform(3, 6))  # 航線之間多等一下，降低被擋機率
    save(all_rows)
    log.info("=== 完成，共 %d 筆 ===", len(all_rows))


if __name__ == "__main__":
    main()
