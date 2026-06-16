#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 拆解【第 6 步】：提高穩定性——用「持久化真實設定檔」。
現象：stealth 能進去，但間歇被擋（同一 session 一旦被標記就一直錯）。
這招：用 launch_persistent_context 保留一個瀏覽器設定檔（cookie/同意紀錄會留著），
      像真人重複使用同一個瀏覽器，跨次累積信任，成功率通常大幅提高。
      （第一次可能仍要重試幾次；之後因為有 cookie 會更穩。）

跑法：
    python gf_step6_persist.py
產出：data/gf_step6.csv / .json；設定檔存在 data/.gf_profile（已被 gitignore）。
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
PROFILE = os.path.join(HERE, "data", ".gf_profile")   # 持久設定檔
SHOT = os.path.join(HERE, "data", "gf_step6.png")
OUT_CSV = os.path.join(HERE, "data", "gf_step6.csv")
OUT_JSON = os.path.join(HERE, "data", "gf_step6.json")

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
    m = re.search(r"\$\s*([\d,]{3,})", t) or re.search(r"\b(\d{1,3}(?:,\d{3})+)\b", t)
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
    return {"price_twd": price, "transfers": transfers,
            "depart_time": times[0].strip() if times else "",
            "arrive_time": times[1].strip() if len(times) > 1 else "",
            "airline": ma.group(1) if ma else ""}


def main():
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE, headless=False,
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-infobars"],
            ignore_default_args=["--enable-automation"],
            user_agent=UA, locale="zh-TW", timezone_id="Asia/Taipei",
            viewport={"width": 1366, "height": 850})
        ctx.add_init_script(STEALTH_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        ok = False
        for attempt in range(1, 8):           # 多試幾次
            print(f"第 {attempt} 次：前往…")
            page.goto(URL, timeout=60_000)
            page.wait_for_timeout(11000)       # 等久一點
            # 第一次可能跳同意視窗，按掉
            for label in ["全部接受", "我同意", "接受全部", "Accept all"]:
                try:
                    page.get_by_text(label, exact=False).first.click(timeout=2000)
                except Exception:
                    pass
            body = page.inner_text("body")
            if any(k in body for k in 結果線索) and not any(e in body for e in 錯誤線索):
                print(f"✅ 第 {attempt} 次：結果載出！")
                ok = True
                break
            page.wait_for_timeout(3000)

        if ok:
            cards = []
            for li in page.query_selector_all("li"):
                try:
                    txt = li.inner_text()
                except Exception:
                    continue
                if re.search(r"\$\s*[\d,]{3,}", txt) and ("小時" in txt or "分鐘" in txt):
                    cards.append(txt)
            rows, seen = [], set()
            for txt in cards:
                row = parse(txt)
                if not row["price_twd"]:
                    continue
                key = (row["price_twd"], row["depart_time"])
                if key in seen:
                    continue
                seen.add(key); rows.append(row)
                print(f"--- 第 {len(rows)} 班 ---", row)
            if rows:
                with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    w.writeheader(); w.writerows(rows)
                with open(OUT_JSON, "w", encoding="utf-8") as f:
                    json.dump(rows, f, ensure_ascii=False, indent=2)
                print(f"\n✅ 解析出 {len(rows)} 筆 → {OUT_CSV}")
        else:
            print("⚠ 多次仍未載出（可再跑一次，持久設定檔會越跑越穩）。")

        page.screenshot(path=SHOT, full_page=True)
        print("截圖：", SHOT)
        input("\n看完按 Enter 關閉…")
        ctx.close()


if __name__ == "__main__":
    main()
