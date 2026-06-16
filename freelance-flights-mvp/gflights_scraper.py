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
import random
import re
from datetime import date, datetime
from logging.handlers import RotatingFileHandler

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
# 禮貌間隔（毫秒，隨機區間）：班與班之間稍等再點，降低「系統發生錯誤」頻率、較不像機器人、較耐封。
POLITE_WAIT_MS = (1500, 3500)
SETTLE_MS = 1800        # 點開詳情後先給頁面這麼久 settle，再開始判斷，避免把載入瞬間誤當錯誤

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
    from urllib.parse import urlencode
    return ("https://www.google.com/travel/flights?"
            + urlencode({"q": q, "curr": "TWD", "hl": "zh-TW", "gl": "TW"}))


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
    raw_times = re.findall(r"(?:清晨|上午|下午|中午|凌晨|晚上)?\s?\d{1,2}:\d{2}", t)
    # 取前兩個「不同」的時間當出發/抵達，避免同一個時間被重複抓成出發=抵達
    times = []
    for x in raw_times:
        xs = x.strip()
        if xs not in times:
            times.append(xs)
    # 跨日：抵達時間後常接「+1」表示隔天到（轉機/紅眼班機）。
    # 抓出來補在 arrive_time 後面，避免「抵達比出發早」被誤判成資料錯誤。
    arrive_suffix = ""
    if len(times) > 1:
        mp = re.search(re.escape(times[1]) + r"\s*\+\s*(\d)", t)
        if mp:
            arrive_suffix = "+" + mp.group(1)
    ma = re.search(r"(台灣虎航|星宇航空|長榮航空|中華航空|香港快運航空|德威航空|"
                   r"濟州航空|真航空|釜山航空|韓亞航空|大韓航空|宿霧太平洋|越捷航空|"
                   r"泰國獅子航空|菲律賓航空|樂桃航空|捷星日本航空|捷星|酷航|"
                   r"聯合航空|全日空航空|全日空|日本航空|國泰航空|國泰|亞洲航空|達美)", t)
    if ma:
        airline = ma.group(1).strip()
    else:
        # 後備：清單沒列到的航空，抓任何「⋯航空」字樣（避免直接空白）
        mg = re.search(r"([一-龥]{2,10}航空)", t)
        airline = mg.group(1).strip() if mg else ""
    return {
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query_date": str(date.today()),
        "origin": route["origin"], "dest": route["dest"], "date": route["date"],
        "price_twd": price,
        "transfers": transfers,                       # 0=直飛
        "depart_time": (times[0].strip() if times else ""),
        "arrive_time": (times[1] + arrive_suffix if len(times) > 1 else ""),
        "airline": airline,
        "flight_no": "",    # 後續可擴充（需點進詳情頁）
        "baggage": "",      # 後續可擴充（需點進詳情頁）
    }


def page_loaded_ok(body):
    """較嚴格的『結果頁已真的載出』判斷。
    舊版只要頁面含 `$`（任何頁面幾乎都有）就算成功，容易『還沒載完就誤判』。
    改為：要『同時看到價格＋"小時"（航程時長）』、且沒有錯誤字樣，才算真的載出。"""
    has_price = bool(re.search(r"\$\s*[\d,]{3,}", body))
    has_time = "小時" in body
    has_error = any(e in body for e in 錯誤線索)
    return has_price and has_time and not has_error


def load_with_retry(page, route):
    """重試到結果載出為止；回傳 True/False。這就是『高穩定性』的核心。
    重點：連線逾時／載入丟例外，都當成『這次失敗』繼續重試，
    絕不讓單次例外往外炸掉整條航線或整個程式。"""
    url = build_url(route)
    for attempt in range(1, MAX_TRIES + 1):
        log.info("　載入嘗試 %d/%d：%s→%s", attempt, MAX_TRIES,
                 route["origin"], route["dest"])
        try:
            page.goto(url, timeout=60_000)
            page.wait_for_timeout(WAIT_MS)
            for label in ["全部接受", "我同意", "接受全部", "Accept all"]:
                try:
                    page.get_by_text(label, exact=False).first.click(timeout=1500)
                except Exception:
                    pass
            body = page.inner_text("body")
        except Exception as e:
            # goto 逾時、frame detached 等：記下來，等一下再重試（不中斷）
            log.warning("　　第 %d 次載入出錯，稍候重試：%s", attempt, e)
            try:
                page.wait_for_timeout(2500)
            except Exception:
                pass
            continue
        if page_loaded_ok(body):
            return True
        page.wait_for_timeout(2500)
    return False


def parse_baggage(text):
    """從詳情文字抓行李說明（手提/託運）。"""
    found = []
    for line in text.split("\n"):
        s = line.strip()
        # 清掉中文字之間被 DOM 換行塞進來的空格（例：「託 運」→「託運」）
        s = re.sub(r"(?<=[一-鿿])\s+(?=[一-鿿])", "", s)
        if ("手提行李" in s or "託運行李" in s) and 2 < len(s) < 40:
            found.append(s)
    return " / ".join(dict.fromkeys(found))


# 航空中文名 → IATA 代碼：用來在詳情頁「精準」找航班號，降低誤抓
AIRLINE_IATA = {
    "台灣虎航": "IT", "星宇航空": "JX", "長榮航空": "BR", "中華航空": "CI",
    "香港快運航空": "UO", "德威航空": "TW", "濟州航空": "7C", "真航空": "LJ",
    "釜山航空": "BX", "韓亞航空": "OZ", "大韓航空": "KE", "宿霧太平洋": "5J",
    "越捷航空": "VJ", "泰國獅子航空": "SL", "菲律賓航空": "PR", "樂桃航空": "MM",
    "捷星日本航空": "GK", "捷星": "GK", "酷航": "TR", "聯合航空": "UA",
    "全日空航空": "NH", "全日空": "NH", "日本航空": "JL", "國泰航空": "CX",
    "國泰": "CX", "亞洲航空": "AK", "達美": "DL",
}


def parse_flight_no(text, airline=""):
    """從詳情頁文字找航班號。
    先用『這班航空的 IATA 代碼＋數字』精準找（例 BR132 / CI 100）；
    找不到再用通用樣式列出候選，方便診斷 Google 詳情頁到底有沒有放航班號。
    回傳 (航班號, 候選清單)。"""
    t = " ".join(text.split())
    code = AIRLINE_IATA.get(airline, "")
    if code:
        m = re.search(r"\b" + re.escape(code) + r"\s?(\d{1,4})\b", t)
        if m:
            return f"{code}{m.group(1)}", []
    # 通用候選：2 碼代碼 + 1~4 位數（純診斷用，可能有雜訊）
    cands = re.findall(r"\b([A-Z0-9]{2}\s?\d{1,4})\b", t)
    cands = list(dict.fromkeys(c.replace(" ", "") for c in cands))
    return "", cands


def click_flight(page, price, depart):
    """在列表找出「票價＋出發時間」相符的航班並點開。
    回傳 'ok'（點到）/ 'click_fail'（找到卡但點不開）/ 'no_match'（找不到對應卡）。
    Google 列表是虛擬捲動/lazy-load，下方卡片可能還沒在 DOM →
    找不到時往下捲、邊捲邊找，把卡片逼出來再點（最多幾輪）。"""
    pf = f"{price:,}"
    # 先回到列表頂端，從頭往下找，避免從半路開始漏掉上面的卡
    try:
        page.mouse.wheel(0, -4000)
        page.wait_for_timeout(400)
    except Exception:
        pass
    for attempt in range(7):
        for li in page.query_selector_all("li"):
            try:
                t = li.inner_text()
            except Exception:
                continue
            if pf in t and depart and depart in t and "小時" in t:
                try:
                    human_click(page, li)   # 擬真點擊（hover＋滑鼠軌跡＋微停）
                    return "ok"
                except Exception as e:
                    log.info("　　[行李] 找到卡但點不開（價%s 出發%s）：%s",
                             pf, depart, e)
                    return "click_fail"
        # 這一屏沒有 → 往下捲一段，讓更下面的卡片載出來再找
        try:
            page.mouse.wheel(0, random.randint(600, 1000))
            page.wait_for_timeout(random.randint(500, 900))
        except Exception:
            break
    log.info("　　[行李] 列表找不到對應航班卡（價%s 出發%s）", pf, depart)
    return "no_match"


def polite_wait(page):
    """班與班之間的隨機禮貌間隔：降低觸發 Google 間歇錯誤、較不像機器人、較耐封。"""
    try:
        page.wait_for_timeout(random.randint(*POLITE_WAIT_MS))
    except Exception:
        pass


def human_click(page, element):
    """像真人那樣點：捲到看得到 → 滑鼠帶軌跡移過去 → hover → 微停 → 才點。
    全程防呆，任何一步失敗都不影響最終的 click。"""
    try:
        element.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    try:
        box = element.bounding_box()
        if box:
            # 落點在卡片內偏中間、帶隨機；滑鼠分段移動（有軌跡，不瞬移）
            tx = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            page.mouse.move(tx, ty, steps=random.randint(8, 20))
    except Exception:
        pass
    try:
        element.hover(timeout=3000)
    except Exception:
        pass
    try:
        page.wait_for_timeout(random.randint(250, 700))
    except Exception:
        pass
    element.click(timeout=5000)


def human_scroll(page):
    """像人邊看邊往下滑：分幾段捲、每段隨機停一下，順便讓 lazy-load 卡片長出來。"""
    for _ in range(random.randint(3, 6)):
        try:
            page.mouse.wheel(0, random.randint(500, 1100))
            page.wait_for_timeout(random.randint(400, 1100))
        except Exception:
            break
    # 偶爾往回捲一點，更像人在重看
    try:
        if random.random() < 0.4:
            page.mouse.wheel(0, -random.randint(200, 500))
            page.wait_for_timeout(random.randint(300, 700))
    except Exception:
        pass


def fetch_detail_text(page):
    """讀詳情頁全文（行李、航班號都從這份文字解析）。詳情頁間歇報錯會自動重載。
    全程防呆：任何步驟出錯都回 ''（加值資料不該中斷主流程）。
    成功回傳詳情頁文字；失敗回 ''，並記 log 方便診斷。"""
    # 先給詳情頁一點時間 settle，避免把「正在載入的瞬間」誤判成錯誤就急著重載
    try:
        page.wait_for_timeout(SETTLE_MS)
    except Exception:
        pass
    for outer in range(5):
        got_error = False
        for _ in range(16):
            try:
                page.wait_for_timeout(500)
                d = page.inner_text("body")
            except Exception as e:
                log.info("　　[詳情] 讀詳情頁出錯放棄：%s", e)
                return ""
            if "手提行李" in d or "託運行李" in d:
                return d
            if "系統發生錯誤" in d:
                got_error = True
                break
        if got_error:
            log.info("　　[詳情] 詳情頁出現『系統發生錯誤』，第 %d 次重載", outer + 1)
        else:
            log.info("　　[詳情] 等約 8 秒仍沒出現行李字樣（第 %d 輪）", outer + 1)
        try:
            page.get_by_text("重新載入", exact=False).first.click(timeout=3000)
        except Exception:
            try:
                page.reload(timeout=60_000)
            except Exception as e:
                log.info("　　[詳情] 重載失敗放棄（frame detached 等）：%s", e)
                return ""      # reload 失敗 → 放棄這班
        try:
            page.wait_for_timeout(random.randint(4000, 7000))  # 重載後等待加抖動
        except Exception:
            return ""
    log.info("　　[詳情] 重試 5 輪仍讀不到，放棄這班")
    return ""


def extract(page, route):
    # 1) 先像人一樣邊看邊往下捲（順便讓 lazy-load 卡片長出來），再抓各航班（去重）
    human_scroll(page)
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
        log.info("　[行李] 開始逐班抓（前 %d 班）", min(BAGGAGE_TOP, len(rows)))
        for idx, row in enumerate(rows[:BAGGAGE_TOP], 1):
            try:
                polite_wait(page)   # 點下一班前先禮貌等一下（隨機）
                status = click_flight(page, row["price_twd"], row["depart_time"])
                if status == "ok":
                    dtext = fetch_detail_text(page)
                    row["baggage"] = parse_baggage(dtext) if dtext else ""
                    log.info("　[行李] 第 %d 班 %s：%s", idx,
                             row["airline"] or "(未知航空)",
                             row["baggage"] or "（沒抓到）")
                    # ① 航班號探測：從同一份詳情文字找，有就填、沒有就記候選供診斷
                    fno, cands = (parse_flight_no(dtext, row["airline"])
                                  if dtext else ("", []))
                    row["flight_no"] = fno
                    if fno:
                        log.info("　[航班號] 第 %d 班 %s → %s", idx,
                                 row["airline"] or "(未知)", fno)
                    else:
                        log.info("　[航班號] 第 %d 班 %s：詳情頁找不到（通用候選：%s）",
                                 idx, row["airline"] or "(未知)",
                                 "、".join(cands[:6]) or "無")
                    try:
                        page.go_back()
                        page.wait_for_timeout(3000)
                    except Exception:
                        pass
                    # 確認回到列表，否則重載
                    try:
                        if not any(k in page.inner_text("body") for k in 結果線索):
                            load_with_retry(page, route)
                    except Exception:
                        load_with_retry(page, route)
                else:
                    log.info("　[行李] 第 %d 班略過（%s）", idx, status)
            except Exception as e:
                log.warning("　某班抓行李失敗（略過該班，不影響其餘）：%s", e)
                try:
                    load_with_retry(page, route)   # 嘗試回到可用列表
                except Exception:
                    pass
    return rows


def save(rows):
    """累積儲存：CSV、JSON 行為一致，都『往後累加』。
    （舊版 CSV 是 append、JSON 卻是覆蓋，只留最後一批 → 已修正。）"""
    if not rows:
        log.info("沒有資料可存。")
        return
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    fields = list(rows[0].keys())
    # CSV：append（檔案不存在時才寫表頭）
    new = not os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)
    # JSON：先讀回舊資料，併上新資料再整檔寫回（壞檔/不存在都當空清單）
    existing = []
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    existing.extend(rows)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    log.info("已存 %d 筆（累計 %d 筆）→ %s（與 .json）",
             len(rows), len(existing), OUTPUT_CSV)


def main():
    log.info("=== Google Flights 抓取開始（%d 條航線）===", len(ROUTES))
    os.makedirs(os.path.dirname(PROFILE), exist_ok=True)
    total = 0
    all_rows = []   # 收集所有航班，供呼叫端（例如個人通知腳本）取用
    with sync_playwright() as p:
        # 啟動參數共用；優先用「你電腦真的 Chrome」(channel="chrome")，
        # 它的指紋(WebGL/字型/codec)就是真瀏覽器，比內建 Chromium 不易被偵測。
        launch_kw = dict(
            user_data_dir=PROFILE, headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-infobars"],
            ignore_default_args=["--enable-automation"],
            user_agent=UA, locale="zh-TW", timezone_id="Asia/Taipei",
            viewport={"width": 1366, "height": 850})
        try:
            ctx = p.chromium.launch_persistent_context(channel="chrome", **launch_kw)
            log.info("　使用真 Chrome（channel=chrome）")
        except Exception as e:
            # 沒裝 Chrome / 抓不到 → 自動退回內建 Chromium，不讓程式掛掉
            log.warning("　找不到真 Chrome，退回內建 Chromium：%s", e)
            ctx = p.chromium.launch_persistent_context(**launch_kw)
        ctx.add_init_script(STEALTH_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for route in ROUTES:
            # 每條航線各自包起來：單一航線出任何錯都只略過它，不波及其他航線
            try:
                if load_with_retry(page, route):
                    rows = extract(page, route)
                    log.info("　%s→%s：抓到 %d 班", route["origin"],
                             route["dest"], len(rows))
                    save(rows)            # ★ 抓完一條就先存，中途崩潰也不丟已抓到的
                    total += len(rows)
                    all_rows.extend(rows)
                else:
                    log.warning("　%s→%s：重試 %d 次仍未載出，略過。",
                                route["origin"], route["dest"], MAX_TRIES)
            except Exception as e:
                log.warning("　%s→%s：發生未預期錯誤，略過此航線：%s",
                            route["origin"], route["dest"], e)
        ctx.close()
    log.info("=== 完成，本次共 %d 班 ===", total)
    return all_rows


if __name__ == "__main__":
    main()
