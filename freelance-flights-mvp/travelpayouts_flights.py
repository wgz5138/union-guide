#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高雄 ↔ 東京 便宜機票每日記價 + 降價通知（用 Travelpayouts / Aviasales 免費資料 API）

這支不是「爬網站」，是直接跟 Travelpayouts 要資料——免費、合法、不怕被封。
資料來源是 Aviasales 用戶最近實際查到的最低票價。

────────────────────────────────────────────────────────
怎麼開始用（你已經註冊好、也拿到 token 了）
────────────────────────────────────────────────────────
1. 把你的 token 設成「環境變數」（比寫死在程式裡安全）：
       Mac/Linux：
           export TRAVELPAYOUTS_TOKEN="你的token"
       Windows（PowerShell）：
           setx TRAVELPAYOUTS_TOKEN "你的token"
       （Windows 設完要重開終端機才生效）
2. 安裝套件：pip install requests
3. 執行：python travelpayouts_flights.py

跑完看 data/khh_tyo_price.csv（每天一列價格）和 logs/scraper.log。
低於門檻價會在畫面提醒；要寄到手機，照下面 notify() 接 Telegram。
"""

import csv
import logging
import os
import time
from datetime import date, datetime
from logging.handlers import RotatingFileHandler

import requests

# ─────────────────────────────────────────────────────────────
# 設定區（你自己改這裡）
# ─────────────────────────────────────────────────────────────
ORIGIN = "KHH"           # 出發：高雄小港
DEST = "TYO"             # 抵達：東京（TYO=成田+羽田都算）
DEPART_MONTH = "2026-08"  # 想查的出發月份（查整個月最便宜；也可寫到日 2026-08-01）
CURRENCY = "twd"         # 用新台幣報價
THRESHOLD = 8000         # 低於這個價（TWD）就通知你
ONE_WAY = True           # True=單程；False=來回

OUTPUT_CSV = os.path.join("data", "khh_tyo_price.csv")
LOG_FILE = os.path.join("logs", "scraper.log")

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
TOKEN = os.environ.get("TRAVELPAYOUTS_TOKEN", "")

# 穩定性參數
MAX_RETRIES = 3
BACKOFF_BASE = 2
TIMEOUT = 20


# ─────────────────────────────────────────────────────────────
# log（同時印畫面 + 寫檔，檔案自動輪替）
# ─────────────────────────────────────────────────────────────
def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logger = logging.getLogger("travelpayouts")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)
    fileh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000,
                                backupCount=3, encoding="utf-8")
    fileh.setFormatter(fmt)
    logger.addHandler(fileh)
    return logger


log = setup_logging()


# ─────────────────────────────────────────────────────────────
# 帶重試的請求（這就是「高穩定性」的心臟）
# ─────────────────────────────────────────────────────────────
def get_json_with_retry(url, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_err = e
            wait = BACKOFF_BASE ** attempt
            log.warning("第 %d/%d 次失敗：%s → %d 秒後重試",
                        attempt, MAX_RETRIES, e, wait)
            if attempt < MAX_RETRIES:
                time.sleep(wait)
    raise RuntimeError(f"重試 {MAX_RETRIES} 次仍失敗：{url}（最後錯誤：{last_err}）")


# ─────────────────────────────────────────────────────────────
# 查最便宜的票
# ─────────────────────────────────────────────────────────────
def search_cheapest():
    if not TOKEN:
        raise RuntimeError(
            "找不到 token！請先設定環境變數 TRAVELPAYOUTS_TOKEN"
            "（做法見本檔案開頭說明）。")

    result = get_json_with_retry(
        API_URL,
        headers={"X-Access-Token": TOKEN},
        params={
            "origin": ORIGIN,
            "destination": DEST,
            "departure_at": DEPART_MONTH,
            "currency": CURRENCY,
            "sorting": "price",
            "one_way": str(ONE_WAY).lower(),  # "true"/"false"
            "limit": 30,
        },
    )

    if not result.get("success", True):
        raise RuntimeError(f"API 回報錯誤：{result}")

    offers = result.get("data", [])
    if not offers:
        log.info("這個條件查無票價（換個月份或日期試試）。")
        return None

    cheapest = min(offers, key=lambda o: o["price"])
    currency = result.get("currency", CURRENCY).upper()

    # 組出可直接點開看的搜尋連結（link 是相對路徑）
    link = cheapest.get("link", "")
    full_link = ("https://www.aviasales.com" + link) if link else ""

    return {
        "date": str(date.today()),                       # 今天（記價日）
        "depart_at": cheapest.get("departure_at", "")[:10],  # 這班是哪天出發
        "route": f"{ORIGIN}-{DEST}",
        "price": cheapest["price"],
        "currency": currency,
        "airline": cheapest.get("airline", "?"),         # 航空公司代碼
        "transfers": cheapest.get("transfers", "?"),     # 0=直飛
        "link": full_link,
    }


# ─────────────────────────────────────────────────────────────
# 存進 CSV（每天一列）
# ─────────────────────────────────────────────────────────────
def save_csv(row):
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    row["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    log.info("已記錄：%s %s（%s，轉機 %s 次）→ %s",
             row["price"], row["currency"], row["airline"],
             row["transfers"], OUTPUT_CSV)


# ─────────────────────────────────────────────────────────────
# 低於門檻就通知（先印畫面；要寄手機就接 Telegram）
# ─────────────────────────────────────────────────────────────
def notify(row):
    msg = (f"✈️ 便宜票！{row['route']} {row['depart_at']} 出發 "
           f"只要 {row['price']:.0f} {row['currency']}"
           f"（{row['airline']}，轉機 {row['transfers']} 次）\n{row['link']}")
    log.info("🔔 %s", msg)
    # 想寄到手機：去 Telegram 找 @BotFather 建一個 bot 拿 token，再解除下面註解
    # token, chat_id = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    # if token and chat_id:
    #     requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
    #                   data={"chat_id": chat_id, "text": msg}, timeout=10)


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────
def main():
    log.info("=== 查 %s→%s（%s 出發，%s）===",
             ORIGIN, DEST, DEPART_MONTH, "單程" if ONE_WAY else "來回")
    try:
        row = search_cheapest()
        if not row:
            return
        save_csv(row)
        if row["price"] < THRESHOLD:
            notify(row)
        else:
            log.info("目前最低 %.0f %s，還沒到你設的門檻 %d，先記著。",
                     row["price"], row["currency"], THRESHOLD)
        log.info("=== 完成 ===")
    except Exception as e:
        log.exception("執行失敗：%s", e)
        raise


if __name__ == "__main__":
    main()
