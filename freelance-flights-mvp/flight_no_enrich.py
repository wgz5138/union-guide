#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""航班號增益（enrichment）
=================================================
Google Flights 介面不穩定提供航班號，本模組用「航空公司 + 航線 + 起飛時間」
對照 Amadeus 班表，把航班號補進抓到的資料；並把對照寫進 data/flight_no_map.csv，
之後就算沒有 API（額度用完／免費版關閉）也能靠這張表補。

設計：抓取（Google）與補號（班表）分開，互不影響穩定度。
  • 有設 AMADEUS_API_KEY / AMADEUS_API_SECRET → 自動向 Amadeus 查、更新對照表。
  • 沒設金鑰 → 只用既有對照表補；補不到就留空（絕不影響其他欄位）。

注意：僅補「直飛」航班的航班號（轉機航班有多段、不只一個航班號，留空較誠實）。
"""
import csv
import os
import re

try:
    import requests
except Exception:                       # 沒裝 requests 也不要讓 import 失敗
    requests = None

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_FILE = os.path.join(HERE, "data", "flight_no_map.csv")
# 與 amadeus_flights.py 一致用測試環境；要上正式資料改成 https://api.amadeus.com 並換正式金鑰
AMADEUS_BASE = "https://test.api.amadeus.com"

# 航空中文名 → IATA 代碼（本模組自帶一份，保持可獨立運作、不依賴爬蟲模組）
NAME_IATA = {
    "台灣虎航": "IT", "星宇航空": "JX", "長榮航空": "BR", "中華航空": "CI",
    "香港快運航空": "UO", "德威航空": "TW", "濟州航空": "7C", "真航空": "LJ",
    "釜山航空": "BX", "韓亞航空": "OZ", "大韓航空": "KE", "宿霧太平洋": "5J",
    "越捷航空": "VJ", "泰國獅子航空": "SL", "菲律賓航空": "PR", "樂桃航空": "MM",
    "捷星日本航空": "GK", "捷星": "GK", "酷航": "TR", "聯合航空": "UA",
    "全日空航空": "NH", "全日空": "NH", "日本航空": "JL", "國泰航空": "CX",
    "國泰": "CX", "亞洲航空": "AK", "達美": "DL",
}


def norm_time(s):
    """中文時段 → 24 小時 HH:MM。例：下午2:00→14:00、中午12:55→12:55、清晨7:00→07:00。"""
    s = s or ""
    m = re.search(r"(\d{1,2}):(\d{2})", s)
    if not m:
        return ""
    h, mi = int(m.group(1)), m.group(2)
    if ("下午" in s or "晚上" in s) and h != 12:
        h += 12
    elif "中午" in s:
        h = 12
    elif ("凌晨" in s or "上午" in s or "清晨" in s) and h == 12:
        h = 0
    return f"{h:02d}:{mi}"


def load_map():
    m = {}
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    m[(r["origin"], r["dest"], r["carrier"], r["hhmm"])] = r["flight_no"]
        except Exception:
            pass
    return m


def save_map(m):
    try:
        os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
        with open(MAP_FILE, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["origin", "dest", "carrier", "hhmm", "flight_no"])
            for (o, d, c, t), fn in sorted(m.items()):
                w.writerow([o, d, c, t, fn])
    except OSError:
        pass


def _amadeus_token():
    key = os.environ.get("AMADEUS_API_KEY", "")
    sec = os.environ.get("AMADEUS_API_SECRET", "")
    if not (key and sec and requests):
        return ""
    try:
        r = requests.post(
            f"{AMADEUS_BASE}/v1/security/oauth2/token",
            data={"grant_type": "client_credentials",
                  "client_id": key, "client_secret": sec},
            timeout=20)
        r.raise_for_status()
        return r.json().get("access_token", "")
    except Exception:
        return ""


def _amadeus_flights(origin, dest, date, token):
    """查 Amadeus 直飛班次，回傳 [(carrier, hhmm, flight_no), ...]；失敗回空。"""
    if not (token and requests):
        return []
    out = []
    try:
        r = requests.get(
            f"{AMADEUS_BASE}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params={"originLocationCode": origin, "destinationLocationCode": dest,
                    "departureDate": date, "adults": 1, "nonStop": "true", "max": 50},
            timeout=30)
        r.raise_for_status()
        for off in r.json().get("data", []):
            seg = off["itineraries"][0]["segments"][0]
            carrier = seg.get("carrierCode", "")
            num = seg.get("number", "")
            mt = re.search(r"T(\d{2}:\d{2})", seg.get("departure", {}).get("at", ""))
            if carrier and num and mt:
                out.append((carrier, mt.group(1), f"{carrier}{num}"))
    except Exception:
        return out
    return out


def enrich(rows, log=None):
    """把 rows 的 flight_no 補上（直飛班）。先用對照表，金鑰有設則順便用 Amadeus 更新表。
    回傳補上的筆數。全程防呆：任何錯誤都不影響 rows 其他欄位。"""
    if not rows:
        return 0
    m = load_map()
    token = _amadeus_token()
    if token:
        for (o, d, date) in {(r["origin"], r["dest"], r["date"]) for r in rows}:
            for carrier, hhmm, fn in _amadeus_flights(o, d, date, token):
                m[(o, d, carrier, hhmm)] = fn
    filled = 0
    for r in rows:
        if r.get("flight_no"):                 # Google 偶爾自己抓到就尊重，不覆蓋
            continue
        if r.get("transfers") not in (0, "0"):  # 只補直飛（轉機有多段航班號，留空較誠實）
            continue
        carrier = NAME_IATA.get(r.get("airline", ""), "")
        hhmm = norm_time(r.get("depart_time", ""))
        fn = m.get((r.get("origin"), r.get("dest"), carrier, hhmm), "")
        if fn:
            r["flight_no"] = fn
            filled += 1
    save_map(m)
    if log:
        log.info("　[航班號] 增益：本批補上 %d 筆（對照表共 %d 筆%s）",
                 filled, len(m), "；含 Amadeus 更新" if token else "；未用 API")
    return filled
