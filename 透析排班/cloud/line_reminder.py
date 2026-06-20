#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
透析印藥水 LINE 提醒（雲端版，純標準庫）
每天執行一次：找出「明天」要印藥水的人 → 私訊提醒本人。

資料來源
  1) 本週名單：欄位 印日期, 區, 姓名
       來自玉繡維護的 Google 試算表（發布成 CSV）→ 用環境變數 SHEET_CSV_URL
       或本機檔（測試用）→ 參數 --list <檔>
  2) userId 對照：repo 內 line_userid對照.csv（欄位 姓名, 卡號, userId）

環境變數
  LINE_CHANNEL_TOKEN  LINE 金鑰（GitHub Secret）
  SHEET_CSV_URL       Google 試算表發布的 CSV 網址

參數
  --dry-run           只印出「會發給誰」，不真的發（測試用）
  --list <檔>         用本機名單檔（測試用，取代 SHEET_CSV_URL）
  --date YYYY-MM-DD   指定「今天」是哪天（測試用），預設台灣今天
  --target prev|same  提醒「前一天」(預設) 或「當天」
"""
import os, sys, csv, io, json, argparse, urllib.request
from datetime import datetime, timedelta, timezone

TW = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
MAP_CSV = os.path.join(BASE, "..", "line_userid對照.csv")


def load_usermap(path):
    m = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            nm = (r.get("姓名") or "").strip()
            uid = (r.get("userId") or "").strip()
            if nm and uid:
                m[nm] = uid
    return m


def norm_date(s):
    s = (s or "").strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%m-%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            if fmt == "%m-%d":
                d = d.replace(year=datetime.now(TW).year)
            return d
        except ValueError:
            pass
    return None


def load_rows(text):
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        d = (r.get("印日期") or r.get("日期") or "").strip()
        area = (r.get("區") or r.get("區域") or "").strip()
        nm = (r.get("姓名") or "").strip()
        if d and nm:
            rows.append((norm_date(d), area, nm))
    return rows


def fetch_list(args):
    if args.list:
        with open(args.list, encoding="utf-8-sig") as f:
            return f.read()
    url = os.environ.get("SHEET_CSV_URL")
    if url:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read().decode("utf-8-sig")
    local = os.path.join(BASE, "本週名單.csv")     # 備援：repo 內名單
    if os.path.exists(local):
        with open(local, encoding="utf-8-sig") as f:
            return f.read()
    sys.exit("❌ 沒有名單來源：設 SHEET_CSV_URL、放 本週名單.csv、或用 --list <檔>")


def push(token, uid, text, dry):
    if dry:
        print(f"   [乾跑] → {uid[:12]}… : {text}")
        return True
    body = json.dumps({"to": uid, "messages": [{"type": "text", "text": text}]}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push", data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30)
        return True
    except Exception as e:
        print(f"   ⚠ 發送失敗 {uid[:12]}… : {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list")
    ap.add_argument("--date")
    ap.add_argument("--target", choices=["prev", "same"], default="prev")
    args = ap.parse_args()

    today = norm_date(args.date) if args.date else datetime.now(TW).date()
    target = today + (timedelta(days=1) if args.target == "prev" else timedelta(0))
    print(f"■ 今天={today}　提醒「印日={target}」的人（{args.target}）")

    usermap = load_usermap(MAP_CSV)
    rows = load_rows(fetch_list(args))

    todo = {}
    for d, area, nm in rows:
        if d == target:
            todo.setdefault(nm, [])
            if area and area not in todo[nm]:
                todo[nm].append(area)

    if not todo:
        print("　→ 明天沒有人要印藥水（或名單還沒更新）。結束。")
        return

    token = os.environ.get("LINE_CHANNEL_TOKEN", "")
    if not token and not args.dry_run:
        sys.exit("❌ 沒有 LINE_CHANNEL_TOKEN（請在 GitHub Secrets 設定）")

    mmdd = f"{target.month}/{target.day}"
    when = "今天" if args.target == "same" else "明天"
    ok = miss = 0
    for nm, areas in todo.items():
        uid = usermap.get(nm)
        zone = "、".join(areas)
        zpart = f"「{zone}」" if zone else ""
        text = f"🔔 記得{when}({mmdd})要印{zpart}藥水喔！🙏"
        if not uid:
            print(f"   ⚠ 找不到「{nm}」的 userId（還沒加好友？）→ 略過")
            miss += 1
            continue
        if push(token, uid, text, args.dry_run):
            ok += 1
    print(f"■ 完成：成功 {ok} 人；缺 userId {miss} 人")


if __name__ == "__main__":
    main()
