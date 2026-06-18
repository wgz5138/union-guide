#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台北 ↔ 東京 機票每日記價 + 降價通知（用 Amadeus 免費 API）

這支不是「爬網站」，是直接跟 Amadeus 官方要資料——更穩、合法、不怕被封。

────────────────────────────────────────────────────────
怎麼開始用（一次性，約 5 分鐘）
────────────────────────────────────────────────────────
1. 去 https://developers.amadeus.com 註冊（免費）
2. 建一個 App → 拿到兩串金鑰：API Key 和 API Secret
3. 把金鑰設成「環境變數」（比寫死在程式裡安全）：
       Mac/Linux：
           export AMADEUS_API_KEY="你的key"
           export AMADEUS_API_SECRET="你的secret"
       Windows（PowerShell）：
           setx AMADEUS_API_KEY "你的key"
           setx AMADEUS_API_SECRET "你的secret"
       （Windows 設完要重開終端機才生效）
4. 安裝套件：pip install requests
5. 執行：python amadeus_flights.py

跑完看 data/tpe_tyo_price.csv（每天一列價格）和 logs/scraper.log。
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
ORIGIN = "TPE"            # 出發：台北桃園
DEST = "TYO"              # 抵達：東京（TYO=成田+羽田都算）
DEPART_DATE = "2026-08-01"  # 想查的出發日
ADULTS = 1
CURRENCY = "TWD"          # 用新台幣報價
THRESHOLD = 8000          # 低於這個價（TWD）就通知你

OUTPUT_CSV = os.path.join("data", "tpe_tyo_price.csv")
LOG_FILE = os.path.join("logs", "scraper.log")

# Amadeus 免費「測試環境」。等你要正式上線、要真實即時資料，
# 再把下面換成 https://api.amadeus.com（並改用正式金鑰）。
BASE = "https://test.api.amadeus.com"

# 金鑰從環境變數讀（見檔案開頭說明）
API_KEY = os.environ.get("AMADEUS_API_KEY", "")
API_SECRET = os.environ.get("AMADEUS_API_SECRET", "")

# 穩定性參數
MAX_RETRIES = 3
BACKOFF_BASE = 2
TIMEOUT = 20


# ─────────────────────────────────────────────────────────────
# log（同時印畫面 + 寫檔，檔案自動輪替）
# ─────────────────────────────────────────────────────────────
def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logger = logging.getLogger("amadeus")
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
def request_with_retry(method, url, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, **kwargs)
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
# 步驟一：登入拿 token
# ─────────────────────────────────────────────────────────────
def get_token():
    if not API_KEY or not API_SECRET:
        raise RuntimeError(
            "找不到金鑰！請先設定環境變數 AMADEUS_API_KEY / AMADEUS_API_SECRET"
            "（做法見本檔案開頭說明）。")
    data = request_with_retry(
        "POST", f"{BASE}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": API_KEY,
            "client_secret": API_SECRET,
        },
    )
    log.info("登入成功，取得 token。")
    return data["access_token"]


# ─────────────────────────────────────────────────────────────
# 步驟二：查最便宜的票
# ─────────────────────────────────────────────────────────────
def search_cheapest(token):
    result = request_with_retry(
        "GET", f"{BASE}/v2/shopping/flight-offers",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "originLocationCode": ORIGIN,
            "destinationLocationCode": DEST,
            "departureDate": DEPART_DATE,
            "adults": ADULTS,
            "currencyCode": CURRENCY,
            "max": 20,  # 拿前 20 筆，自己挑最便宜
        },
    )
    offers = result.get("data", [])
    if not offers:
        log.info("這個日期查無航班。")
        return None

    # 找出最便宜那一筆
    cheapest = min(offers, key=lambda o: float(o["price"]["total"]))
    price = float(cheapest["price"]["total"])
    currency = cheapest["price"]["currency"]

    # 第一段航班的航空公司代碼（方便你認）
    carrier = (cheapest["itineraries"][0]["segments"][0]
               .get("carrierCode", "?"))
    stops = len(cheapest["itineraries"][0]["segments"]) - 1  # 0=直飛

    return {
        "date": str(date.today()),     # 今天（記價日）
        "depart_date": DEPART_DATE,    # 這是哪天出發的票
        "route": f"{ORIGIN}-{DEST}",
        "price": price,
        "currency": currency,
        "carrier": carrier,
        "stops": stops,                # 0=直飛，1=轉一次…
    }


# ─────────────────────────────────────────────────────────────
# 步驟三：存進 CSV（每天一列）
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
    log.info("已記錄：%s %s（%s 直飛數%s）→ %s",
             row["price"], row["currency"], row["carrier"],
             row["stops"], OUTPUT_CSV)


# ─────────────────────────────────────────────────────────────
# 步驟四：低於門檻就通知（先印畫面；要寄手機就接 Telegram）
# ─────────────────────────────────────────────────────────────
def notify(row):
    msg = (f"✈️ 便宜票！{row['route']} {row['depart_date']} 出發 "
           f"只要 {row['price']:.0f} {row['currency']}"
           f"（{row['carrier']}，直飛數 {row['stops']}）")
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
    log.info("=== 查 %s→%s（%s 出發）===", ORIGIN, DEST, DEPART_DATE)
    try:
        token = get_token()
        row = search_cheapest(token)
        if not row:
            return
        save_csv(row)
        if row["price"] < THRESHOLD:
            notify(row)
        else:
            log.info("目前 %.0f %s，還沒到你設的門檻 %d，先記著。",
                     row["price"], row["currency"], THRESHOLD)
        log.info("=== 完成 ===")
    except Exception as e:
        log.exception("執行失敗：%s", e)
        raise


if __name__ == "__main__":
    main()
