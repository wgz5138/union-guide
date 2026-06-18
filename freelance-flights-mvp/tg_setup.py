#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小工具：找出你的 Telegram chat id（給新手用，免得自己讀一堆 JSON）

用法：
  1. 先在 Telegram 用 @BotFather 建好 bot，拿到 bot token
  2. 把 token 設成環境變數：
        Windows(PowerShell)：  $env:TG_TOKEN="你的bot token"
        Mac/Linux：            export TG_TOKEN="你的bot token"
  3. ★重要★ 打開 Telegram，搜尋你剛建的 bot，按「開始 / Start」並隨便傳一句話給它
  4. 執行：python tg_setup.py
  5. 它會印出你的 chat id。把它設成環境變數 TG_CHAT，就完成了。
"""

import os
import sys

import requests

token = os.environ.get("TG_TOKEN")
if not token:
    print("❌ 還沒設 TG_TOKEN。請先設定環境變數 TG_TOKEN=你的bot token。")
    sys.exit(1)

try:
    resp = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
    resp.raise_for_status()
    data = resp.json()
except requests.RequestException as e:
    print(f"❌ 連不上 Telegram：{e}")
    sys.exit(1)

if not data.get("ok"):
    print(f"❌ Telegram 回報錯誤（token 可能打錯了）：{data}")
    sys.exit(1)

updates = data.get("result", [])
if not updates:
    print("⚠ 還沒收到任何訊息。")
    print("　請先到 Telegram 搜尋你的 bot，按「Start」並傳一句話給它，再跑一次本程式。")
    sys.exit(0)

# 從最新的訊息裡找出 chat id（去重）
chat_ids = {}
for u in updates:
    msg = u.get("message") or u.get("channel_post") or {}
    chat = msg.get("chat") or {}
    if "id" in chat:
        name = chat.get("first_name") or chat.get("title") or ""
        chat_ids[chat["id"]] = name

print("✅ 找到你的 chat id：")
for cid, name in chat_ids.items():
    print(f"    {cid}    （{name}）")
print()
print("下一步：把它設成環境變數，例如：")
first = next(iter(chat_ids))
print(f'    Windows：  $env:TG_CHAT="{first}"')
print(f'    Mac/Linux：export TG_CHAT="{first}"')
print("設好後跑 travelpayouts_flights.py，撿到便宜票就會推到你手機了。")
