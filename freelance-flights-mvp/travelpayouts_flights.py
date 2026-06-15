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
import urllib.parse
from datetime import date, datetime
from logging.handlers import RotatingFileHandler

import requests

# ─────────────────────────────────────────────────────────────
# 設定區（你自己改這裡）★ 想查哪幾條，就在 ROUTES 裡加幾行 ★
# ─────────────────────────────────────────────────────────────
# ★ 好消息：origin / dest 可以直接寫「中文地名」，程式會自動翻成代碼！★
#   （下面 地名對照表 有的就能用中文；沒有的就填代碼，例如某個冷門城市）
#   month  = 去程月份（必填）
#   return = 回程月份（選填）→ 有寫就查「來回票」，沒寫就查「單程」
ROUTES = [
    {"origin": "高雄", "dest": "日本",   "month": "2026-09", "return": "2026-09"},  # 全日本 來回
    {"origin": "高雄", "dest": "韓國",   "month": "2026-09", "return": "2026-09"},  # 全韓國 來回
    {"origin": "高雄", "dest": "泰國",   "month": "2026-09", "return": "2026-09"},  # 全泰國 來回
    {"origin": "高雄", "dest": "越南",   "month": "2026-09", "return": "2026-09"},  # 全越南 來回
    {"origin": "高雄", "dest": "香港",   "month": "2026-09", "return": "2026-09"},  # 香港 來回
    {"origin": "高雄", "dest": "新加坡", "month": "2026-09", "return": "2026-09"},  # 新加坡 來回
]

# 地名對照表：中文 → 代碼（要加新地點就在這裡多寫一行）
地名對照表 = {
    # 台灣
    "高雄": "KHH", "台北": "TPE", "台中": "RMQ", "桃園": "TPE",
    # 國家（查整個國家最便宜的城市）
    "日本": "JP", "韓國": "KR", "泰國": "TH", "越南": "VN",
    "香港": "HK", "新加坡": "SG", "馬來西亞": "MY", "菲律賓": "PH", "中國": "CN",
    # 城市
    "東京": "TYO", "大阪": "OSA", "福岡": "FUK", "名古屋": "NGO", "沖繩": "OKA",
    "首爾": "SEL", "釜山": "PUS", "曼谷": "BKK", "清邁": "CNX",
    "河內": "HAN", "胡志明": "SGN", "峴港": "DAD",
    "吉隆坡": "KUL", "馬尼拉": "MNL", "宿霧": "CEB", "上海": "SHA", "北京": "BJS",
}


def 轉代碼(name):
    """中文地名→代碼；對照表沒有的就當作已經是代碼，原樣回傳。"""
    return 地名對照表.get(name, name)


CURRENCY = "twd"         # 用新台幣報價
THRESHOLD = 15000        # 低於這個價（TWD）就跳通知（多國來回，先設寬一點 15000）

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
# 組一個「繁體中文」的 Skyscanner 訂票連結（點開就是中文頁）
# ─────────────────────────────────────────────────────────────
def build_skyscanner_link(origin, destination, outbound, inbound=""):
    params = {
        "origin": origin,
        "destination": destination,
        "outboundDate": outbound,    # YYYY-MM-DD
        "adultsv2": 1,
        "locale": "zh-TW",           # 繁體中文
        "market": "TW",              # 台灣
        "currency": "TWD",           # 新台幣
    }
    if inbound:
        params["inboundDate"] = inbound
    base = "https://www.skyscanner.net/g/referrals/v1/flights/day-view/"
    return base + "?" + urllib.parse.urlencode(params)


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
        "origin": 轉代碼(route["origin"]),       # 中文地名自動翻成代碼
        "destination": 轉代碼(route["dest"]),
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

    depart_at = cheapest.get("departure_at", "")[:10]
    return_at = cheapest.get("return_at", "")[:10]
    # 用實際查到的「機場代碼」組一個【繁體中文 Skyscanner】連結，一點開就是中文頁
    full_link = build_skyscanner_link(
        cheapest.get("origin_airport") or 轉代碼(route["origin"]),
        cheapest.get("destination_airport") or cheapest.get("destination")
        or 轉代碼(route["dest"]),
        depart_at,
        return_at if round_trip else "",
    )

    return {
        "date": str(date.today()),                       # 今天（記價日）
        "trip": "來回" if round_trip else "單程",
        "depart_at": depart_at,                          # 去程哪天
        "return_at": return_at,                          # 回程哪天（單程為空）
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
    # 寄到手機（Telegram）：只要環境變數 TG_TOKEN 和 TG_CHAT 都有設就會送。
    # 沒設就只印在畫面，不會出錯。（怎麼拿這兩個值，見 README / tg_setup.py）
    token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT")
    if token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": msg},
                timeout=10,
            )
            log.info("　已推送到 Telegram。")
        except requests.RequestException as e:
            # 通知失敗不該害整個程式掛掉，記一筆就好
            log.warning("　Telegram 推送失敗（不影響記價）：%s", e)


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
