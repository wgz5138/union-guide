#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 拆解【第 5 步】：穩定抓出每張航班並解析（接近完工）。
已突破：stealth 過反爬、結果載得出、資料是文字。
這一步：用「靠內容找卡」(不怕 Google 改 class) + 修正版解析（直達、中文時間）。

跑法：
    python gf_step5_data.py
產出：data/gf_step5.csv 與 .json；畫面印出每張卡與解析結果。
"""

import csv
import json
import os
import re

from playwright.sync_api import sync_playwright

URL = ("https://www.google.com/travel/flights?"
       "q=Flights%20from%20KHH%20to%20NRT%20on%202026-09-15%20oneway"
       "&curr=TWD&hl=zh-TW&gl=TW")
HERE = os.path.dirname(os.path.abspath(__file__))
SHOT = os.path.join(HERE, "data", "gf_step5.png")
OUT_CSV = os.path.join(HERE, "data", "gf_step5.csv")
OUT_JSON = os.path.join(HERE, "data", "gf_step5.json")

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


def parse(text):
    t = " ".join(text.split())
    # 價格：優先抓有 $ 的（避免把 CO2「200 公斤」當價格）
    m = re.search(r"\$\s*([\d,]{3,})", t) or re.search(r"\b(\d{1,3}(?:,\d{3})+)\b", t)
    price = int(m.group(1).replace(",", "")) if m else None
    # 轉機：直達/直飛/nonstop = 0；否則「轉機 N 次」或「N 次轉機」或「N stop」
    if re.search(r"直達|直飛|[Nn]onstop", t):
        transfers = 0
    else:
        ms = (re.search(r"轉機\s*(\d+)\s*次", t)      # 轉機 1 次（數字在後）
              or re.search(r"(\d+)\s*次轉機", t)       # 1 次轉機（數字在前）
              or re.search(r"(\d+)\s*stop", t))
        transfers = int(ms.group(1)) if ms else None
    # 時間：中文制（上午/下午/中午/凌晨/晚上 + h:mm），取前兩個
    times = re.findall(r"(?:清晨|上午|下午|中午|凌晨|晚上)?\s?\d{1,2}:\d{2}", t)
    # 航空（常見台/亞洲航空；長名放前面避免被短名截斷）
    ma = re.search(r"(台灣虎航|星宇航空|長榮航空|中華航空|香港快運航空|德威航空|"
                   r"濟州航空|真航空|釜山航空|韓亞航空|大韓航空|宿霧太平洋|越捷航空|"
                   r"泰國獅子航空|菲律賓航空|樂桃航空|捷星日本航空|捷星|酷航|"
                   r"聯合航空|全日空航空|全日空|日本航空|國泰航空|國泰|亞洲航空|達美)", t)
    return {
        "price_twd": price,
        "transfers": transfers,
        "depart_time": times[0].strip() if times else "",
        "arrive_time": times[1].strip() if len(times) > 1 else "",
        "airline": ma.group(1) if ma else "",
    }


def main():
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-infobars"],
            ignore_default_args=["--enable-automation"])
        ctx = browser.new_context(user_agent=UA, locale="zh-TW",
                                  timezone_id="Asia/Taipei",
                                  viewport={"width": 1366, "height": 850})
        ctx.add_init_script(STEALTH_JS)
        page = ctx.new_page()

        # 載入（stealth 仍可能偶爾錯，重試幾次）
        for attempt in range(1, 5):
            page.goto(URL, timeout=60_000)
            page.wait_for_timeout(9000)
            body = page.inner_text("body")
            if any(k in body for k in 結果線索) and not any(e in body for e in 錯誤線索):
                print(f"✅ 第 {attempt} 次：結果已載出")
                break
            print(f"第 {attempt} 次未見結果，重試…")
        else:
            print("⚠ 仍未載出結果，回報截圖給我。")

        # 靠內容找卡：所有 li，挑「同時有價格 $ 和 小時/分鐘」的
        cards = []
        for li in page.query_selector_all("li"):
            try:
                txt = li.inner_text()
            except Exception:
                continue
            if re.search(r"\$\s*[\d,]{3,}", txt) and ("小時" in txt or "分鐘" in txt):
                cards.append(txt)
        print(f"\n靠內容找到 {len(cards)} 個候選（含重複/展開版，下面會去重）")

        # 解析 + 用「票價＋出發時間」去重（展開詳情版會跟摘要卡同鍵→自動濾掉）
        rows, seen = [], set()
        for txt in cards:
            row = parse(txt)
            if not row["price_twd"]:
                continue
            key = (row["price_twd"], row["depart_time"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            print(f"\n--- 第 {len(rows)} 班 ---\n{' '.join(txt.split())[:150]}")
            print("解析：", row)

        if rows:
            with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader(); w.writerows(rows)
            with open(OUT_JSON, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            print(f"\n✅ 解析出 {len(rows)} 筆 → {OUT_CSV}")

        page.screenshot(path=SHOT, full_page=True)
        print("截圖：", SHOT)
        input("\n看完按 Enter 關閉…")
        browser.close()


if __name__ == "__main__":
    main()
