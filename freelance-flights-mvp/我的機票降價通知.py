#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
我的機票降價通知（個人專用，非交付客主）
================================================
這支是「我自己用」的小工具，不屬於 A2310 交付範圍。
它做兩件客主沒要求、純粹我自己想要的事：
  1) 跑客主版的 gflights_scraper.py 抓機票（票價/轉機/時間/航空/行李）
  2) 抓完比對「上次最低價」，只在『變便宜』時推一則 Telegram 給我（不洗版）

設計重點（與客主版分開、互不干擾）：
  • 客主版 gflights_scraper.py 保持乾淨，完全不含 Telegram / 降價邏輯。
  • 這支用 import 的方式重用它的抓取，再自己加通知。
  • 狀態檔、金鑰都是我私人的，不進客主交付。

用法：
    set TG_TOKEN=...      （或用 setx 永久設定）
    set TG_CHAT=...
    python 我的機票降價通知.py

沒設 TG_TOKEN / TG_CHAT 也能跑，只會印在畫面、不推播。
"""

import json
import os

import requests

import gflights_scraper as gf

log = gf.log   # 沿用客主版的 logger（同一份 log 檔）

# 我私人的「上次最低價」狀態：放 data/，與客主交付、也與 API 版 price_state.json 分開
PRICE_STATE_FILE = os.path.join(gf.HERE, "data", "gflights_price_state.json")


def load_state():
    """讀回各航線『上次最低價』{KHH-NRT: 5699}。檔案不存在/壞掉就回空的。"""
    if not os.path.exists(PRICE_STATE_FILE):
        return {}
    try:
        with open(PRICE_STATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(state):
    try:
        os.makedirs(os.path.dirname(PRICE_STATE_FILE), exist_ok=True)
        with open(PRICE_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except OSError as e:
        log.warning("　價格狀態存檔失敗（不影響抓取）：%s", e)


def tg_send(text):
    """推到 Telegram；TG_TOKEN/TG_CHAT 沒設就只印畫面，不會出錯（防呆）。"""
    token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT")
    if not (token and chat_id):
        log.info("　（未設 TG_TOKEN/TG_CHAT，僅印畫面、不推播）")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        log.info("　已推送到 Telegram。")
    except requests.RequestException as e:
        log.warning("　Telegram 推送失敗（不影響抓取）：%s", e)


def notify_if_cheaper(route, rows, state):
    """找本航線最低價，與上次比；只在『變便宜』時推 Telegram（不洗版）。
    會就地更新 state[航線] = 這次最低價。"""
    priced = [r for r in rows if r.get("price_twd")]
    if not priced:
        return
    best = min(priced, key=lambda r: r["price_twd"])
    key = f"{route['origin']}-{route['dest']}"
    now = best["price_twd"]
    last = state.get(key)

    trans = "直飛" if best["transfers"] == 0 else f"轉機{best['transfers']}次"
    when = best["depart_time"] + (
        "→" + best["arrive_time"] if best["arrive_time"] else "")
    bag = f"\n🧳 {best['baggage']}" if best.get("baggage") else ""
    head = (f"✈️ {route['origin']}→{route['dest']} {route['date']}\n"
            f"最低 NT${now:,}（{best['airline'] or '航空未知'}・{trans}・{when}）")
    link = "\n" + gf.build_url(route)

    if last is None:
        log.info("　[降價] %s 首次記錄基準價 NT$%s（不推播）", key, f"{now:,}")
    elif now < last:
        msg = (f"📉 降價通知！{head}\n"
               f"比上次便宜 {last - now:,} 元（上次 NT${last:,}）{bag}{link}")
        log.info("🔔 %s", msg.replace("\n", " "))
        tg_send(msg)
    else:
        log.info("　[降價] %s 沒變便宜（現 NT$%s／上次 NT$%s），不推播",
                 key, f"{now:,}", f"{last:,}")
    state[key] = now


def main():
    # 1) 跑客主版抓取（會照常存 CSV/JSON），拿回所有航班
    all_rows = gf.main() or []
    # 2) 依航線分組（origin, dest, date），逐航線比價 + 通知
    state = load_state()
    groups = {}
    for r in all_rows:
        groups.setdefault((r["origin"], r["dest"], r["date"]), []).append(r)
    for (origin, dest, d), rows in groups.items():
        notify_if_cheaper({"origin": origin, "dest": dest, "date": d}, rows, state)
    save_state(state)
    log.info("=== 降價通知檢查完成（%d 條航線）===", len(groups))


if __name__ == "__main__":
    main()
