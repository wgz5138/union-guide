#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雙向 Telegram 機票 bot：在 Telegram 直接傳訊息給 bot，它就回你最便宜的票。

用法：
  1. 確認環境變數 TRAVELPAYOUTS_TOKEN、TG_TOKEN 已設好。
     （建議也設 TG_CHAT：設了就「只回應你本人」，別人傳訊不理，省你的額度。）
  2. 點兩下『啟動聊天機器人.bat』，或執行：python telegram_bot.py
  3. 程式會一直開著等你。這段時間在 Telegram 對 bot 打：
        查 高雄 東京 2026-09            （單程）
        查 高雄 東京 2026-09 2026-10     （來回：多給一個回程月份）
     它就回你最便宜的票＋繁體中文訂票連結。
  4. 要停止：在視窗按 Ctrl + C。

注意：bot 要「一直開著」才能即時回應，所以這支適合電腦開著時跑
（不像每日查價可以丟雲端；雙向聊天需要一直在線）。
"""

import os
import re
import time

import requests

import travelpayouts_flights as tp

TOKEN = os.environ.get("TG_TOKEN")
OWNER = os.environ.get("TG_CHAT")          # 設了就只回應本人
API = f"https://api.telegram.org/bot{TOKEN}"

說明 = (
    "✈️ 機票查詢小幫手\n"
    "傳給我：出發 目的地 去程月份 [回程月份]\n"
    "例：\n"
    "　查 高雄 東京 2026-09　（單程）\n"
    "　查 高雄 東京 2026-09 2026-10　（來回）\n"
    "地名可打中文（高雄、日本、首爾…）或英文代碼。"
)


def send(chat_id, text):
    try:
        requests.post(f"{API}/sendMessage",
                      data={"chat_id": chat_id, "text": text}, timeout=15)
    except requests.RequestException as e:
        print("送出失敗：", e)


def handle(text):
    """把使用者訊息變成查詢，回傳要回覆的字串。
    很寬鬆：有沒有空格、有沒有逗號、有沒有「查」都看得懂。
    例：『查 高雄 東京 2026-09』『查高雄福岡，2026-09』都行。"""
    # 1) 先抓出月份（一個=單程；兩個=來回）
    months = re.findall(r"\d{4}-\d{2}", text)
    # 2) 把「查」、月份、各種標點都換成空白，剩下的拿來找地名
    rest = text.replace("查", " ")
    for m in months:
        rest = rest.replace(m, " ")
    for ch in "，,、。；;／/ 　":
        rest = rest.replace(ch, " ")
    # 3) 先用「地名對照表」在字串裡找中文地名（依出現順序）
    hits = sorted((rest.find(n), n) for n in tp.地名對照表 if n in rest)
    places = [n for _, n in hits]
    # 4) 找不到足夠中文地名，就退回用空白切詞（支援英文代碼）
    if len(places) < 2:
        places = [w for w in rest.split() if w]

    if len(places) < 2 or len(months) < 1:
        return "看不太懂耶 😅\n\n" + 說明

    origin, dest, month = places[0], places[1], months[0]

    # 如果地名是「中文但不在對照表」，API 會看不懂 → 先友善提醒，別吐錯誤
    未知 = [p for p in (origin, dest)
            if p not in tp.地名對照表 and any(ord(c) > 127 for c in p)]
    if 未知:
        return (f"我不認得「{'、'.join(未知)}」😅\n"
                "請改用機場代碼（例：重慶 CKG、成都 CTU），或用清單上的中文地名：\n"
                + "、".join(tp.地名對照表))

    route = {"origin": origin, "dest": dest, "month": month}
    if len(months) >= 2:
        route["return"] = months[1]

    row = tp.search_cheapest(route)
    if not row:
        return f"「{origin}→{dest} {month}」最近查無票價，換個月份或目的地試試。"

    when = row["depart_at"]
    if row["trip"] == "來回" and row["return_at"]:
        when += f" 去 / {row['return_at']} 回"
    return (f"✈️ {row['route']}（{row['trip']}）{when}\n"
            f"最低 {row['price']:.0f} {row['currency']}"
            f"（{row['airline']}，轉機 {row['transfers']} 次）\n{row['link']}")


def main():
    if not TOKEN:
        print("❌ 還沒設 TG_TOKEN。請先設定環境變數再跑。")
        return
    print("🤖 機票 bot 啟動，去 Telegram 傳訊息給它吧～（這個視窗按 Ctrl+C 可停止）")
    offset = None
    while True:
        try:
            r = requests.get(f"{API}/getUpdates",
                             params={"timeout": 30, "offset": offset}, timeout=40)
            updates = r.json().get("result", [])
        except requests.RequestException as e:
            print("連線問題，5 秒後重試：", e)
            time.sleep(5)
            continue

        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            text = (msg.get("text") or "").strip()
            if not chat_id or not text:
                continue
            if OWNER and str(chat_id) != str(OWNER):
                continue  # 只回應本人
            if text in ("/start", "help", "說明", "?", "？"):
                send(chat_id, 說明)
                continue
            print("收到：", text)
            try:
                reply = handle(text)
            except Exception as e:
                reply = f"查詢出錯：{e}"
            send(chat_id, reply)


if __name__ == "__main__":
    main()
