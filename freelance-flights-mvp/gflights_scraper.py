#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 機票數據抓取（A2310 案・正式版）

本檔整併了實際驗證成功的做法：
  • stealth（隱藏自動化特徵）+ 持久化設定檔（保留 cookie/同意）→ 過反爬、提高成功率
  • 失敗自動重試到成功 → 真正的「高穩定性」
  • 「靠內容找卡 + 文字正則解析」→ 不依賴會變的亂碼 class
  • 多航線/多日期、結構化儲存（CSV + JSON）、log

已可穩定取得：票價、轉機次數、起降時間、航空公司。
（航班號、行李額度需點進票價詳情頁，為後續可擴充項目。）

⚠️ Google ToS 禁止自動抓取；正式委託請先與客戶確認合規與頻率/封鎖風險。

安裝：
    pip install playwright
    playwright install chromium
執行：
    python gflights_scraper.py
"""

import csv
import json
import logging
import os
import re
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────────────────────
# 設定區（出發/抵達用 IATA 代碼；日期 YYYY-MM-DD）
# ─────────────────────────────────────────────────────────────
ROUTES = [
    {"origin": "KHH", "dest": "NRT", "date": "2026-09-15"},  # 高雄→東京
    {"origin": "KHH", "dest": "KIX", "date": "2026-09-15"},  # 高雄→大阪
]

HEADLESS = False        # Google 對 headless 偵測較嚴，建議 False（看得到瀏覽器較穩）
MAX_TRIES = 8           # 每條航線最多重試幾次（高穩定性的關鍵）
WAIT_MS = 11_000        # 每次載入後等待毫秒
FETCH_BAGGAGE = True    # 是否逐班點詳情抓「行李額度」（較慢：詳情頁也會間歇報錯需重試）
BAGGAGE_TOP = 5         # 每條航線最多抓前幾班的行李（控制時間；其餘行李留空）

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "data", ".gf_profile")   # 持久設定檔（gitignore）
OUTPUT_CSV = os.path.join(HERE, "data", "gflights.csv")
OUTPUT_JSON = os.path.join(HERE, "data", "gflights.json")
LOG_FILE = os.path.join(HERE, "logs", "gflights.log")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
STEALTH_JS = """
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
Object.defineProperty(navigator,'languages',{get:()=>['zh-TW','zh','en']});
Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
window.chrome = window.chrome || { runtime: {} };
"""
結果線索 = ["小時", "直達", "直飛", "NT$", "$"]
錯誤線索 = ["系統發生錯誤", "糟糕", "Something went wrong"]


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


def build_url(route):
    q = (f"Flights from {route['origin']} to {route['dest']} "
         f"on {route['date']} oneway")
    return ("https://www.google.com/travel/flights?"
            + urlencode({"q": q, "curr": "TWD", "hl": "zh-TW", "gl": "TW"}))


def has_results(body):
    """畫面是否真的有航班結果：要有『真實票價($數字)』＋『小時』且無錯誤。
    （只看「小時」會被頁尾「24 小時內的資訊」誤判，故必須要有票價。）"""
    return (bool(re.search(r"\$\s*[\d,]{3,}", body)) and "小時" in body
            and not any(e in body for e in 錯誤線索))


def parse(text, route):
    t = " ".join(text.split())
    m = (re.search(r"\$\s*([\d,]{3,})", t)
         or re.search(r"\b(\d{1,3}(?:,\d{3})+)\b", t))
    price = int(m.group(1).replace(",", "")) if m else None
    if re.search(r"直達|直飛|[Nn]onstop", t):
        transfers = 0
    else:
        ms = (re.search(r"轉機\s*(\d+)\s*次", t) or re.search(r"(\d+)\s*次轉機", t)
              or re.search(r"(\d+)\s*stop", t))
        transfers = int(ms.group(1)) if ms else None
    times = re.findall(r"(?:清晨|上午|下午|中午|凌晨|晚上)?\s?\d{1,2}:\d{2}", t)
    ma = re.search(r"(台灣虎航|星宇航空|長榮航空|中華航空|香港快運航空|德威航空|"
                   r"濟州航空|真航空|釜山航空|韓亞航空|大韓航空|宿霧太平洋|越捷航空|"
                   r"泰國獅子航空|菲律賓航空|樂桃航空|捷星日本航空|捷星|酷航|"
                   r"聯合航空|全日空航空|全日空|日本航空|國泰航空|國泰|亞洲航空|達美)", t)
    return {
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query_date": str(date.today()),
        "origin": route["origin"], "dest": route["dest"], "date": route["date"],
        "price_twd": price,
        "transfers": transfers,                       # 0=直飛
        "depart_time": (times[0].strip() if times else ""),
        "arrive_time": (times[1].strip() if len(times) > 1 else ""),
        "airline": ma.group(1).strip() if ma else "",
        "flight_no": "",    # 後續可擴充（需點進詳情頁）
        "baggage": "",      # 後續可擴充（需點進詳情頁）
    }


def load_with_retry(page, route):
    """重試到結果載出為止；回傳 True/False。這就是『高穩定性』的核心。"""
    url = build_url(route)
    for attempt in range(1, MAX_TRIES + 1):
        log.info("　載入嘗試 %d/%d：%s→%s", attempt, MAX_TRIES,
                 route["origin"], route["dest"])
        page.goto(url, timeout=60_000)
        page.wait_for_timeout(WAIT_MS)
        for label in ["全部接受", "我同意", "接受全部", "Accept all"]:
            try:
                page.get_by_text(label, exact=False).first.click(timeout=1500)
            except Exception:
                pass
        if has_results(page.inner_text("body")):
            return True
        page.wait_for_timeout(2500)
    return False


def parse_baggage(text):
    """從詳情文字抓行李說明（手提/託運）。"""
    found = []
    for line in text.split("\n"):
        s = line.strip()
        if ("手提行李" in s or "託運行李" in s) and 2 < len(s) < 40:
            found.append(s)
    return " / ".join(dict.fromkeys(found))


def click_flight(page, price, depart):
    """在列表找出「票價＋出發時間」相符的航班並點開（回傳是否點到）。"""
    pf = f"${price:,}"   # 含 $，避免 5,699 誤配 15,699
    for li in page.query_selector_all("li"):
        try:
            t = li.inner_text()
        except Exception:
            continue
        if pf in t and depart and depart in t and "小時" in t:
            try:
                li.click(timeout=5000)
                return True
            except Exception:
                return False
    return False


def fetch_baggage(page):
    """在詳情頁抓行李；詳情頁也會間歇報錯，比照列表重試。
    全程防呆：任何步驟出錯都不拋例外（行李是加值，不該中斷主流程）。"""
    for _ in range(5):
        for _ in range(16):
            try:
                page.wait_for_timeout(500)
                d = page.inner_text("body")
            except Exception:
                return ""
            if "手提行李" in d or "託運行李" in d:
                return parse_baggage(d)
            if "系統發生錯誤" in d:
                break
        try:
            page.get_by_text("重新載入", exact=False).first.click(timeout=3000)
        except Exception:
            try:
                page.reload(timeout=60_000)
            except Exception:
                return ""      # reload 失敗（frame detached 等）→ 放棄這班行李
        try:
            page.wait_for_timeout(5000)
        except Exception:
            return ""
    return ""


def extract(page, route):
    # 1) 先從列表抓各航班（去重）
    rows, seen = [], set()
    for li in page.query_selector_all("li"):
        try:
            txt = li.inner_text()
        except Exception:
            continue
        if not (re.search(r"\$\s*[\d,]{3,}", txt) and ("小時" in txt or "分鐘" in txt)):
            continue
        row = parse(txt, route)
        if not row["price_twd"]:
            continue
        key = (row["price_twd"], row["depart_time"])
        if key in seen:
            continue
        seen.add(key); rows.append(row)

    # 2) 逐班點詳情補「行李額度」（前 BAGGAGE_TOP 班，控制時間）
    #    全程防呆：任何一班出錯都只略過該班，絕不中斷整體抓取。
    if FETCH_BAGGAGE:
        for row in rows[:BAGGAGE_TOP]:
            try:
                if click_flight(page, row["price_twd"], row["depart_time"]):
                    row["baggage"] = fetch_baggage(page)
                    try:
                        page.go_back()
                        page.wait_for_timeout(3000)
                    except Exception:
                        pass
                    # 確認回到列表，否則重載
                    try:
                        if not has_results(page.inner_text("body")):
                            load_with_retry(page, route)
                    except Exception:
                        load_with_retry(page, route)
            except Exception as e:
                log.warning("　某班抓行李失敗（略過該班，不影響其餘）：%s", e)
                try:
                    load_with_retry(page, route)   # 嘗試回到可用列表
                except Exception:
                    pass
    return rows


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
    os.makedirs(os.path.dirname(PROFILE), exist_ok=True)
    all_rows = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE, headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-infobars"],
            ignore_default_args=["--enable-automation"],
            user_agent=UA, locale="zh-TW", timezone_id="Asia/Taipei",
            viewport={"width": 1366, "height": 850})
        ctx.add_init_script(STEALTH_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for route in ROUTES:
            if load_with_retry(page, route):
                rows = extract(page, route)
                log.info("　%s→%s：抓到 %d 班", route["origin"], route["dest"],
                         len(rows))
                all_rows.extend(rows)
            else:
                log.warning("　%s→%s：重試 %d 次仍未載出，略過。",
                            route["origin"], route["dest"], MAX_TRIES)
        ctx.close()
    save(all_rows)
    log.info("=== 完成，共 %d 班 ===", len(all_rows))


if __name__ == "__main__":
    main()
