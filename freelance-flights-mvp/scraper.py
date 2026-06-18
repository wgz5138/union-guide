#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小可動爬蟲骨架（MVP）— 機票監測案 A2310 練手 / 起點版

這支程式「現在就能跑」：它預設去抓一個專門給人練爬蟲的合法沙盒網站
（quotes.toscrape.com），讓你馬上看到「重試 → 抓取 → 解析 → 存 CSV → log」
整條流水線會動。等你跟客戶確認了真正的機票網站，只要改 parse_flights()
和設定區，就能變成正式案子。

接案重點：客戶要的「高穩定性」不是某個魔法函式，而是下面這幾招的組合——
  1. 逾時 timeout（不要無限等）
  2. 失敗自動重試 + 間隔逐次拉長（exponential backoff）
  3. 寫 log（出事看得到原因）
  4. 失敗時通知你（notify）
  5. 每次請求之間禮貌性隨機等待（別把人家網站打爆 / 被封）

用法：
    pip install -r requirements.txt
    python scraper.py
跑完看 data/flights.csv 和 logs/scraper.log。
"""

import csv
import logging
import os
import random
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────
# 設定區（接案時這一塊通常就是「跟客戶確認」的那些問題）
# ─────────────────────────────────────────────────────────────
USE_DEMO = True  # True=跑練手沙盒；確認真網站後改 False，走 parse_flights()

# 練手沙盒（合法、穩定、專門給人爬）
DEMO_URL = "https://quotes.toscrape.com/"

# 你的真實目標（跟客戶問到網址後填這裡）
TARGET_URL = "https://example.com/REPLACE_ME"

# 要監測的航線（示範用；真實案子讓客戶決定、或做成可設定）
ROUTES = [
    {"origin": "TPE", "dest": "TYO", "date": "2026-08-01"},
]

OUTPUT_CSV = os.path.join("data", "flights.csv")
LOG_FILE = os.path.join("logs", "scraper.log")

# 穩定性參數
MAX_RETRIES = 3          # 最多重試幾次
BACKOFF_BASE = 2         # 重試間隔基數：2s, 4s, 8s ...
REQUEST_TIMEOUT = 15     # 單次請求逾時（秒）
POLITE_DELAY = (1.5, 4)  # 每次抓取之間隨機等待（秒），避免太兇被封

# 換著用的瀏覽器標頭，降低被當機器人的機率
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


# ─────────────────────────────────────────────────────────────
# log 設定：同時印到畫面 + 寫進檔案（檔案會自動輪替，不會無限長大）
# ─────────────────────────────────────────────────────────────
def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logger = logging.getLogger("flights")
    logger.setLevel(logging.INFO)
    if logger.handlers:  # 避免重複加 handler
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    fileh = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    fileh.setFormatter(fmt)
    logger.addHandler(fileh)
    return logger


log = setup_logging()


# ─────────────────────────────────────────────────────────────
# 核心：帶重試的抓取（這就是「高穩定性」的心臟）
# ─────────────────────────────────────────────────────────────
def fetch_with_retry(url):
    """抓一個網址，失敗就重試，間隔逐次拉長。全試完還失敗就丟出例外。"""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            log.info("抓取中（第 %d/%d 次）：%s", attempt, MAX_RETRIES, url)
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()  # 4xx/5xx 直接當失敗
            return resp.text
        except requests.RequestException as e:
            last_err = e
            wait = BACKOFF_BASE ** attempt
            log.warning("第 %d 次失敗：%s → %d 秒後重試", attempt, e, wait)
            if attempt < MAX_RETRIES:
                time.sleep(wait)
    raise RuntimeError(f"重試 {MAX_RETRIES} 次仍失敗：{url}（最後錯誤：{last_err}）")


# ─────────────────────────────────────────────────────────────
# 解析：把抓回來的 HTML 變成一列一列的資料（dict）
# ─────────────────────────────────────────────────────────────
def parse_demo(html):
    """練手用：解析 quotes.toscrape.com，證明整條流水線會動。"""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for q in soup.select("div.quote"):
        rows.append({
            "quote": q.select_one("span.text").get_text(strip=True),
            "author": q.select_one("small.author").get_text(strip=True),
            "tags": ",".join(t.get_text(strip=True) for t in q.select("a.tag")),
        })
    return rows


def parse_flights(html, route):
    """
    正式版：解析機票資料。確認目標網站後在這裡寫。

    兩種策略（接案前先用瀏覽器 F12 → Network → XHR 偵查走哪條）：

      [上策] 網站背後有回傳 JSON 的 API：
          根本不用解析 HTML，直接 requests.get(那個 api 網址).json()
          再從 json 取欄位。最穩、最快。

      [中策] 資料就在 HTML 裡（靜態）：
          用 BeautifulSoup 像下面這樣 select 出來。

      [下策] 資料靠 JavaScript 動態長出來（例：Google Flights）：
          requests 抓到的會是空殼。改用 scraper_playwright.py 開真瀏覽器。

    回傳：list[dict]，每個 dict 是一筆航班，欄位對齊 CSV 表頭。
    """
    # TODO：把下面換成真實選擇器 / JSON 取值
    rows = []
    # soup = BeautifulSoup(html, "html.parser")
    # for card in soup.select("REPLACE_ME"):
    #     rows.append({
    #         "origin": route["origin"],
    #         "dest": route["dest"],
    #         "date": route["date"],
    #         "price": card.select_one("REPLACE_ME").get_text(strip=True),
    #         "flight_no": card.select_one("REPLACE_ME").get_text(strip=True),
    #         "stops": card.select_one("REPLACE_ME").get_text(strip=True),
    #         "baggage": card.select_one("REPLACE_ME").get_text(strip=True),
    #     })
    return rows


# ─────────────────────────────────────────────────────────────
# 存檔：append 進 CSV，第一次自動寫表頭，每列加抓取時間
# ─────────────────────────────────────────────────────────────
def save_csv(rows):
    if not rows:
        log.info("這次沒有可寫入的資料。")
        return
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for r in rows:
        r["scraped_at"] = stamp  # 監測案一定要留「這筆是什麼時候抓的」

    file_exists = os.path.exists(OUTPUT_CSV)
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)
    log.info("已寫入 %d 筆 → %s", len(rows), OUTPUT_CSV)


# ─────────────────────────────────────────────────────────────
# 失敗通知（先留鉤子，交付時依客戶要的管道接上）
# ─────────────────────────────────────────────────────────────
def notify_failure(message):
    """全部失敗時通知。下面示範 Telegram；客戶要 Email 再換。
    （提醒：LINE Notify 已於 2025 年停用，別再用。）"""
    log.error("需要通知：%s", message)
    # 範例（填好 token/chat_id 再解除註解）：
    # token, chat_id = "YOUR_BOT_TOKEN", "YOUR_CHAT_ID"
    # requests.post(
    #     f"https://api.telegram.org/bot{token}/sendMessage",
    #     data={"chat_id": chat_id, "text": message}, timeout=10,
    # )


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────
def main():
    log.info("=== 開始執行 ===（模式：%s）", "練手沙盒" if USE_DEMO else "正式")
    all_rows = []
    try:
        if USE_DEMO:
            html = fetch_with_retry(DEMO_URL)
            all_rows = parse_demo(html)
        else:
            for route in ROUTES:
                # 真實案子：通常 TARGET_URL 要帶上航線/日期參數
                html = fetch_with_retry(TARGET_URL)
                all_rows.extend(parse_flights(html, route))
                time.sleep(random.uniform(*POLITE_DELAY))  # 禮貌等待
        save_csv(all_rows)
        log.info("=== 完成 ===（共 %d 筆）", len(all_rows))
    except Exception as e:
        # 把錯誤寫進 log 並通知，不要讓程式默默死掉
        log.exception("執行失敗：%s", e)
        notify_failure(f"機票監測失敗：{e}")
        raise


if __name__ == "__main__":
    main()
