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
import json
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
#   month  = 去程月份（選填！不寫就自動查「這個月起」連續 FLEX_MONTHS_AHEAD
#            個月、挑最便宜的──這樣不用一直手動改月份，也不會日期一過
#            就永遠查不到卻沒人發現）
#   return = 回程月份（選填）→ 有寫就查「來回票」，沒寫就查「單程」
#            （來回票請連 month 一起指定，彈性月份目前只支援單程）
ROUTES = [
    {"origin": "高雄", "dest": "日本"},    # 全日本 單程・自動查未來幾個月最便宜
    {"origin": "高雄", "dest": "韓國"},    # 全韓國 單程・自動查未來幾個月最便宜
    {"origin": "高雄", "dest": "泰國"},    # 全泰國 單程・自動查未來幾個月最便宜
    {"origin": "高雄", "dest": "越南"},    # 全越南 單程・自動查未來幾個月最便宜
    {"origin": "高雄", "dest": "香港"},    # 香港   單程・自動查未來幾個月最便宜
    {"origin": "高雄", "dest": "新加坡"},  # 新加坡 單程・自動查未來幾個月最便宜
]

# 地名對照表：中文 → 代碼（要加新地點就在這裡多寫一行）
地名對照表 = {
    # 台灣
    "高雄": "KHH", "台北": "TPE", "台中": "RMQ", "桃園": "TPE",
    # 國家（查整個國家最便宜的城市）
    "日本": "JP", "韓國": "KR", "泰國": "TH", "越南": "VN",
    "香港": "HK", "新加坡": "SG", "馬來西亞": "MY", "菲律賓": "PH", "中國": "CN",
    # 日本城市
    "東京": "TYO", "大阪": "OSA", "福岡": "FUK", "名古屋": "NGO",
    "沖繩": "OKA", "那霸": "OKA", "札幌": "SPK", "北海道": "SPK",
    # 韓國城市
    "首爾": "SEL", "釜山": "PUS", "濟州": "CJU", "大邱": "TAE",
    # 東南亞城市
    "曼谷": "BKK", "清邁": "CNX", "普吉島": "HKT", "河內": "HAN",
    "胡志明": "SGN", "峴港": "DAD", "吉隆坡": "KUL", "馬尼拉": "MNL",
    "宿霧": "CEB", "峇里島": "DPS", "澳門": "MFM",
    # 中國城市
    "上海": "SHA", "北京": "BJS", "重慶": "CKG", "成都": "CTU",
    "廣州": "CAN", "深圳": "SZX", "杭州": "HGH", "廈門": "XMN",
    "南京": "NKG", "青島": "TAO", "西安": "SIA", "武漢": "WUH", "昆明": "KMG",
}


def 轉代碼(name):
    """中文地名→代碼；對照表沒有的就當作已經是代碼，原樣回傳。"""
    return 地名對照表.get(name, name)


def next_months(n=3):
    """回傳從『這個月』起連續 n 個月份字串 YYYY-MM（本月也算在內）。
    給『沒指定月份』時自動查用──這樣不用每次手動打年月，也不會因為
    寫死某個月份、日期一過就永遠查不到而不自知（見 FLEX_MONTHS_AHEAD）。"""
    y, m = date.today().year, date.today().month
    out = []
    for i in range(n):
        total = m - 1 + i
        out.append(f"{y + total // 12:04d}-{total % 12 + 1:02d}")
    return out


CURRENCY = "twd"         # 用新台幣報價
THRESHOLD = 15000        # 低於這個價（TWD）就跳通知（多國來回，先設寬一點 15000）
FLEX_MONTHS_AHEAD = 3    # route 沒填 "month" 時，自動查「這個月起」連續幾個月

# 資料與 log 都放在「程式所在的資料夾」底下（不管從哪裡點兩下執行都一樣），
# 所以你把專案放 F 槽，data/ 和 logs/ 就在 F 槽，全部集中、好找。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "flight_prices.csv")
LOG_FILE = os.path.join(BASE_DIR, "logs", "scraper.log")
# 記每條航線「上次的價格」，用來判斷有沒有降價（只在變便宜時才通知，不洗版）。
STATE_FILE = os.path.join(BASE_DIR, "price_state.json")

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
# 查票：底層拿回所有票，再給上層挑「最便宜一張」或「列出多個選項」
# ─────────────────────────────────────────────────────────────
def _fetch_offers(route):
    """打 API 拿回這條航線的所有票。回傳 (offers, currency, round_trip)。
    route 沒填 "month"（沒打年月）就自動查未來 FLEX_MONTHS_AHEAD 個月、
    合併所有結果──不用每次手動打年月，也不怕月份寫死了、日期一過就
    永遠查不到卻沒人發現（原本 API 的 departure_at 到底能不能留空、
    留空後行為為何，官方文件查證不到明確結果，所以不賭它，改用
    我們自己算好的月份清單，行為 100% 可控可測）。"""
    if not TOKEN:
        raise RuntimeError(
            "找不到 token！請先設定環境變數 TRAVELPAYOUTS_TOKEN"
            "（做法見本檔案開頭說明）。")

    round_trip = "return" in route  # 有填回程 = 來回票
    months = [route["month"]] if route.get("month") else next_months(FLEX_MONTHS_AHEAD)

    all_offers = []
    currency = CURRENCY.upper()
    for month in months:
        params = {
            "origin": 轉代碼(route["origin"]),       # 中文地名自動翻成代碼
            "destination": 轉代碼(route["dest"]),
            "departure_at": month,
            "currency": CURRENCY,
            "sorting": "price",
            "one_way": "false" if round_trip else "true",
            "limit": 30,
        }
        if round_trip:
            params["return_at"] = route["return"]  # 回程月份

        result = get_json_with_retry(
            API_URL, headers={"X-Access-Token": TOKEN}, params=params)
        if not result.get("success", True):
            raise RuntimeError(f"API 回報錯誤：{result}")

        currency = result.get("currency", CURRENCY).upper()
        # 只留有 price 的票，避免後面 min()/取值時 KeyError
        all_offers.extend(o for o in result.get("data", []) if o.get("price") is not None)

    return all_offers, currency, round_trip


def _build_row(offer, route, currency, round_trip):
    """把一張票的原始資料整理成統一格式（含中文 Skyscanner 連結）。"""
    depart_at = offer.get("departure_at", "")[:10]
    return_at = offer.get("return_at", "")[:10]
    dest_code = (offer.get("destination_airport")
                 or offer.get("destination") or 轉代碼(route["dest"]))
    full_link = build_skyscanner_link(
        offer.get("origin_airport") or 轉代碼(route["origin"]),
        dest_code, depart_at, return_at if round_trip else "")
    return {
        "date": str(date.today()),
        "trip": "來回" if round_trip else "單程",
        "depart_at": depart_at,
        "return_at": return_at,
        "route": f"{route['origin']}-{route['dest']}",
        "dest_code": dest_code,                          # 實際抵達城市代碼
        "price": offer["price"],
        "currency": currency,
        "airline": offer.get("airline", "?"),
        "transfers": offer.get("transfers", "?"),        # 0=直飛
        "link": full_link,
    }


def search_cheapest(route):
    """查單一條航線『最便宜的一張』。route 有 return 就查來回，否則單程。"""
    offers, currency, round_trip = _fetch_offers(route)
    if not offers:
        月份說明 = route.get("month") or f"未來{FLEX_MONTHS_AHEAD}個月"
        log.info("　%s→%s（%s）查無票價（換個月份試試）。",
                 route["origin"], route["dest"], 月份說明)
        return None
    cheapest = min(offers, key=lambda o: o["price"])
    return _build_row(cheapest, route, currency, round_trip)


def search_offers(route, top=5, direct_first=True):
    """列出『多張』便宜的票（給使用者挑）。查整個國家時會看到不同城市。
    direct_first=True：若有直飛，優先只列直飛；都沒有才列含轉機的。"""
    offers, currency, round_trip = _fetch_offers(route)
    if not offers:
        return []
    directs = [o for o in offers if o.get("transfers") == 0]
    use = directs if (direct_first and directs) else offers
    use = sorted(use, key=lambda o: o["price"])[:top]
    return [_build_row(o, route, currency, round_trip) for o in use]


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
# 降價偵測：記住每條航線上次的價格
# ─────────────────────────────────────────────────────────────
def load_state():
    """讀回上次各航線的價格 {航線: 價格}。檔案不存在或壞掉就回空的。"""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except OSError as e:
        log.warning("　價格狀態存檔失敗（不影響查價）：%s", e)


# ─────────────────────────────────────────────────────────────
# 通知（印畫面；TG 有設就推手機）。降價時訊息會多一行省多少。
# ─────────────────────────────────────────────────────────────
def notify(row):
    when = row["depart_at"]
    if row["trip"] == "來回" and row["return_at"]:
        when += f" 去 / {row['return_at']} 回"
    drop = ""
    if row.get("drop_from"):
        省 = row["drop_from"] - row["price"]
        drop = f"\n📉 降價了！上次 {row['drop_from']:.0f}，這次省 {省:.0f} 元"
    msg = (f"✈️ 便宜票！{row['route']}（{row['trip']}）{when} "
           f"只要 {row['price']:.0f} {row['currency']}"
           f"（{row['airline']}，轉機 {row['transfers']} 次）{drop}\n{row['link']}")
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
    state = load_state()   # 上次各航線的價格
    deals = 0              # 這次有幾條值得通知
    failed = 0             # 這次有幾條查詢失敗（不中斷其他航線）
    for i, route in enumerate(ROUTES):
        # 每條航線獨立包例外：單一航線失敗（如 API 連續逾時）只略過該條，
        # 不能讓後面的航線都不查、也不能讓已查到的價格記憶跟著遺失
        # （save_state 在迴圈外，若整個迴圈被例外中斷，之前查到的都不會存檔）。
        try:
            trip = "來回" if "return" in route else "單程"
            月份說明 = route.get("month") or f"未來{FLEX_MONTHS_AHEAD}個月"
            log.info("[%d/%d] 查 %s→%s（%s，%s）",
                     i + 1, len(ROUTES), route["origin"],
                     route["dest"], 月份說明, trip)
            row = search_cheapest(route)
            if not row:
                continue
            save_csv(row)

            上次 = state.get(row["route"])
            價格 = row["price"]
            # 通知規則：① 比上次便宜 → 一定通知（並標降了多少）
            #          ② 第一次看到這條，且低於門檻 → 通知
            #          ③ 沒變便宜（持平或變貴）→ 不通知，避免洗版
            if 上次 is not None and 價格 < 上次:
                row["drop_from"] = 上次
                notify(row)
                deals += 1
            elif 上次 is None and 價格 < THRESHOLD:
                notify(row)
                deals += 1
            else:
                log.info("　最低 %.0f %s（上次 %s），沒變便宜，不通知。",
                         價格, row["currency"],
                         f"{上次:.0f}" if 上次 is not None else "無紀錄")

            state[row["route"]] = 價格   # 更新這條的最新價
        except Exception as e:
            failed += 1
            log.exception("　%s→%s：查詢失敗，略過（不影響其他航線）：%s",
                          route["origin"], route["dest"], e)
        finally:
            time.sleep(1)  # 禮貌性間隔，別把人家 API 打太兇

    save_state(state)   # 不管中途有沒有航線失敗，已查到的價格記憶都要存下來
    log.info("=== 完成：%d 條航線，%d 條值得通知，%d 條失敗 ===",
             len(ROUTES), deals, failed)

    if ROUTES and failed == len(ROUTES):
        # 全部航線都失敗，很可能是系統性問題（例如 TOKEN 沒設定、API 整個掛掉），
        # 已查到的（本例中為 0 筆）都已存檔；但仍要讓程式以非零結束碼收尾，
        # 排程／GitHub Actions 才不會把「整批全滅」誤判成一切正常而悄悄過關。
        raise RuntimeError(f"全部 {len(ROUTES)} 條航線都查詢失敗，詳見上方 log。")


if __name__ == "__main__":
    main()
