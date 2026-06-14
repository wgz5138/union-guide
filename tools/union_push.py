# -*- coding: utf-8 -*-
"""
工會金句自動推播：每 4 小時對 LINE 群組推一句金句，過了截止時間自動停。
沿用 LINE Messaging API push（同「印藥水小幫手」那套）。
金鑰與群組ID 走環境變數（GitHub Secrets），不進 git。
"""
import os, json, datetime, urllib.request, urllib.error

TOKEN = os.environ.get("LINE_TOKEN", "").strip()
GROUP = os.environ.get("LINE_GROUP_ID", "").strip()

URL       = "https://singular-paprenjak-c6352c.netlify.app"   # 連署衝刺頁
TZ        = datetime.timezone(datetime.timedelta(hours=8))     # 台灣時間
START     = datetime.datetime(2026, 6, 14, 20, 0, 0, tzinfo=TZ)  # 排程起點(對齊UTC整點)
DEADLINE  = datetime.datetime(2026, 6, 17, 23, 59, 59, tzinfo=TZ) # 截止後不再發
INTERVAL_HR = 4

QUOTES = [
    "🤝 這一步，我們想跟你一起走",
    "✋ 就差幾位，希望有你",
    "⏳ 倒數中，這一次真的只有這一次",
    "🪑 一個人講沒人理，一群人講才有桌子",
    "👥 30 個人，就有一個工會",
    "💰 加班費，自己吵不如一起談",
    "🆓 連署只是表達意願，不用先繳一毛錢",
    "🛡️ 受 §35 保護，名單不會給院方，放心",
    "💪 多一個你，就多一分底氣",
    "🗣️ 不是要鬧事，是想要一個能好好談的管道",
    "🌱 沉默改變不了什麼，連署就有機會",
    "🙌 你願意，我們就更有機會",
    "🚪 機會的門，6/17 就關",
    "🔥 為自己、也為下一位同仁，站出來一次",
    "📝 1 分鐘連署，換一個能為我們發聲的工會",
]

def main():
    if not TOKEN or not GROUP:
        print("尚未設定 LINE_TOKEN / LINE_GROUP_ID（GitHub Secrets），先略過不發。")
        return
    now = datetime.datetime.now(TZ)
    if now > DEADLINE:
        print("活動已結束（過 6/17 23:59），不發送。")
        return
    slot = int((now - START).total_seconds() // (INTERVAL_HR * 3600))
    if slot < 0:
        slot = 0
    quote = QUOTES[slot % len(QUOTES)]
    text = f"{quote}\n\n✋ 1 分鐘連署 👉 {URL}"

    body = json.dumps({"to": GROUP, "messages": [{"type": "text", "text": text}]}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
    try:
        resp = urllib.request.urlopen(req)
        print(f"✅ 已推播 slot {slot}：{quote}（HTTP {resp.status}）")
    except urllib.error.HTTPError as e:
        print(f"❌ LINE 回錯 {e.code}: {e.read().decode('utf-8', 'ignore')}")
        raise

if __name__ == "__main__":
    main()
