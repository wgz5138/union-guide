#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Flights 拆解【第 3 步】：把航班資料「抓出來」。
已知：頁面打得開、結果載得出（有時要重試）、資料是文字在 HTML 裡。
這一步要解：找出每張航班卡 → 印出內容 → 解析票價/轉機/時間/航空。

內建 reload 重試（對付間歇性「系統發生錯誤」）。

跑法：
    python gf_step3_extract.py

跑完看 data/gf_step3.png，並把畫面印出的「找到幾張卡 + 前幾張的文字 + 解析結果」回報給我。
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
SHOT = os.path.join(HERE, "data", "gf_step3.png")
OUT_CSV = os.path.join(HERE, "data", "gf_step3.csv")
OUT_JSON = os.path.join(HERE, "data", "gf_step3.json")

結果線索 = ["小時", "直飛", "NT$", "轉機", "Nonstop"]
錯誤線索 = ["系統發生錯誤", "糟糕", "Something went wrong"]
# 候選的「航班卡」選擇器（Google 的 class 會變，多備幾個輪流試）
卡片選擇器 = ["li.pIav2d", "ul.Rk10dc li", "[role='list'] [role='listitem']",
              "div.pIav2d"]


def 有結果(body):
    return any(k in body for k in 結果線索) and not any(e in body for e in 錯誤線索)


def parse(text):
    """從一張卡的文字解析欄位。"""
    m = re.search(r"(?:NT\$|＄|\$)?\s*([\d,]{3,})", text)
    price = int(m.group(1).replace(",", "")) if m else None
    if re.search(r"直飛|[Nn]onstop", text):
        transfers = 0
    else:
        ms = re.search(r"(\d+)\s*(?:次轉機|stop)", text)
        transfers = int(ms.group(1)) if ms else None
    times = re.findall(r"\d{1,2}:\d{2}", text)
    ma = re.search(r"(亞洲航空|台灣虎航|長榮|中華航空|星宇|樂桃|捷星|國泰|"
                   r"日本航空|全日空|大韓航空|酷航)", text)
    return {
        "price_twd": price,
        "transfers": transfers,
        "depart_time": times[0] if times else "",
        "arrive_time": times[1] if len(times) > 1 else "",
        "airline": ma.group(1) if ma else "",
    }


def main():
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_context(locale="zh-TW").new_page()
        page.goto(URL, timeout=60_000)
        page.wait_for_timeout(5000)

        # 等結果（間歇錯誤就按重新載入）
        for attempt in range(1, 6):
            body = page.inner_text("body")
            if 有結果(body):
                print(f"✅ 第 {attempt} 次：結果已載出")
                break
            if any(e in body for e in 錯誤線索):
                print(f"第 {attempt} 次：系統發生錯誤 → 重新載入…")
                try:
                    page.get_by_text("重新載入", exact=False).first.click(timeout=5000)
                except Exception:
                    page.reload(timeout=60_000)
            page.wait_for_timeout(7000)

        # 找航班卡：哪個選擇器抓到最多就用哪個
        best_sel, best_items = None, []
        for sel in 卡片選擇器:
            try:
                items = page.query_selector_all(sel)
            except Exception:
                items = []
            print(f"選擇器 '{sel}' → 找到 {len(items)} 個")
            if len(items) > len(best_items):
                best_sel, best_items = sel, items

        print(f"\n採用：'{best_sel}'，共 {len(best_items)} 張卡")
        rows = []
        for i, it in enumerate(best_items[:8], 1):   # 先看前 8 張
            txt = " ".join(it.inner_text().split())
            print(f"\n--- 第 {i} 張卡原始文字 ---\n{txt[:200]}")
            row = parse(txt)
            print("解析：", row)
            if row["price_twd"]:
                rows.append(row)

        # 存檔
        if rows:
            with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader(); w.writerows(rows)
            with open(OUT_JSON, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            print(f"\n✅ 解析出 {len(rows)} 筆 → {OUT_CSV}")

        page.screenshot(path=SHOT, full_page=True)
        print(f"截圖：{SHOT}")
        input("\n看完按 Enter 關閉…")
        browser.close()


if __name__ == "__main__":
    main()
