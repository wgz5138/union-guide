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

import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler

import requests

import travelpayouts_flights as tp

TOKEN = os.environ.get("TG_TOKEN")
OWNER = os.environ.get("TG_CHAT")          # 設了就只回應本人
API = f"https://api.telegram.org/bot{TOKEN}"

# ─────────────────────────────────────────────────────────────
# log（同時印畫面 + 寫檔）
# 這支平常用 pythonw 背景啟動（開機背景啟動.bat／背景啟動機器人.bat）
# 沒有視窗，print() 出來的東西沒地方顯示、等於直接消失——收不到訊息、
# 有沒有連上、卡在哪一步都無從查起。改成跟 travelpayouts_flights.py
# 一樣寫檔案，之後「TG 不回」就能翻 logs/telegram_bot.log 直接看原因
# （常見原因：TG_CHAT 跟實際傳訊息那個聊天對不上號、409 衝突、連線失敗）。
# ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "logs", "telegram_bot.log")


def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logger = logging.getLogger("telegram_bot")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)
    fileh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000,
                                backupCount=3, encoding="utf-8")
    fileh.setFormatter(fmt)
    logger.addHandler(fileh)
    return logger


log = setup_logging()


# ─────────────────────────────────────────────────────────────
# 防止重複啟動：兩份 bot 同時搶 getUpdates 會一直 409 衝突
# ─────────────────────────────────────────────────────────────
# 緣由：`啟動聊天機器人.bat`（前景 `python.exe`）跟
# `背景啟動機器人.bat`／`開機背景啟動.bat`（背景 `pythonw.exe`）是
# 兩個不同的進程名稱，而 `停止機器人.bat` 原本只殺 `pythonw.exe`——
# 若使用者兩種都點過，會留下一個殺不掉的前景視窗，永遠 409 下去，
# 且使用者/我都看不出「已經在跑了，不缺你這份」。
# 用一個記 PID 的鎖檔在啟動當下自己擋掉，不管是哪個 .bat 點的都有效，
# 不用依賴使用者記得先點對正確的停止腳本。
LOCK_FILE = os.path.join(BASE_DIR, "telegram_bot.lock")


def _pid_alive(pid):
    """檢查這個 PID 現在是不是真的還有進程在跑（不是真的送信號，
    只是問一下，不會影響到那個進程）。"""
    if os.name == "nt":
        import subprocess
        try:
            out = subprocess.run(
                ["tasklist", "/fi", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=10)
            return str(pid) in out.stdout
        except (OSError, subprocess.SubprocessError):
            return False  # 查不到就當作沒在跑，寧可誤判成「可以啟動」
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock():
    """回傳 True＝拿到鎖、可以啟動；False＝已經有一份活著在跑，別再開。
    鎖檔壞掉／記錄的 PID 已經死了，都當作沒人在跑，直接蓋過去
    （不會卡死——舊進程真的死掉後，下一次啟動一定拿得到鎖）。"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, encoding="utf-8") as f:
                old_pid = int(f.read().strip())
            if _pid_alive(old_pid):
                return False
        except (OSError, ValueError):
            pass
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


說明 = (
    "✈️ 機票查詢小幫手\n"
    "傳給我：出發 目的地 [去程月份] [回程月份]\n"
    "月份可以不打，不打就自動幫你查未來幾個月最便宜的！\n"
    "例：\n"
    "　查 高雄 東京　（不打月份，自動查未來幾個月）\n"
    "　查 高雄 東京 2026-09　（單程，指定月份）\n"
    "　查 高雄 東京 2026-09 2026-10　（來回）\n"
    "地名可打中文（高雄、日本、首爾…）或英文代碼。\n\n"
    "🔍 還沒決定去哪？不用填目的地，傳「探索」給我，\n"
    "我會幫你掃一輪常查的幾個國家，優先秀「降價幅度大」的，\n"
    "沒有降價紀錄的補「最便宜」的給你看。\n"
    "　探索　（用預設出發地）\n"
    "　探索 高雄　（指定出發地）"
)

# 探索模式關鍵字：出現這些字，就不強制要求目的地，改成掃一輪熱門國家找划算的
探索關鍵字 = ("探索", "驚喜", "隨便看看", "有什麼便宜", "不知道去哪", "隨機")


MAX_MSG_LEN = 4000   # Telegram 訊息上限 4096 字，留一點安全margin


def send(chat_id, text):
    if len(text) > MAX_MSG_LEN:
        text = text[:MAX_MSG_LEN] + "\n…（內容過長，已截斷）"
    try:
        resp = requests.post(f"{API}/sendMessage",
                             data={"chat_id": chat_id, "text": text}, timeout=15)
        data = resp.json()
        if not data.get("ok", False):
            # 網路層沒出錯，但 Telegram 拒絕了這則訊息（例如格式問題）
            # ——一定要記下來，不能讓查詢結果無聲無息消失。
            log.warning("送出失敗（Telegram 拒絕）：%s", data)
    except (requests.RequestException, ValueError) as e:
        log.warning("送出失敗：%s", e)


def handle(text):
    """把使用者訊息變成查詢，回傳要回覆的字串。
    很寬鬆：有沒有空格、有沒有逗號、有沒有「查」都看得懂。
    例：『查 高雄 東京 2026-09』『查高雄福岡，2026-09』都行。
    也支援『探索』模式（見 探索關鍵字）：不填目的地，掃一輪熱門國家找划算的。"""
    is_explore = any(k in text for k in 探索關鍵字)

    # 1) 先抓出月份（一個=單程；兩個=來回；探索模式不需要月份，忽略）
    months = re.findall(r"\d{4}-\d{2}", text)
    # 2) 把「查」、探索關鍵字、月份、各種標點都換成空白，剩下的拿來找地名
    rest = text.replace("查", " ")
    for k in 探索關鍵字:
        rest = rest.replace(k, " ")
    for m in months:
        rest = rest.replace(m, " ")
    for ch in "，,、。；;／/ 　":
        rest = rest.replace(ch, " ")
    # 3) 先用「地名對照表」在字串裡找中文地名（依出現順序）
    hits = sorted((rest.find(n), n) for n in tp.地名對照表 if n in rest)
    places = [n for _, n in hits]
    # 4) 找不到足夠中文地名，就退回用空白切詞（支援英文代碼）
    #    長度 >=2 才算候選字：地名對照表最短的地名是 2 字、機場代碼是 3 字，
    #    這樣才不會把口語尾詞（「啊」「呢」「吧」）誤判成使用者打的地名
    #    ──探索模式門檻只要 1 個地名，特別容易踩到這個情況。
    if len(places) < (1 if is_explore else 2):
        places = [w for w in rest.split() if len(w) >= 2]

    if is_explore:
        # 探索模式：最多只需要一個地名（出發地），沒給就用預設值
        origin = places[0] if places else None
        if origin and origin not in tp.地名對照表 and any(ord(c) > 127 for c in origin):
            return (f"我不認得出發地「{origin}」😅\n"
                    "請改用機場代碼，或用清單上的中文地名：\n"
                    + "、".join(tp.地名對照表))
        rows = tp.explore_deals(origin=origin, top=5)
        if not rows:
            return "熱門國家最近都查無票價，晚點再試試看 🙏"
        起點 = origin or (tp.ROUTES[0]["origin"] if tp.ROUTES else "高雄")
        lines = [f"🔍 探索模式（出發：{起點}）幫你掃了一輪，這些比較划算 👇"]
        for i, r in enumerate(rows, 1):
            飛行 = "直飛" if r["transfers"] == 0 else f"轉{r['transfers']}次"
            drop = (f"　📉 降了 {r['drop_pct']}%（上次 {r['drop_from']:.0f}）"
                    if r.get("drop_pct") else "")
            lines.append(
                f"\n{i}. ✈ {r['route']}（{r['dest_code']}）"
                f"{r['price']:.0f} {r['currency']}（{飛行}・{r['depart_at']}）{drop}\n{r['link']}")
        return "\n".join(lines)

    # 沒打年月也可以查：不強制要求月份，自動查未來幾個月（見下方 route 組裝）
    if len(places) < 2:
        return "看不太懂耶 😅\n\n" + 說明

    origin, dest = places[0], places[1]

    # 如果地名是「中文但不在對照表」，API 會看不懂 → 先友善提醒，別吐錯誤
    未知 = [p for p in (origin, dest)
            if p not in tp.地名對照表 and any(ord(c) > 127 for c in p)]
    if 未知:
        return (f"我不認得「{'、'.join(未知)}」😅\n"
                "請改用機場代碼（例：重慶 CKG、成都 CTU），或用清單上的中文地名：\n"
                + "、".join(tp.地名對照表))

    route = {"origin": origin, "dest": dest}
    月份說明 = f"未來{tp.FLEX_MONTHS_AHEAD}個月"
    if len(months) >= 1:
        route["month"] = months[0]
        月份說明 = months[0]
    if len(months) >= 2:
        route["return"] = months[1]

    # 列出多張便宜的票讓你挑（查整個國家時會看到不同城市；優先直飛）
    rows = tp.search_offers(route, top=5, direct_first=True)
    if not rows:
        return f"「{origin}→{dest}」（{月份說明}）最近查無票價，換個目的地試試。"

    trip = rows[0]["trip"]
    lines = [f"✈️ {origin}→{dest}（{trip}）便宜的幾個（點連結看/訂）："]
    for i, r in enumerate(rows, 1):
        飛行 = "直飛" if r["transfers"] == 0 else f"轉{r['transfers']}次"
        when = r["depart_at"]
        if trip == "來回" and r["return_at"]:
            when += f"→{r['return_at']}回"
        lines.append(
            f"\n{i}. ✈ {r['dest_code']}　{r['price']:.0f} {r['currency']}"
            f"（{飛行}・{r['airline']}・{when}）\n{r['link']}")
    return "\n".join(lines)


def main():
    if not TOKEN:
        log.error("❌ 還沒設 TG_TOKEN。請先設定環境變數再跑。")
        return
    if not acquire_lock():
        # 不管是前景視窗（啟動聊天機器人.bat）還是背景（開機背景啟動.bat／
        # 背景啟動機器人.bat）點開的，只要偵測到已經有一份活著，直接不跑，
        # 別再去搶 getUpdates 製造 409 衝突。
        log.error("已經有一份機票 bot 在跑了（見 %s），不重複啟動。"
                  "想換一份跑（例如改了設定要生效），"
                  "先確定舊的真的關掉——用『停止機器人.bat』，"
                  "或工作管理員找 python.exe / pythonw.exe 手動結束。",
                  LOCK_FILE)
        return
    log.info("🤖 機票 bot 啟動，去 Telegram 傳訊息給它吧～"
             "（背景執行時看 logs/telegram_bot.log；有開視窗按 Ctrl+C 可停止）")
    if OWNER:
        log.info("　目前設定只回應 TG_CHAT=%s，其他聊天傳訊息會被忽略。", OWNER)
    offset = None
    while True:
        # 取得新訊息：連線錯、或回應不是 JSON，都自我恢復，絕不讓 bot 整支掛掉
        try:
            r = requests.get(f"{API}/getUpdates",
                             params={"timeout": 30, "offset": offset}, timeout=40)
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("連線/回應問題，5 秒後重試：%s", e)
            time.sleep(5)
            continue

        if not data.get("ok", False):
            if data.get("error_code") == 409:
                log.warning("⚠ 偵測到另一個 bot 也在收訊息（409 衝突）。"
                            "請只留一個：先點『停止機器人.bat』再重開一個。10 秒後重試…")
                time.sleep(10)
            else:
                log.warning("Telegram 回報異常，5 秒後重試：%s", data)
                time.sleep(5)
            continue

        for upd in data.get("result", []):
            try:
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue
                if OWNER and str(chat_id) != str(OWNER):
                    # 常見的「bot 明明在跑卻完全不回」就是卡在這裡：
                    # 傳訊息的這個聊天跟設定的 TG_CHAT 對不上號，被無聲忽略。
                    # 記下實際 chat_id，方便比對是不是設定值錯了。
                    log.info("收到訊息但 chat_id=%s 跟 TG_CHAT=%s 不符，忽略。",
                             chat_id, OWNER)
                    continue
                if text in ("/start", "help", "說明", "?", "？"):
                    send(chat_id, 說明)
                    continue
                log.info("收到（chat_id=%s）：%s", chat_id, text)
                try:
                    reply = handle(text)
                except Exception as e:
                    reply = f"查詢出錯：{e}"
                send(chat_id, reply)
            except Exception as e:
                # 單則訊息出錯只略過該則，bot 繼續活著
                log.exception("處理某則訊息出錯（略過）：%s", e)
                continue


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # pythonw 背景啟動沒有視窗，任何沒接住的例外原本會無聲消失，
        # 讓人完全不知道 bot 已經死掉了。至少留一筆紀錄在檔案裡。
        log.exception("bot 意外中止")
        raise
    finally:
        # 不管是正常結束、Ctrl+C、還是意外中止，都要把鎖放掉，
        # 不然下次啟動會被自己的舊鎖擋住（鎖檔裡的 PID 已死，
        # acquire_lock() 其實會自動判斷並蓋過去，這裡純粹求乾淨）。
        release_lock()
