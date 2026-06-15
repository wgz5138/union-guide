#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多航線便宜機票每日記價 + 降價通知（用 Travelpayouts / Aviasales 免費資料 API）
（想查哪幾條，改最下面設定區的 ROUTES 就好）

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

跑完看 data/flight_prices.csv（每條航線各一列價格）和 logs/scraper.log。
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
# 設定區（你自己改這裡）★ 想查哪幾條，就在 ROUTES 裡加幾行 ★
# ─────────────────────────────────────────────────────────────
# 每一行 = 一條航線。複製一行、改代碼和月份，就多查一條。
#   month  = 去程月份（必填）
#   return = 回程月份（選填）→ 有寫就查「來回票」，沒寫就查「單程」
# 城市代碼：高雄 KHH、台北 TPE、東京 TYO、大阪 OSA、福岡 FUK、
#          首爾 SEL、曼谷 BKK、香港 HKG、新加坡 SIN
# 也可填「國家代碼」查整個國家最便宜的：日本 JP、中國 CN、韓國 KR、泰國 TH
# （不確定就 Google「城市 機場代碼」）
ROUTES = [
    {"origin": "KHH", "dest": "JP", "month": "2026-08"},                      # 高雄→全日本（單程）
    {"origin": "KHH", "dest": "TYO", "month": "2026-08", "return": "2026-08"},  # 高雄→東京（來回，8月去8月回）
    {"origin": "KHH", "dest": "OSA", "month": "2026-09", "return": "2026-09"},  # 高雄→大阪（來回，9月）
]

CURRENCY = "twd"         # 用新台幣報價
THRESHOLD = 10000        # 低於這個價（TWD）就跳通知（來回票較貴，先設 10000）

OUTPUT_CSV = os.path.join("data", "flight_prices.csv")
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
def search_cheapest(route):
    """查單一條航線最便宜的票。route 有 return 就查來回，否則查單程。"""
    if not TOKEN:
        raise RuntimeError(
            "找不到 token！請先設定環境變數 TRAVELPAYOUTS_TOKEN"
            "（做法見本檔案開頭說明）。")

    round_trip = "return" in route  # 有填回程 = 來回票
    params = {
        "origin": route["origin"],
        "destination": route["dest"],
        "departure_at": route["month"],
        "currency": CURRENCY,
        "sorting": "price",
        "one_way": "false" if round_trip else "true",
        "limit": 30,
    }
    if round_trip:
        params["return_at"] = route["return"]  # 回程月份

    result = get_json_with_retry(
        API_URL,
        headers={"X-Access-Token": TOKEN},
        params=params,
    )

    if not result.get("success", True):
        raise RuntimeError(f"API 回報錯誤：{result}")

    offers = result.get("data", [])
    if not offers:
        log.info("　%s→%s（%s）查無票價（換個月份試試）。",
                 route["origin"], route["dest"], route["month"])
        return None

    cheapest = min(offers, key=lambda o: o["price"])
    currency = result.get("currency", CURRENCY).upper()

    # 組出可直接點開看的搜尋連結（link 是相對路徑）
    link = cheapest.get("link", "")
    full_link = ("https://www.aviasales.com" + link) if link else ""

    return {
        "date": str(date.today()),                       # 今天（記價日）
        "trip": "來回" if round_trip else "單程",
        "depart_at": cheapest.get("departure_at", "")[:10],  # 去程哪天
        "return_at": cheapest.get("return_at", "")[:10],     # 回程哪天（單程為空）
        "route": f"{route['origin']}-{route['dest']}",
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
    when = row["depart_at"]
    if row["trip"] == "來回" and row["return_at"]:
        when += f" 去 / {row['return_at']} 回"
    msg = (f"✈️ 便宜票！{row['route']}（{row['trip']}）{when} "
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
    log.info("=== 開始查 %d 條航線 ===", len(ROUTES))
    deals = 0  # 這次有幾條低於門檻
    try:
        for i, route in enumerate(ROUTES):
            trip = "來回" if "return" in route else "單程"
            log.info("[%d/%d] 查 %s→%s（%s，%s）",
                     i + 1, len(ROUTES), route["origin"],
                     route["dest"], route["month"], trip)
            row = search_cheapest(route)
            if not row:
                continue
            save_csv(row)
            if row["price"] < THRESHOLD:
                notify(row)
                deals += 1
            else:
                log.info("　最低 %.0f %s，還沒到門檻 %d，先記著。",
                         row["price"], row["currency"], THRESHOLD)
            time.sleep(1)  # 禮貌性間隔，別把人家 API 打太兇
        log.info("=== 完成：%d 條航線，%d 條低於門檻 ===", len(ROUTES), deals)
    except Exception as e:
        log.exception("執行失敗：%s", e)
        raise


if __name__ == "__main__":
    main()
