# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）v3.26
  • Fix1：公平歷史學玉繡實際決定，而非程式原排
  • Fix2：稽核送出後 LINE 通知每位稽核者責任班次
  • Fix3：自動選最接近今天的班表分頁
  • v3.26：排班 Round3 跨區優先於同區印第二次（病房/ICU/休假限制下盡可能不讓同區人一週兩次）
  • v3.27：本週放假但可印藥水的人可在 UI 手動指定（強制可印.csv），系統視為白班候選人
  • v3.28：強制可印雙效升級 — ①玉繡指定的人優先於公平排序（不再被成本低的人搶掉）②班表空白當天也能被納入候選（從本週其他班別推出所在區域）
  • v3.29：修正 v3.28 補漏邏輯造成印藥水日錯算（把 7/17 的人算成 7/16）；改為只靠優先排序，班表有記錄才納入候選；kind_area 調整讓特休/副值等排除班別也能被玉繡強制指定
  • v3.30：還原 kind_area() — 強制可印只做優先排序，不改資格判斷（放假/大夜/空白 → 一律不能印）
  • v3.30：還原 kind_area() — 強制可印只做優先排序，不改資格判斷（放假/大夜/空白 → 一律不能印）【v3.31 Round1 改動因造成雙印回歸，已撤銷】
  • v3.32：排班 Round1+2 改為全域最佳化配對(scipy)，取代貪心逐格搶人，解決「換處理順序就搶錯人、
    逼別人印第二次」的結構性問題；拿 3 週真實班表驗證：不劣於 v3.30、其中 1 週（本次爭議週）
    從「1人雙印」改善為「0人雙印」，且與玉繡當面確認過的規則(顏凰任 7/16 印 7/18)吻合
  • v3.33：修正「送到雲端」的靜默失敗 — 排班歷史(setScheduleHistory)同步失敗時，先前完全不會
    提示，畫面只顯示「已送到雲端」成功訊息，導致統計管理讀不到那一週卻沒人發現。現在失敗會
    跳出明確錯誤訊息並提示重試。
  • v3.34：v3.33 上線後重送仍不跳錯誤、統計卻還是沒更新 — 因為 GAS 端 setScheduleHistory_()
    不管收到幾筆都一律回 {ok:true}，即使實際送出 0 筆也算「成功」。push_history() 改回傳
    (ok, 實際筆數, 失敗原因)，成功也會顯示送了幾筆，這樣才看得出「回報成功但其實0筆」這種狀況。
  • v3.35：找到 7月資料消失的真正原因 — 不是同步失敗，是「統計管理→印藥水統計」分頁可以
    直接改印次/休次數字、按「存回雲端」，這個功能會呼叫 setAllScheduleHistory（GAS端整份
    clearContents 再重建），把全部人的每週真實明細換成「統計-印01」這種沒有日期的假列，
    26週374筆真實歷史因此消失，只剩總數字。已加防呆：這顆按鈕現在要先勾選「我知道會清空
    每週明細」才能按，並在上方加醒目警告說明用途，避免下次又不小心整份洗掉。
  • v3.36：v3.35上線後第一次真的送出，跳出新錯誤「Out of range float values are not JSON
    compliant: nan」— build_corrected_history()/push_history() 讀 CSV 時沒指定 dtype=str，
    pandas 把「休」狀態那些空白的治療日欄位讀成 float NaN，requests 送 JSON 時嚴格檢查
    NaN 不合法直接拋例外。改成 pd.read_csv(..., dtype=str, keep_default_na=False)，空白
    保留為空字串，不再被轉成 NaN。已用實際資料重現問題、驗證修法有效才上線。
  • v3.38：修掉「統計管理→同步本機CSV→雲端」這顆按鈕的洗資料地雷——2026-07-20凌晨實際
    發生：本機備份CSV還停在舊週次，按下去把雲端剛送出、比CSV新的一週資料整批蓋掉了。
    原本 sync_schedule_history_from_csv()/sync_audit_history_from_csv() 是「本機整批覆蓋
    雲端」；改成「先讀雲端現況，只把本機有、雲端沒有的週次/月份補上去，雲端既有資料原封
    不動」——不是加警告字樣，是讓這顆按鈕在設計上就不可能再覆蓋掉雲端較新的資料。
  • v3.38：同一版加首頁顯眼統計（雲端排班歷史累積筆數／最新一週，大字體 st.metric），
    每次打開網頁都看得到，平常掃一眼就能發現「數字很久沒變/忽然變小」這種異常，不用等
    查統計才發現（這次事件玉繡是三週後才發現）；並主動比對本機git備份CSV是否落後於雲端，
    落後就直接顯示警告，不用等有人誤按同步按鈕才知道備份是舊的。
  • v3.39：修正「傳LINE群組用」文字（_build_line_txt）原本依「治療日」分組輸出，導致不同
    治療日往前推剛好同一天印藥水時（例如白班7/21治療日、小夜7/22治療日，往前推都是
    7/20），會各自變成一行、同一天看起來印了兩批人共四人，容易被誤會排錯（2026-07-19、
    07-20兩週都有人反映看不懂）。改成依「印藥水日」分組合併輸出，同一天的人（不論來自
    哪個治療日）合併成一行，各區用「、」串接多人。
  • v3.40：全面盤點後發現「組員名單」分頁的「📤 從本機CSV同步到雲端」跟排班/稽核歷史
    是同一類地雷——本機 組員名單.csv 落後時按下去一樣整批覆蓋雲端。但組員名單跟排班/
    稽核歷史不同：真的會有人被移除（離職/退組），不能沿用v3.38「只補missing」的合併
    邏輯（會把雲端正確移除的人誤救回來）。改成更嚴格：只有雲端目前是空的（真正的初始化）
    才允許這顆按鈕動作，雲端已有名單一律拒絕並提示改用下方表格編輯＋存回雲端。
  • v3.41：派獨立agent全面稽查出17個bug（5高7中5低），逐一實測資料驗證後修復13個
    （app.py + 排班.py + 稽核.py）：
    【高】LINE群組公告日期每週錯2-3人 — 每欄只取第一區的印藥水日當整欄日期，改成每
    格各自帶自己的印藥水日（實測4週48人次：修正前錯9次→修正後0次）
    【高】雙印時姓名被污染成「XXX雙印」送上雲端，導致收不到提醒/公平歷史算錯/公告
    同時列印與休 — 產生定案 + _build_line_txt 都補上濾除
    【高】稽核統計「存回雲端」沒有防呆，補上跟排班統計一樣的警告勾選框
    【高】稽核第二班白/夜門檻算錯（allow_night_band2 拿 n_night 當基準）— 改成用
    「總白班格數」判斷，實測7月真實資料從1格排不出→0格
    【高】稽核 W135/W246 組別限制形同虛設（cands() 漏帶 g 參數）— 補上 group_ok() 檢查
    ＋排不出時自動放寬並跳警告
    【中】稽核月份key用西元(2026-07)、稽核紀錄.csv卻是民國(115-07)，skip_month永遠對
    不上、公平分數悄悄算錯 — 統一改民國，app.py/稽核.py兩邊都修，連帶修正
    fetch_last_audit_prefill() 抓「上次稽核月」的排序bug
    【中】稽核「第一週」判斷邏輯選錯月份 — 改成看該週落在目標月的天數最多者
    【中】強制可印只認得完整全名，玉繡輸入簡稱查無此人時完全靜默失效 — 改成後綴比對
    ＋比對不到時明確跳警告列出哪幾筆沒生效
    【中】雲端草稿UTC時間字串截前10碼取到錯誤日期（3處同樣手寫 _clean_dt，跨日/跨年
    都會錯）— 統一改共用 gs_date_to_ymd()，已測5組含跨年案例
    【中】排班/稽核歷史讀取失敗時靜默改用本機舊備份算分數，畫面完全無提示 — 3處呼叫
    點補上明確錯誤/警告訊息
    【中】稽核人工改派沒同步回歷史紀錄，下次公平分數對不上玉繡實際決定 — 新增
    build_corrected_audit_history()，仿照排班歷史既有做法
    【中】「產生定案」整週共用同一個猜測年份，跨年那週（如12月最後一週+1月第一週）
    後半段月份年份一定算錯 — 改成從當次產生的雲端貼上CSV建「每格自己的年份」對照表
    （(區,月,日)→年），逐格查表不再整週共用；4週真實資料驗證0筆查表失敗，且跨年模擬
    案例確認1/1、1/2從錯誤的去年改成正確的隔年
    【低】_best_sheet_index 年份修正只做單向（假設分頁一定是未來），跨年後選到半年前
    分頁 — 改雙向修正
    【低】稽核歷史同步會把「草稿」「意見-」開頭的特殊列跟正常月份一起重複疊加 — 同步
    前先過濾掉這兩種
  • v3.42（2026-08-01）休診日單一來源（接續包第二十三節待辦#17，架構決策已由使用者拍板
    「要有同步機制、不是只加交叉檢查」）：過年/連假清單原本有兩份各自維護——
    webapp/休診日.csv（排班.py prev_treat 算「印藥水日」用）與 藥水小幫手.gs 的
    EXTRA_HOLIDAYS 陣列（prevWorkday_ 算「LINE 提醒日」用）。改一邊不會同步到另一邊，
    兩邊對不上就會讓「排出來的印藥水日」跟「LINE 通知的日期」差一天（跟 v5.8 修掉的
    off-by-one 同一類，只是兩份剛好都還是空的所以沒爆）。
    改法：試算表新增「休診日」分頁當唯一來源，.gs 的 isWorkday_ 改讀該分頁（含執行期
    快取＋日期型別正規化），app.py 新增 getHolidays/setHolidays，排班/稽核執行前把雲端
    休診日當 config_override 餵進去（雲端優先、本機 CSV 只當讀不到時的保底且會跳警告），
    並在「📊 統計管理」新增「🗓 休診日」分頁供玉繡直接編輯。
    ⚠ .gs 要手動「部署→管理部署→新版本」到 v6.1 才會生效。
  • v3.43（2026-08-01）搭配 .gs v6.2：GAS 的 sendAuditNotice 現在會檢查 LINE API 回應碼，
    把「真的沒送出去」的人回報在 failed/failedNames。app.py 這端接住並在畫面明確列出
    「這幾位的 LINE 通知實際發送失敗，請改用其他方式告知」——以前 LINE 回 401/403/400
    會被整個吞掉、畫面照樣顯示「已通知 N 人」，那幾個人其實根本沒收到。
    （舊版 GAS 沒有這兩個欄位，取不到就當 0/空，不會壞。）
    接續包第二十三節的 3 項待辦至此全部完成（#14/#16 在 .gs v6.2、#17 在 v3.42/v6.1）。
"""
import os, io, re, csv, json, base64, hashlib, tempfile, shutil, subprocess, sys
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = ["組員名單.csv", "床號分區.csv", "不可印班別.csv", "休診日.csv",
          "排班紀錄.csv", "稽核紀錄.csv"]
CELL_RE = re.compile(r'^(.*?)\((\d+)/(\d+)印\)(.*)$')

def _detect_ext(b): return ".xlsx" if b[:4] == b'PK\x03\x04' else ".xls"


# ── 核心工具執行器 ────────────────────────────────────────
def run_tool(script, xls_bytes, extra_args, config_overrides=None):
    work = tempfile.mkdtemp()
    try:
        for fn in CONFIG + [script]:
            src = os.path.join(HERE, fn)
            if os.path.exists(src): shutil.copy(src, work)
        if config_overrides:
            for fn, content in config_overrides.items():
                with open(os.path.join(work, fn), "wb") as f: f.write(content)
        if xls_bytes is not None:        # 一般模式：寫入上傳的班表
            ext  = _detect_ext(xls_bytes)
            xlsp = os.path.join(work, f"上傳班表{ext}")
            with open(xlsp, "wb") as f: f.write(xls_bytes)
            cmd = [sys.executable, script, xlsp] + list(extra_args)
        else:                            # 快速模式：免上傳 Excel
            cmd = [sys.executable, script] + list(extra_args)
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=180)
        files = {}
        od = os.path.join(work, "輸出")
        if os.path.isdir(od):
            for fn in sorted(os.listdir(od)):
                with open(os.path.join(od, fn), "rb") as fh: files[fn] = fh.read()
        updated_hist = {}
        for hfn in ["排班紀錄.csv", "稽核紀錄.csv"]:
            hp = os.path.join(work, hfn)
            if os.path.exists(hp):
                with open(hp, "rb") as fh: updated_hist[hfn] = fh.read()
        stdout = r.stdout + (("\n" + r.stderr.strip()) if r.stderr.strip() else "")
        return stdout, files, updated_hist
    finally:
        shutil.rmtree(work, ignore_errors=True)


def pick(files, suffix):
    for fn, b in files.items():
        if fn.endswith(suffix): return fn, b
    return None, None

def extract_notes(stdout):
    notes = []
    for ln in stdout.splitlines():
        s = ln.strip()
        if any(k in s for k in ("休息","↳","※","❌","借")) and "【公平累計】" not in s:
            notes.append(s)
    return notes

def extract_fairness(stdout):
    """抽出【公平累計】表格區段（含標題）。"""
    lines = stdout.splitlines()
    in_block = False; block = []
    for ln in lines:
        s = ln.strip()
        if "【公平累計】" in s:
            in_block = True
        if in_block:
            if s == "" and block:    # 空行代表區段結束
                break
            if s:
                block.append(s)
    return block

def parse_grid(df):
    names = df.copy(); dates = df.copy(); marks = df.copy()
    for r in df.index:
        for c in df.columns:
            v = str(df.loc[r,c]); m = CELL_RE.match(v)
            if m:
                names.loc[r,c]=m.group(1); dates.loc[r,c]=f"{int(m.group(2))}/{int(m.group(3))}"; marks.loc[r,c]=m.group(4)
            else:
                names.loc[r,c]=v; dates.loc[r,c]=""; marks.loc[r,c]=""
    return names, dates, marks

def year_from_cloud(files):
    _, b = pick(files, ".csv")
    if b:
        try:
            d = pd.read_csv(io.BytesIO(b), encoding="utf-8-sig")
            return int(str(d["印日期"].iloc[0]).split("-")[0])
        except Exception: pass
    return pd.Timestamp.now().year

def year_map_from_cloud(files):
    """v3.41 修正 #13a：整週不能只用一個年份！
    舊版 year_from_cloud() 只抓 CSV 第一列的年份當「整週共用」，如果這週剛好跨年
    （例如 12月最後一週+1月第一週排在同一張表，或單週橫跨 12/29~1/4），
    後面月份的格子年份一定會算錯（該是明年的被標成今年，或反過來）。
    這支改成「每一格自己查」：排班.py 產生的『雲端貼上_*.csv』本來就有每一列真正的
    印日期(含年)，這裡直接建 (區, 月, 日) → 年 的對照表，之後產生定案時逐格查表，
    不再整週共用單一猜測值。"""
    out = {}
    _, b = pick(files, ".csv")
    if b:
        try:
            d = pd.read_csv(io.BytesIO(b), encoding="utf-8-sig", dtype=str)
            for _, row in d.iterrows():
                ds = str(row.get("印日期", "")).strip()
                m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', ds)
                if not m: continue
                area = str(row.get("區", "")).strip()
                out[(area, int(m.group(2)), int(m.group(3)))] = int(m.group(1))
        except Exception:
            pass
    return out


# ── Fix3：自動選最接近今天的班表分頁 ─────────────────────
def _best_sheet_index(sheets):
    """分頁名稱有日期 → 選最接近今天的；否則選最後一頁。
    支援完整日期（2026-06-16）及 MMDD/MMDD-MMDD 格式（0706、0706-0712）。"""
    from datetime import timezone, timedelta
    today = datetime.now(timezone(timedelta(hours=8))).date()  # 台灣時區
    best_idx = len(sheets) - 1
    best_delta = None
    for i, sn in enumerate(sheets):
        sn_str = str(sn)
        # 完整日期格式：2026-06-16
        m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", sn_str)
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                delta = abs((d - today).days)
                if best_delta is None or delta < best_delta:
                    best_delta = delta; best_idx = i
            except Exception: pass
            continue
        # MMDD 或 MMDD-MMDD 格式：0706、0629-0712
        m2 = re.match(r"(\d{2})(\d{2})", sn_str.strip())
        if m2:
            try:
                mo, dy = int(m2.group(1)), int(m2.group(2))
                if 1 <= mo <= 12 and 1 <= dy <= 31:
                    yr = today.year
                    d = date(yr, mo, dy)
                    # 跨年修正要做**雙向**。v3.41：舊版只有「太舊 → 加一年」，
                    # 少了反向的「太新 → 減一年」，導致例如今天是 2027-01-02 時，
                    # 分頁「1228~0103」會被算成 2027-12-28（delta 360）而不是
                    # 2026-12-28（delta 5），預設就選錯分頁。
                    # （_fmt_week 在下方本來就是雙向寫法，兩邊原本不一致。）
                    if (today - d).days > 180:
                        d = date(yr + 1, mo, dy)
                    elif (d - today).days > 180:
                        d = date(yr - 1, mo, dy)
                    delta = abs((d - today).days)
                    if best_delta is None or delta < best_delta:
                        best_delta = delta; best_idx = i
            except Exception: pass
    return best_idx


# ── Fix1：根據玉繡實際定案重建公平歷史 ──────────────────
def _load_roster_names():
    """讀組員名單.csv → {姓名: 卡號}"""
    f = os.path.join(HERE, "組員名單.csv")
    mapping = {}
    if not os.path.exists(f): return mapping
    try:
        with open(f, encoding="utf-8-sig") as fp:
            for row in csv.DictReader(fp):
                card = (row.get("卡號") or "").strip()
                name = (row.get("姓名") or "").strip()
                if name: mapping[name] = card
    except Exception: pass
    return mapping

def _load_roster_full():
    """讀組員名單.csv → [{'卡號':.., '姓名':..}]（依檔案順序）"""
    f = os.path.join(HERE, "組員名單.csv")
    out = []
    if not os.path.exists(f): return out
    try:
        with open(f, encoding="utf-8-sig") as fp:
            for row in csv.DictReader(fp):
                card = (row.get("卡號") or "").strip()
                name = (row.get("姓名") or "").strip()
                if name: out.append({"卡號": card, "姓名": name})
    except Exception: pass
    return out

def fetch_last_audit_prefill():
    """從雲端稽核歷史抓「最近一個月」的每人班型/區，給快速模式預先帶入。
    回傳 {姓名: (班型, 區)}；班型由班次推回（第三班=小夜，否則白班）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return {}
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        rows = resp.json().get("rows") or []
        if len(rows) < 2: return {}
        hdr = [str(x).strip() for x in rows[0]]
        iM, iN, iP = hdr.index("月份"), hdr.index("姓名"), hdr.index("位置")
        # 只看正常的月份鍵，跳過草稿/意見那些特殊列。
        # v3.41：舊版寫死 ^\d{4}-\d{2}$（只吃西元4位數），但實際資料全是民國3位數
        # （114-09 ~ 115-07），永遠比不中 → 「快速點選會帶出上個月設定」這功能其實
        # 一直是靜默失效的，玉繡每個月都得從頭點。改成民國/西元都接受。
        months = [str(r[iM]).strip() for r in rows[1:]
                  if re.match(r"^\d{3,4}-\d{2}$", str(r[iM]).strip())]
        if not months: return {}
        # 民國(115-07)與西元(2026-07)若混在一起，直接 max() 會用字串比而排錯
        # （"2">"1" 會讓 2026-07 永遠勝過 115-12），先正規化成西元再取最大
        def _to_ce(k):
            y, m = k.split("-")
            y = int(y)
            return (y + 1911 if y < 1911 else y, int(m))
        last = max(months, key=_to_ce)
        pf = {}
        for r in rows[1:]:
            if str(r[iM]).strip() != last: continue
            name = str(r[iN]).strip(); pos = str(r[iP]).strip()
            if not name or not pos: continue          # 休息者無位置 → 不帶入
            area = pos.split("/")[0].strip()
            typ  = "小夜" if "第三班" in pos else "白班"
            pf[name] = (typ, area)
        return pf
    except Exception:
        return {}

# ── 稽核「草稿暫存」：借用稽核歷史的特殊月份鍵存放，不影響公平輪序 ──
DRAFT_KEY = "草稿"

def fetch_audit_draft():
    """讀雲端草稿（稽核歷史裡 月份=='草稿' 那幾筆）→ {姓名: (班型, 區)}。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return {}
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        rows = resp.json().get("rows") or []
        if len(rows) < 2: return {}
        hdr = [str(x).strip() for x in rows[0]]
        iM, iN, iS, iP = (hdr.index("月份"), hdr.index("姓名"),
                          hdr.index("狀態"), hdr.index("位置"))
        d = {}
        for r in rows[1:]:
            if str(r[iM]).strip() != DRAFT_KEY: continue
            name = str(r[iN]).strip()
            if name: d[name] = (str(r[iS]).strip(), str(r[iP]).strip())  # 狀態=班型, 位置=區
        return d
    except Exception:
        return {}

def push_audit_draft(df):
    """把目前點選存成雲端草稿（借用 setAuditResult，月份=草稿；班型放狀態欄、區放位置欄）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    try:
        rows = [[DRAFT_KEY, str(r["卡號"]), str(r["姓名"]), str(r["班型"]), str(r["區"])]
                for _, r in df.iterrows()]
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAuditResult", "secret": WRITE_SECRET,
                                   "key": DRAFT_KEY, "rows": rows},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

def clear_audit_draft():
    """清除雲端草稿（送空 rows，月份=草稿 的紀錄會被移除）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAuditResult", "secret": WRITE_SECRET,
                                   "key": DRAFT_KEY, "rows": []},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

# ── 印藥水定案雲端草稿（讓小巫雙重確認）───────────────────
def push_week_draft(rows, sheet0):
    """把玉繡的定案存到雲端草稿（排班草稿分頁），讓小巫可以讀取確認。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    try:
        cloud_rows = [[str(sheet0)] + [str(v) for v in r] for r in rows]
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setWeekDraft", "secret": WRITE_SECRET,
                                   "rows": cloud_rows},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

def gs_date_to_ymd(s):
    """把 GAS 回傳的日期轉成台北時區的 YYYY-MM-DD 字串。

    ⚠ v3.41 修正的重要 bug：Google Sheets 會把「2026-07-16」這種字串存成**日期型別**，
    `JSON.stringify` 序列化時會轉成 **UTC**：台北 7/16 00:00 → "2026-07-15T16:00:00.000Z"。
    舊版三處 `_clean_dt` 都直接 `re.match(r'(\\d{4}-\\d{2}-\\d{2})')` 截前10碼，於是拿到
    **7/15，整整少一天**。（"T16:00:00Z" 正好是 UTC+8 的午夜，就是它是日期型別的鐵證。）
    後果：載入雲端草稿後，全部12人的印藥水日整批早一天，接著按「送到雲端」就把錯的
    日期寫進本週名單，LINE 提醒也跟著錯——症狀跟 v5.8 修掉的那個一樣，但成因完全不同。

    這裡改成：偵測到帶時間的 ISO 格式就先當 UTC 解析、再轉台北時區取日期；
    純日期字串（沒有時間部分）維持原樣直接取用。
    """
    s = str(s).strip()
    # 帶時間的 ISO 字串（GAS 序列化日期型別會長這樣）→ 必須做時區換算
    m = re.match(r'^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})', s)
    if m:
        try:
            dt_utc = datetime.strptime(m.group(0)[:19], "%Y-%m-%dT%H:%M:%S")
            return (dt_utc + timedelta(hours=8)).strftime("%Y-%m-%d")   # UTC → Asia/Taipei
        except Exception:
            return m.group(1)
    m2 = re.match(r'(\d{4}-\d{2}-\d{2})', s)
    return m2.group(1) if m2 else s

def fetch_week_draft():
    """讀取雲端草稿 → (rows, sheet0)；沒有草稿回傳 (None, None)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None, None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getWeekDraft", "secret": WRITE_SECRET},
                             timeout=20)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None, None
        rows_raw = d["rows"]
        if len(rows_raw) < 2: return None, None
        sheet0 = str(rows_raw[1][0])
        # GAS 回傳日期可能是 "2026-07-05T16:00:00.000Z"（UTC）→ 要轉台北時區才不會少一天
        rows = [[gs_date_to_ymd(r[1])] + [str(x) for x in r[2:]] for r in rows_raw[1:]]
        return rows, sheet0
    except Exception:
        return None, None

def clear_week_draft_cloud():
    """清除雲端草稿。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setWeekDraft", "secret": WRITE_SECRET,
                                   "rows": []},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

def fetch_schedule_stats():
    """從雲端排班歷史彙總每人印/休次數 → DataFrame，或 None。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getScheduleHistory", "secret": WRITE_SECRET},
                             timeout=30)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None
        rows = d["rows"]
        if len(rows) < 2: return None
        df = pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
        df["狀態"] = df["狀態"].str.strip()
        # 只統計正常 印/休（排除草稿、修正等特殊週次）
        df = df[df["狀態"].isin(["印","休"])]
        if df.empty: return None
        grp = df.groupby(["卡號","姓名"])["狀態"].value_counts().unstack(fill_value=0)
        grp = grp.reindex(columns=["印","休"], fill_value=0).reset_index()
        grp.columns = ["卡號","姓名","印次","休次"]
        grp["印次"] = pd.to_numeric(grp["印次"], errors="coerce").fillna(0).astype(int)
        grp["休次"] = pd.to_numeric(grp["休次"], errors="coerce").fillna(0).astype(int)
        grp["淨值(印-休)"] = grp["印次"] - grp["休次"]
        grp = grp.sort_values("淨值(印-休)", ascending=False).reset_index(drop=True)
        return grp
    except Exception as _e:
        return str(_e)   # 回傳錯誤字串，UI 可顯示

def save_schedule_stats(df):
    """把統計表重建為歷史 rows 並整批推送到雲端（清空重建）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    try:
        rows = []
        for _, r in df.iterrows():
            card = str(r["卡號"]).strip()
            name = str(r["姓名"]).strip()
            n_print = max(0, int(r["印次"]))
            n_rest  = max(0, int(r["休次"]))
            for i in range(n_print):
                rows.append([f"統計-印{i+1:02d}", card, name, "印", ""])
            for i in range(n_rest):
                rows.append([f"統計-休{i+1:02d}", card, name, "休", ""])
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAllScheduleHistory", "secret": WRITE_SECRET,
                                   "rows": rows},
                             timeout=30)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

def fetch_schedule_history_raw():
    """從雲端排班歷史取得原始明細 → DataFrame(週次/卡號/姓名/狀態/治療日)，或 None。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getScheduleHistory", "secret": WRITE_SECRET},
                             timeout=30)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None
        rows = d["rows"]
        if len(rows) < 2: return None
        df = pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
        df["狀態"] = df["狀態"].str.strip()
        return df[df["狀態"].isin(["印","休"])].reset_index(drop=True)
    except Exception as _e:
        return str(_e)

def fetch_members_cloud():
    """從 GS 雲端讀取組員名單 → DataFrame(卡號/姓名)，或 None。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getMembers", "secret": WRITE_SECRET},
                             timeout=20)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None
        rows = d["rows"]
        if len(rows) < 2: return None
        return pd.DataFrame(rows[1:], columns=[str(x) for x in rows[0]])
    except Exception:
        return None

def fetch_members_as_csv():
    """讀雲端組員名單並轉為 CSV bytes（供 config_override 注入排班/稽核.py）。"""
    df = fetch_members_cloud()
    if df is None: return None
    return df.to_csv(index=False).encode("utf-8-sig")

def save_members_cloud(df):
    """把組員名單 DataFrame 存回 GS 雲端。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    try:
        rows = [[str(r.get("卡號","")).strip(), str(r.get("姓名","")).strip()]
                for _, r in df.iterrows() if str(r.get("姓名","")).strip()]
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setMembers", "secret": WRITE_SECRET, "rows": rows},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

# ── 休診日：雲端「休診日」分頁是唯一來源（v3.42）────────────────
# 過年/連假這種「沒診、不上班」的日子，本來有兩份各自維護的清單：
#   ① webapp/休診日.csv        → 排班.py 的 prev_treat()，決定「印藥水日」往前推幾天
#   ② 藥水小幫手.gs 的 EXTRA_HOLIDAYS 陣列 → prevWorkday_()，決定「LINE 提醒日」往前推
# 改一邊不會同步到另一邊，兩邊一旦對不上，排班算出來的印藥水日跟 LINE 通知的日期
# 就會差一天——跟 v5.8 修掉的 off-by-one 是同一類災情，只是兩份清單目前剛好都是空的
# 所以還沒爆發。v3.42 起改成雲端「休診日」分頁當唯一來源，兩邊都讀它。
def fetch_holidays_cloud():
    """讀雲端「休診日」分頁 → (DataFrame[日期,說明], 錯誤訊息)。

    (df, "")   成功。⚠ df 可能是空的——「雲端目前沒有登記任何休診日」本身就是有效
               答案，**不可以**當成失敗而改用本機 CSV，否則又變回兩份清單各自為政。
    (None, msg) 真的讀不到（沒設定 URL/Secret、網路失敗、或 Apps Script 還停在
               v6.0 以前、不認得 getHolidays 這個 action）。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET:
        return None, "未設定 APPS_SCRIPT_URL / WRITE_SECRET"
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getHolidays", "secret": WRITE_SECRET},
                             timeout=20)
        d = resp.json()
        if not d.get("ok"):
            err = str(d.get("error", "GAS 回傳失敗"))
            if "unknown action" in err:
                err = ("Apps Script 還沒部署 v6.1（不認得 getHolidays）。"
                       "請把 藥水小幫手_完整版.gs 最新版貼進編輯器後「部署→管理部署→新版本」。")
            return None, err
        rows = d.get("rows") or []
        if len(rows) < 1:
            return pd.DataFrame(columns=["日期", "說明"]), ""
        hdr = [str(x).strip() for x in rows[0]]
        out = []
        for r in rows[1:]:
            # Sheets 會把日期存成日期型別，GAS 序列化成 UTC ISO 字串（見 gs_date_to_ymd
            # 的說明），直接截前 10 碼會少一天，一律走同一支轉換函式。
            ymd = gs_date_to_ymd(r[0]) if len(r) > 0 else ""
            memo = str(r[1]).strip() if len(r) > 1 else ""
            if str(ymd).strip():
                out.append({"日期": str(ymd).strip(), "說明": memo})
        return pd.DataFrame(out, columns=["日期", "說明"]), ""
    except Exception as _e:
        return None, str(_e)

HOLIDAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def fetch_holidays_as_csv():
    """雲端休診日 → 休診日.csv bytes（給 config_override 注入 排班.py/稽核.py）。

    回傳 (csv_bytes, 錯誤訊息)；讀不到時 csv_bytes 為 None，呼叫端要顯示警告
    （不要靜默改用本機備份，那正是這次要根治的問題）。
    """
    df, err = fetch_holidays_cloud()
    if df is None:
        return None, err
    buf = io.StringIO()
    buf.write("日期,說明\n")
    bad = []
    for _, r in df.iterrows():
        ymd = str(r.get("日期", "")).strip()
        if not ymd: continue
        if not HOLIDAY_RE.match(ymd):
            bad.append(ymd); continue        # 格式不對就不要餵進去，排班.py 也只會警告後略過
        memo = str(r.get("說明", "")).replace(",", "，").replace("\n", " ").strip()
        buf.write(f"{ymd},{memo}\n")
    warn = f"雲端休診日有 {len(bad)} 筆格式不對已略過：{'、'.join(bad)}" if bad else ""
    return buf.getvalue().encode("utf-8-sig"), warn

def save_holidays_cloud(df):
    """把休診日 DataFrame 存回雲端「休診日」分頁 → (ok, 寫入筆數, 錯誤訊息)。

    整批取代（不是「只補不蓋」）——休診日跟組員名單一樣，真的會需要「刪除」
    （例如原本排定的補班日取消），只補不蓋會讓刪掉的日子復活。防呆改成走
    「表格編輯前一定先讀雲端現況」＋「本機 CSV 只有雲端全空時才能上傳」。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET:
        return False, 0, "未設定 APPS_SCRIPT_URL / WRITE_SECRET"
    try:
        rows, bad = [], []
        for _, r in df.iterrows():
            ymd = str(r.get("日期", "")).strip()
            if not ymd: continue
            if not HOLIDAY_RE.match(ymd):
                bad.append(ymd); continue
            rows.append([ymd, str(r.get("說明", "")).strip()])
        if bad:
            return False, 0, ("日期格式要像 2026-01-01（西元-月-日，補零）。"
                              f"這幾筆不合格式，沒有存出去：{'、'.join(bad)}")
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setHolidays", "secret": WRITE_SECRET,
                                   "rows": rows},
                             timeout=20)
        d = resp.json()
        if resp.ok and d.get("ok", False):
            return True, len(rows), ""
        err = str(d.get("error", "GAS 回傳失敗"))
        if "unknown action" in err:
            err = ("Apps Script 還沒部署 v6.1（不認得 setHolidays）。"
                   "請把 藥水小幫手_完整版.gs 最新版貼進編輯器後「部署→管理部署→新版本」。")
        return False, 0, err
    except Exception as _e:
        return False, 0, str(_e)

def fetch_audit_stats():
    """從 GS 稽核歷史彙總每人稽核/休次數 → DataFrame，或 None。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None
        rows = d["rows"]
        if len(rows) < 2: return None
        df = pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
        df["狀態"] = df["狀態"].str.strip()
        # 排除草稿和意見回饋，其餘（正常月份 + 統計重建記錄）都納入計算
        excl = (df["月份"].str.startswith("意見-") | (df["月份"] == "草稿"))
        valid = df[~excl & df["狀態"].isin(["稽核","休"])]
        if valid.empty: return pd.DataFrame(columns=["卡號","姓名","稽核次","休次","淨值(稽核-休)"])
        grp = valid.groupby(["卡號","姓名"])["狀態"].value_counts().unstack(fill_value=0)
        grp = grp.reindex(columns=["稽核","休"], fill_value=0).reset_index()
        grp.columns = ["卡號","姓名","稽核次","休次"]
        grp["稽核次"] = pd.to_numeric(grp["稽核次"], errors="coerce").fillna(0).astype(int)
        grp["休次"]   = pd.to_numeric(grp["休次"],   errors="coerce").fillna(0).astype(int)
        grp["淨值(稽核-休)"] = grp["稽核次"] - grp["休次"]
        return grp.sort_values("淨值(稽核-休)", ascending=False).reset_index(drop=True)
    except Exception as _e:
        return str(_e)

def save_audit_stats(df):
    """把稽核統計表重建為歷史 rows 並整批推送到 GS（清空重建）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    try:
        rows = []
        for _, r in df.iterrows():
            card = str(r["卡號"]).strip()
            name = str(r["姓名"]).strip()
            for i in range(max(0, int(r["稽核次"]))):
                rows.append([f"統計-稽{i+1:02d}", card, name, "稽核", ""])
            for i in range(max(0, int(r["休次"]))):
                rows.append([f"統計-休{i+1:02d}", card, name, "休", ""])
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAllAuditHistory", "secret": WRITE_SECRET,
                                   "rows": rows},
                             timeout=30)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

def fetch_latest_audit_result():
    """從 GS 稽核歷史讀取最新一個月的名單明細（稽核者含位置、休息者列出）。
    回傳 (月份str, DataFrame) 或 (None, None) 或 (None, 錯誤字串)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None, None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=30)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None, None
        rows = d["rows"]
        if len(rows) < 2: return None, None
        df = pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
        excl = (df["月份"].str.startswith("意見-") |
                df["月份"].str.startswith("統計-") |
                (df["月份"] == "草稿"))
        valid = df[~excl & df["狀態"].isin(["稽核","休"])].copy()
        if valid.empty: return None, None
        latest = sorted(valid["月份"].unique())[-1]   # 字典排序，115-07 > 115-06 > 114-12
        result = valid[valid["月份"] == latest][["姓名","狀態","位置"]].reset_index(drop=True)
        return latest, result
    except Exception as _e:
        return None, str(_e)

def _sync_to_gs(action, rows, timeout=30, retries=2):
    """送資料到 GS，逾時自動重試。回傳 (ok, n, err_msg)。"""
    last_err = ""
    for attempt in range(retries):
        try:
            resp = requests.post(APPS_SCRIPT_URL,
                                 json={"action": action, "secret": WRITE_SECRET, "rows": rows},
                                 timeout=timeout)
            d = resp.json()
            if resp.ok and d.get("ok", False):
                return True, len(rows), ""
            last_err = d.get("error", "GAS 回傳失敗")
            break
        except requests.exceptions.Timeout:
            last_err = f"連線逾時（第{attempt+1}次，共{retries}次）"
        except Exception as e:
            last_err = str(e)
            break
    return False, 0, last_err

def sync_schedule_history_from_csv():
    """把本機排班紀錄.csv 裡「雲端目前沒有的週次」補進雲端排班歷史。

    v3.38 前：整批覆蓋雲端（setAllScheduleHistory 是 clearContents 重建），若本機 CSV
    落後（雲端有、CSV 沒有的新週次），一按就會把雲端較新的資料蓋掉——2026-07-20 凌晨
    實際發生過一次，蓋掉了剛送出的 0720~0726 那 15 筆。
    v3.38 起：先讀雲端現況，只把「本機有、雲端沒有」的週次補上去，雲端既有的週次原封
    不動地保留、一起送回去（GAS 端仍是整批 setAllScheduleHistory，但送出的內容已經是
    「雲端原有 + 本機獨有」的合併結果，不會遺失雲端較新的資料）。
    回傳 (ok, 新補上的筆數, err)。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, 0, "未設定 URL/Secret"
    csv_path = os.path.join(HERE, "排班紀錄.csv")
    if not os.path.exists(csv_path): return False, 0, "找不到排班紀錄.csv"
    try:
        df_local = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        cloud_df = fetch_schedule_history_raw()
        if isinstance(cloud_df, str):
            return False, 0, f"讀取雲端現況失敗，為安全起見取消同步：{cloud_df}"
        cloud_weeks = set(cloud_df["週次"].astype(str)) if cloud_df is not None else set()
        missing = df_local[~df_local["週次"].astype(str).isin(cloud_weeks)]
        if missing.empty:
            return True, 0, ""
        combined = (pd.concat([cloud_df, missing], ignore_index=True)
                    if cloud_df is not None and not cloud_df.empty else missing)
        rows = [list(r) for _, r in combined.iterrows()]
        ok, _, err = _sync_to_gs("setAllScheduleHistory", rows)
        return ok, (len(missing) if ok else 0), err
    except Exception as e:
        return False, 0, str(e)

def fetch_audit_history_full_raw():
    """從雲端稽核歷史取得完整明細（含草稿/意見等特殊列，不篩選）→ DataFrame，或 None/錯誤字串。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=30)
        d = resp.json()
        if not d.get("ok"): return None
        rows = d.get("rows") or []
        if len(rows) < 2: return pd.DataFrame(columns=["月份","卡號","姓名","狀態","位置"])
        return pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
    except Exception as e:
        return str(e)

def sync_audit_history_from_csv():
    """把本機稽核紀錄.csv 裡「雲端目前沒有的月份」補進雲端稽核歷史（同 v3.38 排班版邏輯，
    不覆蓋雲端既有資料，見 sync_schedule_history_from_csv 說明）。回傳 (ok, 新補上的筆數, err)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, 0, "未設定 URL/Secret"
    csv_path = os.path.join(HERE, "稽核紀錄.csv")
    if not os.path.exists(csv_path): return False, 0, "找不到稽核紀錄.csv"
    try:
        df_local = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        cloud_df = fetch_audit_history_full_raw()
        if isinstance(cloud_df, str):
            return False, 0, f"讀取雲端現況失敗，為安全起見取消同步：{cloud_df}"
        cloud_months = set(cloud_df["月份"].astype(str)) if cloud_df is not None else set()
        missing = df_local[~df_local["月份"].astype(str).isin(cloud_months)]
        if missing.empty:
            return True, 0, ""
        # v3.41：送出前先把「草稿」與「意見-」那些特殊列濾掉。GAS 端的
        # setAllAuditHistory 本來就會自己保留這些列（keptAud），我們這邊若又原封不動
        # 送回去，同一批草稿/意見會被寫兩次 → 列數翻倍（實測按1次：草稿1→2筆、
        # 意見1→2筆）。不會掉資料，但會累積雜訊、回饋清單出現重複。
        if cloud_df is not None and not cloud_df.empty:
            _mon = cloud_df["月份"].astype(str)
            cloud_df = cloud_df[~(_mon.eq("草稿") | _mon.str.startswith("意見-"))]
        combined = (pd.concat([cloud_df, missing], ignore_index=True)
                    if cloud_df is not None and not cloud_df.empty else missing)
        rows = [list(r) for _, r in combined.iterrows()]
        ok, _, err = _sync_to_gs("setAllAuditHistory", rows)
        return ok, (len(missing) if ok else 0), err
    except Exception as e:
        return False, 0, str(e)

def _reconstruct_disp_from_rows(rows):
    """從 cloud_rows 重建簡化版 disp DataFrame（日期×區 的 pivot，供草稿檢視）。
    rows 格式：[印日期, 區, 姓名] 或新格式 [印日期, 區, 姓名, 🔺, 治療欄]，只取前三欄。
    同區同印日多人時用「、」串接，不再只留第一個。
    """
    if not rows: return pd.DataFrame()
    try:
        cleaned = [[gs_date_to_ymd(r[0]), str(r[1]), str(r[2])] for r in rows]
        df = pd.DataFrame(cleaned, columns=["印日期","區","姓名"])
        pivot = df.pivot_table(index="區", columns="印日期", values="姓名",
                               aggfunc=lambda x: "、".join(x.dropna())).fillna("")
        pivot.index.name = None; pivot.columns.name = None
        return pivot
    except Exception:
        return pd.DataFrame([[str(r[0]), str(r[1]), str(r[2])] for r in rows],
                             columns=["印日期","區","姓名"])

# ── 印藥水定案本機草稿（app 重開可恢復）────────────────────
WEEK_DRAFT_PATH = os.path.join(HERE, "last_week_draft.json")

def _save_week_draft(rows, sheet0, disp_df):
    try:
        payload = {
            "rows": [[str(v) for v in r] for r in rows],
            "sheet0": str(sheet0),
            "disp": {
                "columns": [str(c) for c in disp_df.columns],
                "index":   [str(i) for i in disp_df.index],
                "data":    [[("" if str(v) in ("nan","None") else str(v))
                             for v in row] for row in disp_df.values]
            }
        }
        with open(WEEK_DRAFT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass

def _load_week_draft():
    if not os.path.exists(WEEK_DRAFT_PATH): return None
    try:
        with open(WEEK_DRAFT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _clear_week_draft():
    try:
        if os.path.exists(WEEK_DRAFT_PATH): os.remove(WEEK_DRAFT_PATH)
    except Exception:
        pass


# ── LINE 群組公告文字格式 ─────────────────────────────────
def _build_line_txt(rows, disp_df=None):
    """LINE 群組公告：左欄顯示印藥水日期，每治療日獨立一列（不碰撞）。

    disp_df: 定案 DataFrame（index=一區/二區, columns=治療日欄標）。
    提供 disp_df 時從格子內容（如「張雅雯(7/1印)」）取得印藥水日期顯示於左欄。
    """
    from datetime import datetime as _dt
    DOW = {0:"週一",1:"週二",2:"週三",3:"週四",4:"週五",5:"週六",6:"週日"}

    yr_val = pd.Timestamp.now().year
    for _r in rows:
        try: yr_val = int(str(_r[0]).split('-')[0]); break
        except Exception: pass

    def _parse_col(col_str):
        m = re.search(r'(\d{1,2})/(\d{1,2})', str(col_str))
        if m: return yr_val, int(m.group(1)), int(m.group(2))
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(col_str))
        if m: return int(m.group(1)), int(m.group(2)), int(m.group(3))
        return None, None, None

    def _dstr(yr, mo, dy): return f"{yr}-{mo:02d}-{dy:02d}"

    def fmt(d_str):
        d = _dt.strptime(d_str, "%Y-%m-%d")
        return f"{DOW[d.weekday()]} {d.month:02d}/{d.day:02d}"  # 月日補零：07/06，確保等寬

    # treats: list of {t: 治療日str, p: 印藥水日str, a: {area: name}}
    # ⚠ v3.41 修正：每一「格」各自帶自己的印藥水日，不再一整欄共用一個。
    # 舊寫法用 `print_str is None` 只取該治療日欄「第一個」有(印)標注的日期，然後把
    # 整欄兩個區的人都算成那一天——但同一個治療日的一區/二區常常一個是白班(印T-1)、
    # 一個是小夜(印T-2)，印藥水日本來就不同天。實測4週48人次錯9次(19%)，被寫晚的人
    # 會晚一天備藥水。注意：送GAS的「本週名單」(個人LINE提醒用)日期一直是對的，
    # 錯的只有貼到LINE群組的這份公告文字，所以會出現「個人提醒跟群組公告對不上」。
    treats = []

    if disp_df is not None:
        for col in disp_df.columns:
            t_yr, t_mo, t_dy = _parse_col(col)
            if t_yr is None: continue
            t_str = _dstr(t_yr, t_mo, t_dy)

            for area in ["一區","二區","三區"]:
                if area not in disp_df.index: continue
                v = str(disp_df.loc[area, col]).strip()
                if not v or v in ("nan","None","❌排不出"): continue
                nm_m = CELL_RE.match(v)
                if nm_m:
                    # 保留 🔺，但把「雙印」標記濾掉——group(4) 可能是「🔺雙印」，
                    # 直接串上去會讓公告出現「廖緗玗雙印」這種被污染的姓名（v3.41）
                    nm = nm_m.group(1).strip() + nm_m.group(4).replace("雙印", "").strip()
                    p_mo, p_dy = int(nm_m.group(2)), int(nm_m.group(3))
                    p_str = _dstr(t_yr, p_mo, p_dy)   # ← 這一格自己的印藥水日
                else:
                    nm = v.replace("雙印", "").strip()
                    p_str = t_str                     # 沒有(印)標注 → 退回用治療日
                if nm:
                    treats.append({"t": t_str, "p": p_str, "a": {area: nm}})
    else:
        # fallback：印藥水日分組，同一區同一天可能有多人，用 list 累積
        tmp = {}
        for r in rows:
            p_str, area, name = str(r[0]), str(r[1]), str(r[2])
            if not name or name in ("","❌排不出"): continue
            tmp.setdefault(p_str, {}).setdefault(area, []).append(name)
        for p_str in sorted(tmp):
            a = {area: "、".join(names) for area, names in tmp[p_str].items()}
            treats.append({"t": p_str, "p": p_str, "a": a})

    if not treats: return ""
    treats.sort(key=lambda x: x["t"])   # 依治療日排序

    # 標題用治療日範圍（說明這週涵蓋哪幾天）
    lines = [f"印藥水名單 (治療日 {fmt(treats[0]['t'])}~ {fmt(treats[-1]['t'])})", ""]

    # 依「印藥水日」合併輸出（不是依治療日）——不同治療日往前推剛好同一天印藥水時
    # （例如白班7/21治療日、小夜7/22治療日，往前推都是7/20），原本會各自出現一行、
    # 看起來像同一天印了兩次、容易誤會（2026-07-19、07-20兩次都有人反映看不懂），
    # 這裡先按印藥水日分組、同一天的人合併成一行。
    by_print = {}
    for e in treats:
        slot = by_print.setdefault(e["p"], {})
        for area, nm in e["a"].items():
            names = slot.setdefault(area, [])
            for nm_single in nm.split("、"):
                nm_single = nm_single.strip()
                if nm_single and nm_single not in names:
                    names.append(nm_single)

    for p_str in sorted(by_print):
        line = fmt(p_str)   # 左欄 = 印藥水日期
        for area in ["一區","二區","三區"]:
            names = by_print[p_str].get(area, [])
            if names: line += f"  {area}：{'、'.join(names)}"
        lines.append(line)

    roster = _load_roster_full()
    if roster:
        printing = set()
        for e in treats:
            # 去掉 🔺 再比對；同一格可能有多人用「、」串接，拆開各別加入
            for nm_joined in e["a"].values():
                for nm_single in nm_joined.split("、"):
                    printing.add(re.sub(r'🔺', '', nm_single).strip())
        resting = [m["姓名"] for m in roster if m["姓名"] not in printing]
        if resting:
            lines += ["", "休息：" + "、".join(resting)]
    return "\n".join(lines)


# ── 💬 意見回饋：借用稽核歷史（特殊鍵「意見-時間」）存放，不動 LINE 程式 ──
APP_VER = "v3.43"
FEEDBACK_PREFIX = "意見-"

def push_feedback(step, detail, expect, urgency, who):
    """把一筆回饋寫進雲端（不影響排班/稽核：狀態欄非『稽核/休』故公平輪序會略過）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")   # 含微秒 → 每筆鍵唯一
    key = FEEDBACK_PREFIX + now
    blob = "問題：" + (detail or "").strip()
    if (expect or "").strip(): blob += "｜期望：" + expect.strip()
    blob += "｜版本：" + APP_VER
    row = [key, (step or ""), (who or "").strip() or "(未留名)", (urgency or ""), blob]
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAuditResult", "secret": WRITE_SECRET,
                                   "key": key, "rows": [row]},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

def _mask_name(name):
    """公開檢視用：把留言者姓名換成固定亂碼（同一人代碼一樣，但看不出是誰）。"""
    name = (name or "").strip()
    if not name or name == "(未留名)":
        return "匿名"
    return "訪客#" + hashlib.md5(name.encode("utf-8")).hexdigest()[:4]

def fetch_feedback_list():
    """讀回所有回饋（稽核歷史裡 月份 以『意見-』開頭的列），新到舊。留言者以亂碼呈現。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return []
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        rows = resp.json().get("rows") or []
        if len(rows) < 2: return []
        hdr = [str(x).strip() for x in rows[0]]
        iM, iC, iN, iS, iP = (hdr.index("月份"), hdr.index("卡號"), hdr.index("姓名"),
                              hdr.index("狀態"), hdr.index("位置"))
        out = []
        for r in rows[1:]:
            k = str(r[iM]).strip()
            if not k.startswith(FEEDBACK_PREFIX): continue
            out.append({
                "時間": k[len(FEEDBACK_PREFIX):],
                "步驟": str(r[iC]).strip(),
                "急迫": str(r[iS]).strip(),
                "內容": str(r[iP]).strip(),
                "留言者": _mask_name(str(r[iN])),
            })
        out.reverse()   # 新的在最上面
        return out
    except Exception:
        return []

def fetch_latest_banbiao():
    """從雲端（Apps Script 讀 Gmail「班表」標籤的最新 Excel 附件）抓班表。
    回傳 (bytes, 說明) 或 (None, 錯誤訊息)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET:
        return None, "雲端尚未設定"
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getLatestBanbiao", "secret": WRITE_SECRET},
                             timeout=60)
        d = resp.json()
        if not d.get("ok"):
            return None, d.get("error", "未知錯誤")
        data = base64.b64decode(d["b64"])
        info = f'{d.get("filename","班表")}（{d.get("date","")}）'
        return data, info
    except Exception as e:
        return None, str(e)

def build_corrected_history(cloud_rows, sheet_name, prev_hist_bytes):
    """用玉繡實際定案（cloud_rows）覆蓋 排班.py 原排的歷史，確保公平輪序正確。
    cloud_rows: [[印日期, 區, 姓名], ...]
    prev_hist_bytes: 排班.py 寫的 排班紀錄.csv bytes（含本週舊資料，會被替換）
    """
    roster = _load_roster_names()
    if not roster: return prev_hist_bytes   # 讀不到名單就維持原版

    # 玉繡定案後實際印藥水的人（去掉空值）
    printed_names = {str(r[2]).strip() for r in cloud_rows if r[2]}

    # 讀舊歷史，移除本週（排班.py 版），保留其他週
    headers = ["週次","卡號","姓名","狀態","治療日"]
    existing = []
    if prev_hist_bytes:
        try:
            df_h = pd.read_csv(io.BytesIO(prev_hist_bytes), encoding="utf-8-sig",
                               dtype=str, keep_default_na=False)
            existing = df_h[df_h["週次"].astype(str) != str(sheet_name)].values.tolist()
        except Exception: pass

    # 依玉繡定案重建本週紀錄
    new_rows = []
    for name, card in roster.items():
        status = "印" if name in printed_names else "休"
        new_rows.append([sheet_name, card, name, status, ""])

    all_rows = existing + new_rows
    df_new = pd.DataFrame(all_rows, columns=headers)
    return df_new.to_csv(index=False).encode("utf-8-sig")


def build_corrected_audit_history(edited_ak, month_key, prev_hist_bytes):
    """用玉繡實際改過的稽核名單（edited_ak）覆蓋 稽核.py 原排的歷史。

    v3.41 新增。印藥水那邊早就有 build_corrected_history()（app.py 檔頭寫的
    「Fix1：公平歷史學玉繡實際決定，而非程式原排」），但**稽核這邊從來沒做過**：
    送出時 `ak_hist_b` 來自子行程原封不動的產出，而 LINE 通知用的是玉繡點格子改過的
    `edited_ak`，兩者來源不同、中間沒有任何同步。結果就是玉繡把某格從 A 改成 B →
    B 收到通知去稽核，雲端歷史卻記「A=稽核、B=休」，下個月 cost 對兩人各錯一格，
    而且會**逐月累積**——這正是「玉繡實際排的跟系統差異越來越大」的其中一個來源。

    edited_ak: DataFrame，欄位 區/組/班次/稽核者（稽核者可能帶「(跨區)」後綴）
    prev_hist_bytes: 稽核.py 寫的 稽核紀錄_輸出.csv bytes（本月那批會被替換）
    """
    roster = _load_roster_names()          # {姓名: 卡號}
    if not roster or edited_ak is None or edited_ak.empty:
        return prev_hist_bytes             # 讀不到名單/沒有編輯結果 → 維持原版

    headers = ["月份","卡號","姓名","狀態","位置"]
    # 玉繡定案後，每個人實際被分配到的位置（區/組/班次）
    pos_of = {}
    try:
        for _, r in edited_ak.iterrows():
            nm = re.sub(r'\(.*?\)', '', str(r.get("稽核者",""))).strip()   # 去掉「(跨區)」
            if not nm: continue
            pos_of[nm] = f"{str(r.get('區','')).strip()}/{str(r.get('組','')).strip()}/{str(r.get('班次','')).strip()}"
    except Exception:
        return prev_hist_bytes             # 欄位對不上就別亂改，維持原版

    # 讀舊歷史，移除本月（稽核.py 版），保留其他月
    existing = []
    if prev_hist_bytes:
        try:
            df_h = pd.read_csv(io.BytesIO(prev_hist_bytes), encoding="utf-8-sig",
                               dtype=str, keep_default_na=False)
            existing = df_h[df_h["月份"].astype(str) != str(month_key)].values.tolist()
        except Exception: pass

    new_rows = []
    for name, card in roster.items():
        if name in pos_of:
            new_rows.append([month_key, card, name, "稽核", pos_of[name]])
        else:
            new_rows.append([month_key, card, name, "休", ""])

    df_new = pd.DataFrame(existing + new_rows, columns=headers)
    return df_new.to_csv(index=False).encode("utf-8-sig")


# ── 雲端歷史：讀取 / 推送 ──────────────────────────────────
def fetch_history_csv(action):
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": action, "secret": WRITE_SECRET},
                             timeout=20)
        if resp.ok:
            data = resp.json()
            if data.get("ok") and data.get("rows"):
                rows = data["rows"]
                if len(rows) < 2: return None
                df = pd.DataFrame(rows[1:], columns=rows[0])
                return df.to_csv(index=False).encode("utf-8-sig")
    except Exception: pass
    return None

def push_history(action, hist_bytes, key):
    """回傳 (ok, n_rows, detail)：n_rows 是實際送出的筆數，detail 是失敗時的原因，
    方便診斷「回報成功但其實沒送資料」這種 GAS 端不驗證空陣列的狀況。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, 0, "未設定 APPS_SCRIPT_URL/WRITE_SECRET"
    if not hist_bytes: return False, 0, "hist_bytes 是空的(build_corrected_history 沒有產生資料，可能組員名單讀取失敗)"
    try:
        df = pd.read_csv(io.BytesIO(hist_bytes), encoding="utf-8-sig",
                          dtype=str, keep_default_na=False)
        key_col = df.columns[0]
        week_rows = df[df[key_col].astype(str) == str(key)].values.tolist()
        if not week_rows:
            return False, 0, f"key='{key}' 在資料裡完全比對不到任何列（key_col='{key_col}'），送出前就已經是 0 筆"
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": action, "secret": WRITE_SECRET,
                                   "key": key, "rows": week_rows},
                             timeout=20)
        rj = resp.json()
        ok = resp.ok and rj.get("ok", False)
        if ok:
            _parts = []
            if "before" in rj or "after" in rj:
                _parts.append(f"寫入前{rj.get('before','?')}列→寫入後{rj.get('after','?')}列")
            if "gotRows" in rj:
                _parts.append(f"GAS收到{rj.get('gotRows')}筆(送出{len(week_rows)}筆) key='{rj.get('gotKey','?')}'")
            if "ssId" in rj:
                _parts.append(f"寫入試算表: {rj.get('ssName','?')} (ID尾碼…{str(rj.get('ssId',''))[-8:]})")
            _detail = "GAS回報：" + "；".join(_parts) if _parts else ""
            return ok, len(week_rows), _detail
        return False, 0, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, 0, f"例外：{e}"

# Fix2：稽核送出後 LINE 通知稽核者
def send_audit_notices(month_key, audit_df):
    """從稽核名單 DataFrame 解析每人位置，呼叫 Apps Script 發 LINE 通知。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return 0, 0
    notices = []
    seen = set()
    for _, row in audit_df.iterrows():
        name = str(row.get("稽核者","")).strip().replace("(跨區)","")
        if not name or name == "❌排不出" or name in seen: continue
        seen.add(name)
        area  = str(row.get("區","")).strip()
        group = str(row.get("組","")).strip()
        band  = str(row.get("班次","")).strip()
        notices.append({"name": name, "position": f"{area}/{group}/{band}"})
    if not notices: return 0, 0, []
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action":"sendAuditNotice","secret":WRITE_SECRET,
                                   "month":month_key,"notices":notices},
                             timeout=20)
        if resp.ok:
            d = resp.json()
            # v3.43：GAS v6.2 起會檢查 LINE API 回應碼，把「真的沒送出去」的人另外
            # 回報在 failed/failedNames（舊版 GAS 沒有這兩個欄位，取不到就當 0/空）。
            return d.get("sent",0), d.get("miss",0), list(d.get("failedNames") or [])
    except Exception: pass
    return 0, 0, []


# ── 月稽核 Stage1：快速偵測班型 ──────────────────────────
def detect_shifts_quick(data, yy, mm):
    person = {}
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
        for sn in xls.sheet_names:
            try: df = pd.read_excel(io.BytesIO(data), sheet_name=sn, header=None)
            except Exception: continue
            hr = None
            for i in range(len(df)):
                c0 = str(df.iat[i,0]).strip() if not pd.isna(df.iat[i,0]) else ""
                c1 = str(df.iat[i,1]).strip() if not pd.isna(df.iat[i,1]) else ""
                if c0=="卡號" and c1=="姓名": hr=i; break
            if hr is None: continue
            blocks=[c for c in range(df.shape[1])
                    if (not pd.isna(df.iat[hr,c])) and str(df.iat[hr,c]).strip()=="類別"]
            bdates=[]
            for c in blocks:
                d=None
                for rr in range(hr-1,hr-4,-1):
                    if 0<=rr<len(df) and not pd.isna(df.iat[rr,c]):
                        v=df.iat[rr,c]
                        if isinstance(v,(pd.Timestamp,datetime)):
                            try: d=v.date(); break
                            except Exception: pass
                        else:
                            s=str(v).strip()
                            m_d=re.search(r"(\d{4})\D?(\d{1,2})\D(\d{1,2})",s)
                            if m_d:
                                try: d=date(int(m_d.group(1)),int(m_d.group(2)),int(m_d.group(3))); break
                                except Exception: pass
                bdates.append(d)
            for r in range(hr+1,len(df)):
                card=str(df.iat[r,0]).strip() if not pd.isna(df.iat[r,0]) else ""
                name=str(df.iat[r,1]).strip() if not pd.isna(df.iat[r,1]) else ""
                if not card and not name: continue
                key=card or name
                if key not in person: person[key]={"card":card,"name":name,"white":0,"night":0}
                for c,d in zip(blocks,bdates):
                    if d is None or d.year!=yy or d.month!=mm: continue
                    if c+1>=df.shape[1] or pd.isna(df.iat[r,c+1]): continue
                    shift=str(df.iat[r,c+1]).strip()
                    if shift.startswith("D"): person[key]["white"]+=1
                    elif shift.startswith("E"): person[key]["night"]+=1
    except Exception: pass
    result=[]
    for key,info in person.items():
        w,n=info["white"],info["night"]
        detected="❓" if w==0 and n==0 else ("白班" if w>=n else "夜班")
        result.append({"卡號":info["card"],"姓名":info["name"],"程式猜測":detected,"確認班型":detected})
    result.sort(key=lambda x:x["姓名"])
    return pd.DataFrame(result) if result else pd.DataFrame(columns=["卡號","姓名","程式猜測","確認班型"])


def _file_key(up): return f"{up.name}_{up.size}"


# ── Streamlit 設定 ─────────────────────────────────────────
st.set_page_config(page_title="透析藥水排班", page_icon="💊", layout="wide")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1UF-DjDcrIPDbp016vkIyV9zsLF6Qz5EBo6Bq-z6t-Js/edit"

try:
    APPS_SCRIPT_URL = st.secrets.get("APPS_SCRIPT_URL", "")
    WRITE_SECRET    = st.secrets.get("WRITE_SECRET", "")
except Exception:
    APPS_SCRIPT_URL = ""; WRITE_SECRET = ""

# ── 測試模式（小巫用）：排班演算法照常跑，但不寫雲端、不送 LINE ────
with st.sidebar:
    st.markdown("### ⚙️ 設定")
    TEST_MODE = st.toggle("🧪 測試模式（小巫用）", value=False,
                          help="開啟後可完整測試排班流程，但不會真的寫到雲端、也不會送 LINE 通知。")
    if TEST_MODE:
        st.warning("測試模式已開啟。\n\n所有「送到雲端」和「送通知」按鈕均為模擬，不影響正式資料。")

if TEST_MODE:
    st.error("🧪 測試模式 — 排班照常跑，但不寫雲端、不送 LINE。關掉左側開關即可切回正式模式。")

st.title("💊 透析藥水排班")
st.caption("上傳班表 Excel → 出名單(表格)。可直接點格子改人名。跨區標 🔺。")
st.caption("🟢 版本 v3.43（①休診日改為單一來源：過年/連假清單過去在 休診日.csv 與 LINE小幫手.gs 各存一份、改一邊不同步，兩邊對不上就會讓「排出來的印藥水日」跟「LINE通知的日期」差一天。現在統一存在雲端「休診日」分頁，排班演算法與 LINE 提醒都讀同一份，可在「📊 統計管理 → 🗓 休診日」直接編輯 ②稽核 LINE 通知若實際發送失敗，畫面會明確列出是誰沒收到，不再只顯示「已通知N人」）· 2026-08-01")

# ── 📊 首頁顯眼統計＋本機備份落後提醒（2026-07-20加，v3.38）─────────────
# 目的：2026-07-19~20那次「7/20資料被同步按鈕蓋掉」事件，玉繡是三週後才發現雲端資料
# 不對。這裡把「雲端目前累積筆數／最新一週」放在每次打開網頁都會看到的顯眼位置，
# 玉繡平常掃一眼「筆數有沒有變多、最新一週對不對」就能及早發現異常，不用等到查統計
# 才發現。同時主動比對本機git備份CSV是否落後於雲端，落後就直接顯示警告，不用等到
# 有人誤按「同步本機CSV→雲端」才發現備份是舊的。
@st.cache_data(ttl=300, show_spinner=False)
def _home_stats_snapshot():
    cloud_df = fetch_schedule_history_raw()
    if isinstance(cloud_df, str) or cloud_df is None or cloud_df.empty:
        return None
    def _latest_week(weeks):
        real = [w for w in weeks if re.match(r"^\d{4}~\d{4}$", str(w))]
        return real[-1] if real else None   # 取「最後一列」而非字串排序，避免跨年份排序錯誤
    n_cloud = len(cloud_df)
    latest_cloud_week = _latest_week(cloud_df["週次"].astype(str).tolist())
    n_local, latest_local_week = 0, None
    try:
        csv_path = os.path.join(HERE, "排班紀錄.csv")
        if os.path.exists(csv_path):
            df_local = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
            n_local = len(df_local)
            latest_local_week = _latest_week(df_local["週次"].astype(str).tolist())
    except Exception:
        pass
    return {"n_cloud": n_cloud, "latest_cloud_week": latest_cloud_week,
            "n_local": n_local, "latest_local_week": latest_local_week}

_snap = _home_stats_snapshot()
if _snap:
    _s1, _s2 = st.columns(2)
    _s1.metric("📊 雲端排班歷史累積筆數", _snap["n_cloud"])
    _s2.metric("📅 雲端最新一週", _snap["latest_cloud_week"] or "—")
    st.caption("💡 這兩個數字平常應該每週增加／更新。如果覺得好幾週沒變、或忽然變小，"
               "代表雲端資料可能被誤動過，請截圖跟AI反映，不要等到統計對不上才發現。")
    if (_snap["latest_local_week"] and _snap["latest_cloud_week"]
            and _snap["latest_local_week"] != _snap["latest_cloud_week"]):
        st.warning(f"⚠️ 本機git備份CSV最新只到「{_snap['latest_local_week']}」，比雲端的"
                   f"「{_snap['latest_cloud_week']}」舊——備份沒跟上雲端。目前「同步本機CSV→雲端」"
                   f"已經是「只補不蓋」，不會因此蓋掉雲端資料，但建議還是請AI把本機備份補到跟雲端一致。")
else:
    st.caption("（雲端統計暫時讀不到，不影響排班功能本身——如果一直讀不到，請告訴AI檢查一下）")

with st.expander("📖 第一次用？點我看「3 步驟」（給玉繡）", expanded=False):
    st.markdown("""
### 每週印藥水，只要 3 步：
**1️⃣ 上傳班表** → 選「🟦 每週印藥水」，把這週班表 Excel 傳上來。
**2️⃣ 排 + 微調** → 選「這一週」分頁 → 按「➡️ 排印藥水」。想換人就直接點格子改名字。
**3️⃣ 產生定案 → 送到雲端** → 按「✅ 產生定案」→「🚀 送到雲端」。完成！系統每晚自動 LINE 提醒，並記住這週誰印、誰休，下週排班更公平。

---
### 每月稽核（推薦「⚡ 快速點選」，免上傳）：
**1️⃣ 切換模式** → 上方選「🟩 每月稽核」→ 稽核方式留在「⚡ 快速點選」，選好「年」「月」。
**2️⃣ 點選白/夜＋區** → 畫面列出組員，系統已帶出上個月的設定；只要改這個月有變動的人，點一下白班/小夜、一區/二區即可。
　💾 只填一半沒關係——按「**暫存草稿**」存起來，明天打開會自動接續填。
**3️⃣ 排稽核** → 按「✅ 排稽核（快速）」。
**4️⃣ 送到雲端** → 名單排出來後按「🚀 送稽核結果到雲端」。每位稽核者馬上收到 LINE 通知，告訴他們「這個月負責哪一班稽核」。

> 也可改用「📤 上傳班表分析」：傳這個月的週班表 Excel，系統自己猜白/夜＋區，你再確認。班表要「Excel 檔本人」，截圖不行。
""")

# ── 🔊 語音導覽（點按鈕，用瀏覽器內建的聲音直接念出來，免音檔）──────────
_VOICE_YAO = (
    "玉繡你好。我們一步一步來，不用緊張。"
    "第一步，先打開排班網頁。如果畫面在睡覺、黑黑的，就點一下把它叫醒，等它跑一下。"
    "打開以後，看上面，選每週印藥水那個藍色的。"
    "接著，按上傳班表，把這個禮拜的班表，Excel 檔，傳上去。記得，要 Excel 檔本人，截圖不行喔。"
    "傳好以後，選這一週的分頁。通常系統會自己選好最接近今天的，你看一下對不對就好。"
    "然後，按排印藥水，等它幾秒鐘。"
    "等一下，就會跑出一張名單表格。如果想換人，直接點那一格，把名字改掉就好。"
    "改好以後，按產生定案。"
    "最後，按送到雲端。看到氣球飛出來，就成功囉。"
    "這樣就好了。系統每次都會記住這週誰印、誰休息，下次排班會自動讓印比較少的人先印，越排越公平。"
    "你不用再做別的事，輕鬆一下。"
)
_VOICE_JI = (
    "玉繡你好。這個更簡單，連班表都不用傳喔。"
    "第一步，一樣先打開排班網頁，在睡的話點一下叫醒它。"
    "打開以後，看上面，選每月稽核那個綠色的。"
    "下面會出現稽核方式，讓它停在快速點選就好，不用上傳東西。"
    "接著，選好年跟月。"
    "下面就會跑出組員的名單。系統會自動幫你帶上個月的設定。"
    "你只要看每一個人，是白班還是小夜，是一區還是二區。這個月有變動的，點一下改；沒變的就不用動。"
    "如果一下子填不完，沒關係，按暫存草稿，明天打開它會自動幫你帶回來，接著填就好。"
    "都確認好了，按排稽核。"
    "等一下，就會跑出這個月的稽核名單。想換人，一樣直接點格子改。"
    "最後，按送稽核結果到雲端。每一位稽核的人，就會收到 LINE 通知。"
    "這樣就完成囉。你做得很好，放輕鬆。"
)
with st.expander("🔊 語音導覽（不會用？點一下，手機念給你聽）", expanded=False):
    _btn = ("padding:14px 18px;margin:6px;border:none;border-radius:12px;"
            "font-size:18px;color:#fff;cursor:pointer;")
    _voice_html = """
    <div style="font-family:-apple-system,'PingFang TC',sans-serif;text-align:center">
      <button style="BTN background:#2563eb" onclick="sayIt(YAO)">🔵 印藥水導覽</button>
      <button style="BTN background:#16a34a" onclick="sayIt(JI)">🟢 稽核導覽</button>
      <button style="BTN background:#6b7280" onclick="stopAll()">⏹ 停止</button>
      <p style="color:#666;font-size:13px;margin-top:8px">點藍色聽「印藥水」、綠色聽「稽核」；正常語速、每句之間會停一下讓你跟著做。要停就按停止。</p>
    </div>
    <script>
      var YAO = __YAO__;
      var JI  = __JI__;
      var _stop = false;
      function _speakSeq(arr, i){
        if(_stop || i >= arr.length){ return; }
        var u = new SpeechSynthesisUtterance(arr[i]);
        u.lang = 'zh-TW';
        u.rate = 1.0;                                   // 正常語速
        u.onend = function(){
          // 有動作的句子（按/選/傳/點/改/存/送）多停一下，讓人來得及做
          var gap = /[按選傳點改存送]/.test(arr[i]) ? 4500 : 2500;
          setTimeout(function(){ _speakSeq(arr, i+1); }, gap);
        };
        window.speechSynthesis.speak(u);
      }
      function sayIt(t){
        _stop = false;
        try{ window.speechSynthesis.cancel(); }catch(e){}
        var parts = t.split('。');
        var arr = [];
        for(var k=0;k<parts.length;k++){
          var s = parts[k].replace(/^\\s+|\\s+$/g,'');
          if(s.length>0){ arr.push(s + '。'); }
        }
        _speakSeq(arr, 0);
      }
      function stopAll(){ _stop = true; try{ window.speechSynthesis.cancel(); }catch(e){} }
    </script>
    """
    _voice_html = (_voice_html
                   .replace("BTN", _btn)
                   .replace("__YAO__", json.dumps(_VOICE_YAO))
                   .replace("__JI__", json.dumps(_VOICE_JI)))
    components.html(_voice_html, height=175)

# ── 💬 回報問題／給建議（誰都能填，存到雲端給管理者看）──────────────
with st.expander("💬 有問題？回報一下（會存起來，大家都看得到）", expanded=False):
    st.caption("不用很會講～照下面選一選、簡單打幾個字就好。送出前可以先看下面「📋 大家回報過的問題」，看看是不是有人提過了。")
    fb_step = st.selectbox("① 你卡在哪一步？",
        ["上傳班表", "排印藥水", "微調名單", "送到雲端",
         "稽核－點選白夜/區", "暫存草稿", "收不到 LINE 通知", "語音導覽", "其他／不確定"],
        key="fb_step")
    fb_detail = st.text_area("② 發生什麼事？（你看到什麼、按了什麼、畫面寫什麼）", key="fb_detail")
    fb_expect = st.text_input("③ 你希望它變怎樣？（可不填）", key="fb_expect")
    fb_urg = st.radio("④ 急不急？", ["還好", "有點急", "很急"], horizontal=True, key="fb_urg")
    fb_who = st.text_input("⑤ 你的名字（可不填）", key="fb_who")
    if st.button("📨 送出回報", type="primary", key="fb_send"):
        if not fb_detail.strip():
            st.warning("請至少在 ② 簡單描述一下發生什麼事 🙏")
        elif not (APPS_SCRIPT_URL and WRITE_SECRET):
            st.error("雲端尚未設定，無法送出。")
        elif push_feedback(fb_step, fb_detail, fb_expect, fb_urg, fb_who):
            st.success("✅ 已送出！謝謝你的回報，我們看到會處理 🙏")
            st.balloons()
        else:
            st.error("送出失敗，請稍後再試。")

# ── 📋 大家回報過的問題（公開；名字以亂碼呈現保護隱私；按「載入」才去抓）──
with st.expander("📋 大家回報過的問題（公開・看看有沒有人提過）", expanded=False):
    st.caption("名字會用亂碼遮起來，看不出是誰。你可以用「時間／內容」認出自己那筆。")
    if st.button("🔄 載入回報", key="fb_load"):
        st.session_state["_fbs"] = fetch_feedback_list()
    if "_fbs" in st.session_state:
        fbs = st.session_state["_fbs"]
        if not fbs:
            st.info("目前還沒有任何回報。")
        else:
            st.caption(f"共 {len(fbs)} 則（新到舊）")
            st.dataframe(pd.DataFrame(fbs), use_container_width=True, hide_index=True)

st.markdown("#### 1️⃣ 選種類")
mode = st.radio("要排哪一種？", ["🟦 每週印藥水", "🟩 每月稽核", "📊 統計管理"], horizontal=True)

# 每月稽核可選「快速點選（免上傳）」或「上傳班表分析」；每週印藥水可選雲端自動抓或自己上傳
audit_quick = False
week_cloud = False
if mode.startswith("📊"):
    pass   # 統計管理不需要上傳
elif mode.startswith("🟩"):
    method = st.radio("稽核方式", ["⚡ 快速點選（免上傳 Excel，推薦）", "📤 上傳班表分析"],
                      horizontal=True)
    audit_quick = method.startswith("⚡")
else:
    src = st.radio("班表從哪來？", ["📥 用雲端最新班表（免上傳，推薦）", "📤 自己上傳 Excel"],
                   horizontal=True)
    week_cloud = src.startswith("📥")

data = None; sheets = []
if mode.startswith("📊"):
    pass   # 不需要 data
elif mode.startswith("🟦") and week_cloud:
    # 從雲端 Gmail 自動抓最新班表（文書把班表寄進來後，這裡一鍵抓）
    if st.button("📥 抓取雲端最新班表", type="primary"):
        with st.spinner("從雲端抓最新班表中…"):
            _b, _info = fetch_latest_banbiao()
        if _b is None:
            st.error("抓不到雲端班表：" + _info + "（你也可以改選『自己上傳』）")
        else:
            st.session_state["cloud_banbiao"] = (_b, _info)
            # 只清排班輸出，保留上次定案（cloud_rows/disp），auto-apply 才能套回
            st.session_state.pop("yao", None)
            st.session_state.pop("yao_edit", None)
    if "cloud_banbiao" in st.session_state:
        data, _info = st.session_state["cloud_banbiao"]
        st.success("✅ 已載入雲端班表：" + _info)
        try:
            sheets = pd.ExcelFile(io.BytesIO(data)).sheet_names
        except Exception as e:
            st.error(f"讀不到班表分頁：{e}"); st.stop()
    else:
        st.info("👆 按「📥 抓取雲端最新班表」，把文書寄進來的最新班表抓進來。")
        st.stop()
elif not audit_quick:                     # 自己上傳（每週印藥水 / 上傳班表稽核）
    up = st.file_uploader("上傳班表 Excel（.xls / .xlsx）", type=["xls","xlsx"])
    if not up:
        st.info("👆 先上傳班表 Excel（含每人每天班別/床號的那種檔）。截圖不行喔！")
        st.stop()
    fk = _file_key(up)
    if st.session_state.get("_last_file") != fk:
        for k in ["yao","cloud_rows","cloud_disp","cloud_sheet0","ak","ak_shifts","ak_month_key","yao_edit"]:
            st.session_state.pop(k, None)
        st.session_state["_last_file"] = fk
    data = up.read()
    try:
        sheets = pd.ExcelFile(io.BytesIO(data)).sheet_names
    except Exception as e:
        st.error(f"讀不到班表分頁：{e}"); st.stop()


# ═══════════════════════ 每週印藥水 ═══════════════════════
if mode.startswith("🟦"):

    # ── 📬 自動偵測雲端草稿（首次進入印藥水模式時）──────────
    if "cloud_rows" not in st.session_state and APPS_SCRIPT_URL and WRITE_SECRET:
        if "week_draft_auto" not in st.session_state:
            with st.spinner("自動偵測雲端草稿…"):
                _ar, _as = fetch_week_draft()
            st.session_state["week_draft_auto"] = (_ar, _as) if _ar else None
        _pending = st.session_state.get("week_draft_auto")
        if _pending:
            _ar, _as = _pending
            st.info(f"📬 偵測到玉繡的排班草稿（{_as}），要載入確認嗎？")
            _dc1, _dc2 = st.columns(2)
            if _dc1.button("✅ 載入草稿", key="auto_draft_load"):
                st.session_state["cloud_rows"]   = _ar
                st.session_state["cloud_disp"]   = _reconstruct_disp_from_rows(_ar)
                st.session_state["cloud_sheet0"] = _as
                st.session_state["cloud_rows_source"] = "draft"
                st.session_state.pop("week_draft_auto", None)
                st.rerun()
            if _dc2.button("✕ 略過", key="auto_draft_skip"):
                st.session_state["week_draft_auto"] = None
                st.rerun()

    # 草稿恢復：關掉 app 再回來，顯示上次定案
    if "cloud_rows" not in st.session_state:
        _wd = _load_week_draft()
        if _wd:
            st.info(f"📂 找到上次的定案（{_wd.get('sheet0','')}），要恢復嗎？")
            _cy, _cn = st.columns(2)
            if _cy.button("📋 載入草稿（確認後再送雲端）"):
                try:
                    _d = _wd["disp"]
                    st.session_state["cloud_rows"]   = _wd["rows"]
                    st.session_state["cloud_disp"]   = pd.DataFrame(
                        _d["data"], index=_d["index"], columns=_d["columns"])
                    st.session_state["cloud_sheet0"] = _wd["sheet0"]
                    st.session_state["cloud_rows_source"] = "draft"
                    st.rerun()
                except Exception as _e:
                    st.error(f"恢復失敗：{_e}")
            if _cn.button("❌ 不用，重新排"):
                _clear_week_draft(); st.rerun()

    # 正常排班流程（需要班表資料）
    if data is not None:
        st.markdown("#### 2️⃣ 選這一週 → 排班 → 微調")
        best = _best_sheet_index(sheets)
        sheet = st.selectbox("選「這一週」的分頁", sheets, index=best)

        with st.expander("⚙️ 本週特殊設定（選填）"):
            force_names_raw = st.text_area(
                "本週放假但可印藥水的人（一行一個姓名，不填則照班別自動判斷）",
                value=st.session_state.get("force_print_names",""),
                placeholder="例：\n黃怡璇\n潘冠秀",
                help="班別看起來是假（特休/公假等）但玉繡確認可以印的人，填在這裡就會被排入候選。"
                     "建議打全名最保險；只打名字（例：怡璇）也可以，但如果打錯字、對不到人，"
                     "畫面下方會跳警告告訴你哪一筆沒生效。"
            )
            st.session_state["force_print_names"] = force_names_raw

        if st.button("➡️ 排印藥水", type="primary"):
            with st.spinner("讀取雲端歷史 + 排班中…"):
                config_overrides = {}
                if APPS_SCRIPT_URL and WRITE_SECRET:
                    # v3.41：讀不到雲端資料時要明講。舊版 `if hist_csv:` 沒有 else，
                    # 抓失敗就靜默改用 repo 裡那份「已知落後」的本機備份算公平分數，
                    # 畫面完全沒提示（首頁自己都在警告本機備份比雲端舊）。
                    hist_csv = fetch_history_csv("getScheduleHistory")
                    if hist_csv: config_overrides["排班紀錄.csv"] = hist_csv
                    else: st.error("⚠️ 讀不到雲端『排班歷史』，這次會改用本機舊備份算公平分數，"
                                   "結果可能不準！請確認網路後重新排一次。")
                    mem_csv = fetch_members_as_csv()
                    if mem_csv: config_overrides["組員名單.csv"] = mem_csv
                    else: st.warning("⚠️ 讀不到雲端『組員名單』，改用本機備份（若最近有人入組/退組可能不準）。")
                    # v3.42：休診日改吃雲端「休診日」分頁（跟 LINE 小幫手 prevWorkday_
                    # 讀的是同一份），確保「排班算的印藥水日」跟「LINE 提醒的日期」
                    # 用同一組連假清單。讀不到要明講，不能靜默用本機備份——那正是
                    # 這次要根治的「兩份清單各自維護」問題。
                    hol_csv, hol_err = fetch_holidays_as_csv()
                    if hol_csv is not None:
                        config_overrides["休診日.csv"] = hol_csv
                        if hol_err: st.warning(f"⚠️ {hol_err}（請到「📊 統計管理 → 🗓 休診日」修正）")
                    else:
                        st.warning(f"⚠️ 讀不到雲端『休診日』（{hol_err}），這次改用本機 休診日.csv。"
                                   "如果最近有新增過年/連假，排出來的印藥水日可能跟 LINE 提醒對不上。")
                # 強制可印人員
                force_names = [n.strip() for n in force_names_raw.splitlines() if n.strip()]
                if force_names:
                    import io as _io
                    _fc = _io.StringIO(); _fc.write("姓名\n")
                    for _n in force_names: _fc.write(_n+"\n")
                    config_overrides["強制可印.csv"] = _fc.getvalue().encode("utf-8-sig")
                out, files, updated_hist = run_tool("排班.py", data, [sheet], config_overrides)
                st.session_state["yao"] = (out, files, sheet, updated_hist)
                st.session_state.pop("yao_edit", None)   # 清掉舊 editor 狀態，讓下面重新套定案

        if "yao" in st.session_state:
            out, files, sheet0, updated_hist = st.session_state["yao"]
            fn, b = pick(files, ".xlsx")
            if not b:
                st.error("沒產生名單，請看下方訊息。"); st.code(out); st.stop()
            grid  = pd.read_excel(io.BytesIO(b), index_col=0).fillna("")
            names, dates, marks = parse_grid(grid)
            yr     = year_from_cloud(files)      # 整週猜測值，僅供查不到時退回
            yr_map = year_map_from_cloud(files)   # v3.41：每一格自己的真實年份

            # 自動套回上次定案的修改（如顏凰任→張雅雯），避免重排後又要重改
            override_names = names.copy()
            _prev_rows  = st.session_state.get("cloud_rows", [])
            _prev_sheet = st.session_state.get("cloud_sheet0", "")
            _prev_disp  = st.session_state.get("cloud_disp")
            if _prev_rows and _prev_sheet == sheet0:
                for _cr in _prev_rows:
                    try:
                        _area = str(_cr[1]); _nm = str(_cr[2])
                        if not _nm or _nm in ("", "❌排不出"): continue
                        if (len(_cr) >= 5 and str(_cr[4])
                                and _area in override_names.index
                                and str(_cr[4]) in override_names.columns):
                            # 新格式：直接用存好的治療欄 key，不靠印日期推算，零碰撞
                            override_names.loc[_area, str(_cr[4])] = _nm
                        else:
                            # 舊格式（3欄）：向下相容，用印日期比對（同日多人時仍可能偏差）
                            _dstr = str(_cr[0])
                            _mo = int(_dstr.split('-')[1]); _dy = int(_dstr.split('-')[2])
                            _tgt = f"{_mo}/{_dy}"
                            for _col in dates.columns:
                                if str(dates.loc[_area, _col]).strip() == _tgt:
                                    override_names.loc[_area, _col] = _nm
                                    break
                    except Exception:
                        pass

                # 套回 🔺 標記：新格式從 rows[3]+rows[4] 讀，舊格式從 cloud_disp 讀
                _new_fmt = [cr for cr in _prev_rows if len(cr) >= 5]
                if _new_fmt:
                    for _area in marks.index:
                        for _col in marks.columns:
                            marks.loc[_area, _col] = ""
                    for _cr in _new_fmt:
                        try:
                            _area, _mk, _col = str(_cr[1]), str(_cr[3]), str(_cr[4])
                            if _area in marks.index and _col in marks.columns:
                                marks.loc[_area, _col] = _mk
                        except Exception:
                            pass
                elif _prev_disp is not None and not _prev_disp.empty:
                    for _r in marks.index:
                        for _c in marks.columns:
                            if _r in _prev_disp.index and _c in _prev_disp.columns:
                                marks.loc[_r, _c] = "🔺" if "🔺" in str(_prev_disp.loc[_r, _c]) else ""

            st.subheader(f"印藥水名單（{sheet0}）")
            st.caption("👇 想換人就直接點格子改名字（日期自動沿用）。改好再按「產生定案」。🔺 = 跨區借人")
            # 顯示用：名字後面加跨區標記 🔺
            display_names = override_names.copy()
            for _r in override_names.index:
                for _c in override_names.columns:
                    _mk = str(marks.loc[_r, _c]).strip() if (_r in marks.index and _c in marks.columns) else ""
                    if _mk:
                        display_names.loc[_r, _c] = str(override_names.loc[_r, _c]) + _mk
            _edit_T = st.data_editor(display_names.T, use_container_width=True, key="yao_edit")
            edited = _edit_T.T   # 轉回 area×day 給後續邏輯用
            for n in extract_notes(out): st.write("・" + n)

            # 公平累計統計（含本週預覽）
            _fair_lines = extract_fairness(out)
            if _fair_lines:
                with st.expander("📊 查看公平累計（印/休統計）", expanded=False):
                    st.caption("排序：印次越少 → 越優先被排到印。休次越多 → 下次更優先。")
                    st.code("\n".join(_fair_lines), language=None)

            st.markdown("#### 3️⃣ 產生定案 → 送到雲端")
            if st.button("✅ 產生定案（套用修改）", type="primary"):
                disp = edited.copy(); rows = []
                for r in edited.index:
                    for c in edited.columns:
                        raw_val = str(edited.loc[r,c])
                        # v3.41：除了 🔺，也要把「雙印」標記拿掉。排班.py 的 celltext()
                        # 在印第二次的格子後面會接「雙印」（例：余怜緣(7/16印)雙印），
                        # 舊版只 sub 掉 🔺，導致姓名欄變成「余怜緣雙印」送進雲端，造成
                        # 三重傷害：①GAS buildUserMap_ 用姓名精確比對 → 查不到 userId
                        # → 該人完全收不到LINE提醒 ②build_corrected_history 對不上名冊
                        # → 明明印兩次卻被記成「休」，公平輪序連錯兩格 ③LINE群組公告同時
                        # 把她列進「印」和「休息」。雙印雖不常見(26週1次)，一發生就是靜默三連錯。
                        nm = re.sub(r'🔺|雙印', '', raw_val).strip()  # 去掉顯示用標記
                        # 以 editor 內容為準：用戶有加 🔺 就保留，有去掉就不補
                        mk = "🔺" if "🔺" in raw_val else ""
                        dt = dates.loc[r,c]
                        if nm and nm != "❌排不出":
                            disp.loc[r,c] = f"{nm}({dt}印){mk}" if dt else f"{nm}{mk}"
                            if dt:
                                mo,dy = dt.split("/")
                                mo_i, dy_i = int(mo), int(dy)
                                # v3.41：先查每格真實年份表，查不到（例如手動改動導致對不上）才退回整週猜測值
                                _row_yr = yr_map.get((r, mo_i, dy_i), yr)
                                # 格式：[印日期, 區, 姓名, 🔺標記, 治療欄key]
                                rows.append([f"{_row_yr}-{mo_i:02d}-{dy_i:02d}", r, nm, mk, str(c)])
                        else:
                            disp.loc[r,c] = nm
                rows.sort(key=lambda x:(x[0],x[1]))
                st.session_state["cloud_rows"]   = rows
                st.session_state["cloud_disp"]   = disp
                st.session_state["cloud_sheet0"] = sheet0
                st.session_state["cloud_rows_source"] = "finalized"
                _save_week_draft(rows, sheet0, disp)   # 自動存本機
                if not TEST_MODE and APPS_SCRIPT_URL and WRITE_SECRET:
                    _draft_ok = push_week_draft(rows, sheet0)
                    if not _draft_ok:
                        st.warning("⚠️ 雲端草稿暫存失敗（網路問題？），請稍後按「💾 備份草稿」手動重試。")

    # 定案顯示（有定案就顯示，不管是否剛排班）
    if "cloud_rows" in st.session_state:
        rows   = st.session_state["cloud_rows"]
        disp   = st.session_state["cloud_disp"]
        sheet0 = st.session_state["cloud_sheet0"]
        _src = st.session_state.get("cloud_rows_source", "finalized")
        if _src == "draft":
            st.info("📋 已載入草稿（僅供確認，尚未送雲端）")
        else:
            st.success("✅ 定案完成！")
        if _src == "draft":
            # 草稿來源：用平鋪列表顯示，避免 pivot 因印日期不同而出現空白欄
            _flat = pd.DataFrame(
                [[gs_date_to_ymd(r[0]), str(r[1]), str(r[2])] for r in rows],
                columns=["印藥水日", "區", "姓名"]
            ).sort_values("印藥水日").reset_index(drop=True)
            st.dataframe(_flat, use_container_width=True, hide_index=True,
                         column_config={
                             "印藥水日": st.column_config.TextColumn("印藥水日", width="medium"),
                             "區":      st.column_config.TextColumn("區",      width="small"),
                             "姓名":    st.column_config.TextColumn("姓名",    width="medium"),
                         })
        else:
            st.dataframe(disp.T, use_container_width=True)   # 直式：日期當列，區當欄

        # 定案後顯示實際休息人員（依玉繡最終調整，非演算法原始結果）
        _roster_all = _load_roster_full()
        if _roster_all:
            _printing = {str(r[2]).strip() for r in rows if r[2]}
            _resting  = [m["姓名"] for m in _roster_all if m["姓名"] not in _printing]
            if _resting:
                st.info("😴 本週休息：" + "、".join(_resting))

        # 💾 暫存草稿：讓小巫可以讀取確認
        if TEST_MODE:
            if st.button("🧪 暫存草稿（測試模擬）", key="week_draft_test"):
                st.info("🧪 測試模式：模擬暫存成功，但沒有真的寫到雲端。")
        elif APPS_SCRIPT_URL and WRITE_SECRET:
            _wd1, _wd2 = st.columns(2)
            if _wd1.button("💾 備份草稿（小巫更新程式後可查看）", key="week_draft_save"):
                with st.spinner("暫存中…"):
                    _ok = push_week_draft(rows, sheet0)
                if _ok:
                    st.success("✅ 草稿已存到雲端！小巫可按「📥 讀取玉繡的排班草稿」來確認。")
                else:
                    st.error("暫存失敗，請稍後再試。")
            if _wd2.button("🗑 清除草稿", key="week_draft_clear"):
                if clear_week_draft_cloud():
                    st.success("✅ 草稿已清除。")
                else:
                    st.error("清除失敗。")

        # LINE 群組公告文字
        # 草稿來源不能傳 disp（pivot 用 aggfunc="first" 會丟失同區多人），直接走 rows fallback
        _line_txt = _build_line_txt(rows, disp_df=(None if _src == "draft" else disp))
        if _line_txt:
            st.markdown("**📋 LINE 群組公告格式**")
            st.caption("長按複製，或按下方按鈕下載 txt 傳 LINE")
            st.code(_line_txt, language=None)
            st.download_button("⬇️ 下載 txt 傳 LINE 群組",
                               _line_txt.encode("utf-8"),
                               file_name=f"印藥水名單_{sheet0}.txt",
                               mime="text/plain")

        if TEST_MODE:
            if st.button("🧪 送到雲端（測試模擬）", type="secondary"):
                st.info(f"🧪 測試模式：模擬送出 {len(rows)} 筆，但實際上**沒有**寫到雲端，也沒有送 LINE 通知。")
                st.balloons()
        elif APPS_SCRIPT_URL and WRITE_SECRET:
            # 提示目前要送的是哪個版本（確認是定案版，不是機器版）
            _names_in_rows = "、".join(sorted({r[2] for r in rows if r[2]}))
            st.caption(f"⚠️ 送出前確認：本次定案人員 → {_names_in_rows}")
            if st.button("🚀 送到雲端（自動排提醒）", type="primary"):
                with st.spinner("送出中，請稍候…"):
                    try:
                        resp = requests.post(
                            APPS_SCRIPT_URL,
                            json={"action":"setWeek","secret":WRITE_SECRET,
                                  # 只送前3欄（印日期/區/姓名）給GAS，多餘的治療欄/🔺欄不外送
                                  "rows":[[str(r[0]), str(r[1]), str(r[2])] for r in rows]},
                            timeout=45)
                        if resp.ok and '"ok":true' in resp.text:
                            st.success(f"🎉 已送到雲端！共 {len(rows)} 筆。系統會自動 LINE 提醒，你不用再做任何事。")
                            st.balloons()
                            _, _, _, updated_hist = st.session_state.get("yao",(None,None,None,{}))
                            corrected = build_corrected_history(
                                rows, sheet0, (updated_hist or {}).get("排班紀錄.csv"))
                            ok2, n2, detail2 = push_history("setScheduleHistory", corrected, sheet0)
                            if ok2:
                                st.caption(f"✅ 排班歷史已同步（{n2} 筆，依玉繡實際定案），下週公平輪序更準確。")
                                if detail2:
                                    st.caption(f"🔍 診斷：{detail2}")
                            else:
                                st.error(f"⚠️ 本週名單已送出、LINE會照常提醒，但「排班歷史」同步失敗！"
                                          f"原因：{detail2}\n\n"
                                          "統計管理頁面的印次/休次不會更新這週，公平輪序會算錯。"
                                          "請到「📊 統計管理 → 印藥水統計」按「🔄 讀取」確認，"
                                          "如果這週真的沒出現，回來這裡重新按一次「🚀 送到雲端」重試。")
                            _clear_week_draft()         # 清除本機草稿
                            # 雲端草稿保留：讓小巫或玉繡重開 app 還能看到定案版
                            st.session_state.pop("week_draft_auto", None)
                        else:
                            st.error(f"送出失敗（{resp.status_code}）：{resp.text[:200]}")
                    except Exception as e:
                        st.error(f"送出失敗：{e}")
        else:
            st.warning("雲端直送尚未設定（請在 Streamlit Secrets 填 APPS_SCRIPT_URL 與 WRITE_SECRET）。")

        with st.expander("📋 手動備援（複製貼到試算表 / 下載 CSV）"):
            # 只取前3欄（rows 可能是新格式5欄），避免 DataFrame 欄數不符
            cloud = pd.DataFrame([[r[0], r[1], r[2]] for r in rows], columns=["印日期","區","姓名"])
            tsv = cloud.to_csv(index=False, sep="\t")
            st.markdown("① 按右上角複製鈕　→　② 開試算表「本週名單」　→　③ 點 A1 貼上")
            st.code(tsv, language=None)
            st.link_button("🔗 開啟試算表（本週名單）", SHEET_URL)
            st.download_button("⬇️ 下載 CSV 檔",
                               cloud.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"雲端貼上_{sheet0}.csv", mime="text/csv")

    if "yao" in st.session_state and data is not None:
        _, files, _, _ = st.session_state["yao"]
        _FILE_LABELS = {
            ".xlsx": "📋 列印用（Excel，貼到護理站公告欄）",
            ".txt":  "💬 傳 LINE 群組用（文字，複製貼上）",
            ".csv":  "☁️ 雲端貼上用（CSV，貼到 Google 試算表）",
        }
        with st.expander("⬇️ 其他檔案下載（列印用 xlsx / 貼 LINE 用 txt）"):
            for fn, b in files.items():
                ext = os.path.splitext(fn)[1].lower()
                label = _FILE_LABELS.get(ext, "")
                if label:
                    st.caption(label)
                st.download_button(f"⬇️ {fn}", b, file_name=fn, key="dl_"+fn)


# ═══════════════════════ 每月稽核 ═══════════════════════
else:
    c1, c2 = st.columns(2)
    yy = c1.number_input("年", 2024, 2100, 2026)
    mm = c2.number_input("月", 1, 12, pd.Timestamp.now().month)
    # v3.41：月份鍵一律用**民國**格式，跟 稽核.py 的 month_tag() 及雲端既有資料
    # （114-09 ~ 115-07 全是民國）保持一致。舊版用西元 "2026-07"，會造成
    # ①load_history 的 skip_month 比不到本月、本月結果混進歷史重算（實測公平分數偏差±2）
    # ②送雲端時同一個月同時存在 "115-07" 與 "2026-07" 兩把鍵 → 每個人被計算兩次
    month_key = f"{int(yy) - 1911}-{int(mm):02d}"

    if st.session_state.get("ak_month_key") != month_key:
        st.session_state.pop("ak_shifts", None)
        st.session_state.pop("ak", None)
        st.session_state["ak_month_key"] = month_key

    if audit_quick:
        # ── 快速模式：免上傳，直接點選白/夜＋區 ──────────────
        st.markdown("#### 2️⃣ 點選每人「白/夜」＋「區」→ 排稽核")
        roster = _load_roster_full()
        if not roster:
            st.error("找不到組員名單（組員名單.csv）。請先確認 repo 裡有這個檔。"); st.stop()
        # 帶入優先序：①雲端草稿（上次暫存）②上個月設定 ③預設
        draft   = fetch_audit_draft()
        prefill = fetch_last_audit_prefill()
        if draft:
            st.caption("📌 已帶回你上次「暫存」的草稿。改好可再按「💾 暫存」，或直接「✅ 排稽核」。")
        else:
            st.caption("免上傳 Excel。系統已帶出上個月的設定，只要改這個月有變動的人即可。")
        base = []
        for m in roster:
            nm = m["姓名"]
            pre = draft.get(nm) or prefill.get(nm)   # 有草稿/上次才帶；沒有就留「未設」
            if pre:
                typ, area = pre
            else:
                typ, area = "白班", "❓"               # 冷啟動：區留❓未設，逼人設定、避免默默全一區
            if typ not in ("白班","小夜"): typ = "白班"
            if area not in ("一區","二區","❓"): area = "❓"
            base.append({"卡號": m["卡號"], "姓名": nm, "班型": typ, "區": area})
        df_q = pd.DataFrame(base)
        edited_q = st.data_editor(
            df_q,
            column_config={
                "卡號": st.column_config.TextColumn("卡號", disabled=True),
                "姓名": st.column_config.TextColumn("姓名", disabled=True),
                "班型": st.column_config.SelectboxColumn("班型 ✏️", options=["白班","小夜"], required=True),
                "區":   st.column_config.SelectboxColumn("區 ✏️",   options=["一區","二區","❓"], required=True),
            },
            use_container_width=True, hide_index=True, key="quick_edit"
        )
        n_white = int((edited_q["班型"] == "白班").sum())
        n_night = int((edited_q["班型"] == "小夜").sum())
        n_a1    = int((edited_q["區"] == "一區").sum())
        n_a2    = int((edited_q["區"] == "二區").sum())
        n_unset = int((edited_q["區"] == "❓").sum())
        st.caption(f"目前：白班 {n_white}、小夜 {n_night}；一區 {n_a1}、二區 {n_a2}"
                   + (f"；❓未設區 {n_unset}" if n_unset else "") + f"（共 {len(edited_q)} 人）")
        if n_unset:
            st.warning(f"⚠️ 還有 {n_unset} 人的「區」是 ❓ 未設，請先點成一區/二區，否則他們會排不進去（會噴錯）。")
        if n_unset == 0 and n_a2 == 0:
            st.warning("⚠️ 目前沒有人在「二區」——二區的稽核會排不出來，確認是不是漏設了？")
        if n_unset == 0 and n_a1 == 0:
            st.warning("⚠️ 目前沒有人在「一區」。")
        if n_night == 0:
            st.warning("⚠️ 目前沒有人是「小夜」——第三班（小夜）會排不出來。")

        # 💾 暫存 / 🗑 清除暫存（雲端草稿，可分次填、明天再回來接續）
        if TEST_MODE:
            cda, cdb = st.columns(2)
            if cda.button("🧪 暫存草稿（測試模擬）"):
                st.info("🧪 測試模式：模擬暫存成功，但沒有真的寫到雲端。")
            if cdb.button("🧪 清除暫存（測試模擬）"):
                st.info("🧪 測試模式：模擬清除成功，但沒有真的動雲端。")
        elif APPS_SCRIPT_URL and WRITE_SECRET:
            cda, cdb = st.columns(2)
            if cda.button("💾 暫存草稿（之後可接續填）"):
                if push_audit_draft(edited_q):
                    st.success("✅ 已暫存到雲端！下次打開會自動帶回，可接著填。")
                else:
                    st.error("暫存失敗，請稍後再試。")
            if cdb.button("🗑 清除暫存（改用上月設定）"):
                if clear_audit_draft():
                    st.success("✅ 已清除暫存。重新整理後會改帶上個月的設定。")
                else:
                    st.error("清除失敗，請稍後再試。")

        if st.button("✅ 排稽核（快速）", type="primary"):
          if n_unset > 0:
            st.error(f"還有 {n_unset} 人的「區」是 ❓ 未設，請先全部點成一區/二區，再排稽核。")
          else:
            with st.spinner("讀取雲端歷史 + 排稽核中…"):
                quick_csv = edited_q.to_csv(index=False).encode("utf-8-sig")
                config_overrides = {"快速名冊.csv": quick_csv}
                if APPS_SCRIPT_URL and WRITE_SECRET:
                    hist_csv = fetch_history_csv("getAuditHistory")   # v3.41：失敗要吵，不要靜默用舊備份
                    if hist_csv: config_overrides["稽核紀錄.csv"] = hist_csv
                    else: st.error("⚠️ 讀不到雲端『稽核歷史』，這次會改用本機舊備份算公平分數，"
                                   "結果可能不準！請確認網路後重新排一次。")
                    mem_csv = fetch_members_as_csv()
                    if mem_csv: config_overrides["組員名單.csv"] = mem_csv
                    else: st.warning("⚠️ 讀不到雲端『組員名單』，改用本機備份（若最近有人入組/退組可能不準）。")
                    # 稽核.py 目前 load_holidays() 有讀、但演算法還沒用到 HOLIDAYS，
                    # 所以讀不到也不影響結果、不吵使用者。仍然一起注入，是為了讓
                    # 「休診日只有雲端一個來源」這件事對三個消費者（排班.py／稽核.py／
                    # .gs）都成立，將來稽核真的用到時不會又冒出第二份清單。
                    _hol_csv, _ = fetch_holidays_as_csv()
                    if _hol_csv is not None: config_overrides["休診日.csv"] = _hol_csv
                out, files, updated_hist = run_tool(
                    "稽核.py", None, ["--quick", month_key], config_overrides)
                st.session_state["ak"] = (out, files, updated_hist)
    else:
        # ── Stage 1：確認班型（上傳班表分析）──────────────────
        st.markdown("#### 2️⃣ 確認班型（程式猜測 → 玉繡確認）")
        st.caption("程式從班表判斷白/夜，不確定的顯示 ❓，請手動改。")

        if st.button("📊 預覽班型", type="secondary"):
            with st.spinner("分析班表中…"):
                df_shifts = detect_shifts_quick(data, int(yy), int(mm))
            if df_shifts.empty:
                st.error("找不到該月份的班表資料，請確認分頁是否包含此月份。")
            else:
                st.session_state["ak_shifts"] = df_shifts
                st.session_state.pop("ak", None)

        if "ak_shifts" in st.session_state:
            df_shifts = st.session_state["ak_shifts"]
            st.caption("👇 可直接點「確認班型」欄修改。")
            edited_shifts = st.data_editor(
                df_shifts,
                column_config={
                    "程式猜測": st.column_config.TextColumn("程式猜測", disabled=True),
                    "確認班型": st.column_config.SelectboxColumn(
                        "確認班型 ✏️", options=["白班","夜班","❓"], required=True)
                },
                use_container_width=True, hide_index=True, key="shift_edit"
            )
            uncertain = (edited_shifts["確認班型"] == "❓").sum()
            if uncertain > 0:
                st.warning(f"⚠️ 還有 {uncertain} 人班型是 ❓，這些人本月排稽核時會略過。")

            if st.button("✅ 確認班型 → 排稽核", type="primary"):
                with st.spinner("讀取雲端歷史 + 排稽核中…"):
                    override_df  = edited_shifts[["卡號","姓名","確認班型"]].rename(columns={"確認班型":"班型"})
                    override_csv = override_df.to_csv(index=False).encode("utf-8-sig")
                    config_overrides = {"班型覆蓋.csv": override_csv}
                    if APPS_SCRIPT_URL and WRITE_SECRET:
                        hist_csv = fetch_history_csv("getAuditHistory")   # v3.41：失敗要吵
                        if hist_csv: config_overrides["稽核紀錄.csv"] = hist_csv
                        else: st.error("⚠️ 讀不到雲端『稽核歷史』，這次會改用本機舊備份算公平分數，"
                                       "結果可能不準！請確認網路後重新排一次。")
                        mem_csv = fetch_members_as_csv()
                        if mem_csv: config_overrides["組員名單.csv"] = mem_csv
                        else: st.warning("⚠️ 讀不到雲端『組員名單』，改用本機備份（若最近有人入組/退組可能不準）。")
                        # 同上：稽核演算法目前沒用到休診日，一起注入是為了維持單一來源
                        _hol_csv, _ = fetch_holidays_as_csv()
                        if _hol_csv is not None: config_overrides["休診日.csv"] = _hol_csv
                    out, files, updated_hist = run_tool(
                        "稽核.py", data, [month_key], config_overrides)
                    st.session_state["ak"] = (out, files, updated_hist)

    # ── Stage 2：稽核名單 + 送雲端 ────────────────────────
    if "ak" in st.session_state:
        out, files, updated_hist = st.session_state["ak"]
        fn, b = pick(files, ".xlsx")
        if not b:
            st.error("沒產生名單，請看下方訊息。"); st.code(out); st.stop()

        st.markdown("#### 3️⃣ 稽核名單 → 送到雲端")
        df = pd.read_excel(io.BytesIO(b)).fillna("")
        st.subheader(f"稽核 AK 名單（{month_key}）")
        st.caption("可直接點「稽核者」欄改人名。")
        edited_ak = st.data_editor(df, use_container_width=True,
                                    key="ak_edit", hide_index=True)
        for n in extract_notes(out): st.write("・" + n)

        if TEST_MODE:
            if st.button("🧪 送稽核結果到雲端（測試模擬）", type="secondary"):
                st.info("🧪 測試模式：模擬送出成功，但實際上**沒有**寫到雲端，也沒有送 LINE 通知給稽核者。")
                st.balloons()
        elif APPS_SCRIPT_URL and WRITE_SECRET:
            if st.button("🚀 送稽核結果到雲端", type="primary"):
                with st.spinner("送出中，請稍候…"):
                    ak_hist_b = files.get("稽核紀錄_輸出.csv")
                    # v3.41：先用玉繡實際改過的名單修正歷史，再送出（比照印藥水的 Fix1）。
                    # 舊版直接送子行程原本的產出，玉繡手改的部分不會進歷史，公平輪序逐月累積誤差。
                    ak_hist_b = build_corrected_audit_history(edited_ak, month_key, ak_hist_b)
                    ok_hist, n_hist, detail_hist = False, 0, "沒有稽核紀錄檔案可送"
                    if ak_hist_b:
                        ok_hist, n_hist, detail_hist = push_history("setAuditResult", ak_hist_b, month_key)

                    # Fix2：LINE 通知每位稽核者
                    sent, miss, failed_names = send_audit_notices(month_key, edited_ak)

                    if ok_hist:
                        st.success(f"🎉 稽核歷史已送到雲端（{month_key}，{n_hist} 筆），下個月公平輪序更準確。")
                    else:
                        st.error(f"⚠️ 稽核歷史同步失敗：{detail_hist}")
                    if sent > 0:
                        st.success(f"📱 已 LINE 通知 {sent} 位稽核者各自的責任班次。")
                        st.balloons()
                    if miss > 0:
                        st.warning(f"⚠️ {miss} 人缺 userId，無法 LINE 通知（請確認「對照」分頁）。")
                    if failed_names:
                        # v3.43：以前 LINE API 回錯誤碼會被 GAS 整個吞掉、畫面照樣顯示
                        # 「已通知 N 人」，這幾個人其實根本沒收到。現在會明確列出來。
                        st.error(f"❌ 這 {len(failed_names)} 位的 LINE 通知**實際發送失敗**，"
                                 f"請改用其他方式告知：{'、'.join(failed_names)}"
                                 "（可能是對照表的 userId 失效，或 LINE 官方帳號額度／token 有問題）")

        st.download_button("⬇️ 下載稽核名單（已套用修改）",
                           edited_ak.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"稽核名單_{month_key}.csv", mime="text/csv")
        with st.expander("⬇️ 其他檔案下載"):
            _AK_FILE_LABELS = {
                ".csv":  "📊 稽核紀錄（上傳到雲端歷史用）",
                ".xlsx": "📋 列印用（Excel）",
                ".txt":  "💬 傳 LINE 群組用（文字）",
            }
            for fn, b in files.items():
                ext = os.path.splitext(fn)[1].lower()
                label = _AK_FILE_LABELS.get(ext, "")
                if label:
                    st.caption(label)
                st.download_button(f"⬇️ {fn}", b, file_name=fn, key="akdl_"+fn)


# ═══════════════════════ 統計管理 ═══════════════════════
if mode.startswith("📊"):
    st.markdown("#### 📊 統計管理")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📋 印藥水統計", "📋 稽核統計", "📋 最新稽核名單", "👥 組員名單", "🗓 休診日"])

    # ── Tab1：印藥水統計 ──────────────────────────────────
    with tab1:
        st.caption("每人累積印藥水次數與休息次數。可直接改，改完按「💾 存回雲端」，下次排班即生效。")
        _sc1, _sc2 = st.columns(2)
        if _sc1.button("🔄 讀取", type="primary", key="stats_load"):
            with st.spinner("讀取中…"):
                _st = fetch_schedule_stats()
            st.session_state["schedule_stats"] = _st if _st is not None else "empty"
        if not TEST_MODE and APPS_SCRIPT_URL and WRITE_SECRET:
            if _sc2.button("📤 同步本機CSV→雲端", key="stats_sync_local",
                           help="把 repo 裡排班紀錄.csv「雲端還沒有的週次」補進雲端，"
                                "雲端既有的週次不會被覆蓋或刪除（v3.38起，只補不蓋）。"):
                with st.spinner("讀取雲端現況並比對中…"):
                    _sok, _sn, _serr = sync_schedule_history_from_csv()
                if _sok and _sn == 0:
                    st.info("雲端已經有本機CSV全部的週次，沒有需要補的資料（沒有動到任何一筆）。")
                elif _sok:
                    st.success(f"✅ 已把本機獨有的 {_sn} 筆（雲端原本沒有的週次）補進雲端！按「🔄 讀取」確認。")
                    st.session_state.pop("schedule_stats", None)
                else:
                    _hint = "（Google 伺服器較慢，已自動重試，請再按一次）" if "逾時" in (_serr or "") else ""
                    st.error(f"同步失敗：{_serr or '未知錯誤'}{_hint}")
        if "schedule_stats" in st.session_state:
            df_st = st.session_state["schedule_stats"]
            if isinstance(df_st, str) and df_st == "empty":
                st.warning("雲端還沒有排班歷史。請按「📤 同步本機CSV→雲端」把今年全年歷史上傳。")
            elif isinstance(df_st, str):
                st.error(f"讀取失敗：{df_st}")
            else:
                df_st = df_st.copy()
                st.caption(f"共 {len(df_st)} 人｜淨值越小 → 印次少 → 下次優先被排印")
                edited_st = st.data_editor(df_st, column_config={
                    "卡號":        st.column_config.TextColumn("卡號", disabled=True),
                    "姓名":        st.column_config.TextColumn("姓名", disabled=True),
                    "印次":        st.column_config.NumberColumn("印次 ✏️", min_value=0, step=1),
                    "休次":        st.column_config.NumberColumn("休次 ✏️", min_value=0, step=1),
                    "淨值(印-休)": st.column_config.NumberColumn("淨值", disabled=True),
                }, use_container_width=True, hide_index=True, key="stats_edit")
                edited_st["淨值(印-休)"] = edited_st["印次"] - edited_st["休次"]
                st.download_button("⬇️ 下載統計 CSV", edited_st.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="印藥水統計.csv", mime="text/csv", key="stats_dl")
                st.warning("⚠️ 這個「存回雲端」會把「排班歷史」整份清空重建，只留這裡的總數字，"
                            "**每一週實際印哪一天、哪週的明細會全部消失**（變成「統計-印01」這種"
                            "沒有日期的假列）。只有在你確定要「整批重設」所有人的累計數字時才用這個，"
                            "平常要修正某一週的資料，請用「每週印藥水」重新排那一週、送到雲端就好，"
                            "不要在這裡改數字存檔。")
                if TEST_MODE:
                    if st.button("🧪 存回雲端（模擬）", key="stats_save_test"):
                        st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
                elif APPS_SCRIPT_URL and WRITE_SECRET:
                    _confirm_wipe = st.checkbox(
                        "我知道這樣會清空所有人的每週明細、只留總數字，仍要繼續", key="stats_save_confirm")
                    if st.button("💾 存回雲端", type="primary", key="stats_save", disabled=not _confirm_wipe):
                        with st.spinner("儲存中…"):
                            ok = save_schedule_stats(edited_st)
                        if ok:
                            st.success("✅ 排班統計已更新！下次排印藥水會自動用新數字。")
                            st.session_state["schedule_stats"] = edited_st.reset_index(drop=True)
                            st.balloons()
                        else:
                            st.error("儲存失敗，請稍後再試。")

    # ── Tab1 下半：個人明細查詢 ──────────────────────────
    with tab1:
        with st.expander("🔍 查詢個人印/休明細（點我展開）", expanded=False):
            _dc1, _dc2 = st.columns([2, 1])
            if _dc1.button("🔄 載入明細資料", key="detail_load"):
                with st.spinner("讀取中…"):
                    _raw = fetch_schedule_history_raw()
                st.session_state["schedule_detail"] = _raw if _raw is not None else "empty"
            if "schedule_detail" in st.session_state:
                _raw = st.session_state["schedule_detail"]
                if isinstance(_raw, str) and _raw == "empty":
                    st.warning("雲端無歷史資料。")
                elif isinstance(_raw, str):
                    st.error(f"讀取失敗：{_raw}")
                else:
                    names = sorted(_raw["姓名"].unique().tolist())
                    sel_name = st.selectbox("選擇人員", names, key="detail_sel")
                    if sel_name:
                        person_df = _raw[_raw["姓名"] == sel_name].copy()
                        n_print = (person_df["狀態"] == "印").sum()
                        n_rest  = (person_df["狀態"] == "休").sum()
                        st.caption(f"**{sel_name}** — 印 {n_print} 次 ／ 休 {n_rest} 次")
                        # 週次可能被 Google Sheets 把前導零吃掉（0112→112），轉回 YYYY/MM/DD
                        from datetime import timezone, timedelta
                        _today = datetime.now(timezone(timedelta(hours=8))).date()
                        def _fmt_week(w):
                            s = str(w).strip()
                            # 純數字 3-4 碼 → 補零到4碼 → 推算年份 → YYYY/MM/DD
                            if re.match(r"^\d{3,4}$", s):
                                s = s.zfill(4)
                                try:
                                    mo, dy = int(s[:2]), int(s[2:])
                                    yr = _today.year
                                    d = date(yr, mo, dy)
                                    if (d - _today).days > 180:
                                        d = date(yr - 1, mo, dy)
                                    return d.strftime("%Y/%m/%d")
                                except Exception:
                                    return s
                            return s
                        person_df["日期"] = person_df["週次"].apply(_fmt_week)
                        show_cols = ["日期", "狀態"]
                        if "治療日" in person_df.columns and person_df["治療日"].str.strip().ne("").any():
                            show_cols.append("治療日")
                        disp = person_df[show_cols].sort_values("日期").reset_index(drop=True)
                        def _color_row(row):
                            color = "#d4edda" if row["狀態"] == "印" else "#fff3cd"
                            return [f"background-color:{color}"] * len(row)
                        st.dataframe(disp.style.apply(_color_row, axis=1),
                                     use_container_width=True, hide_index=True)

    # ── Tab2：稽核統計 ──────────────────────────────────
    with tab2:
        st.caption("每人累積稽核次數與休息次數。可直接改，改完按「💾 存回雲端」，下次排稽核即生效。")
        _ac1, _ac2 = st.columns(2)
        if _ac1.button("🔄 讀取", type="primary", key="audit_stats_load"):
            with st.spinner("讀取中…"):
                _ast = fetch_audit_stats()
            st.session_state["audit_stats"] = _ast if _ast is not None else "empty"
        if not TEST_MODE and APPS_SCRIPT_URL and WRITE_SECRET:
            if _ac2.button("📤 同步本機CSV→雲端", key="audit_sync_local",
                           help="把 repo 裡稽核紀錄.csv「雲端還沒有的月份」補進雲端，"
                                "雲端既有的月份不會被覆蓋或刪除（v3.38起，只補不蓋）。"):
                with st.spinner("讀取雲端現況並比對中…"):
                    _aok, _an, _aerr = sync_audit_history_from_csv()
                if _aok and _an == 0:
                    st.info("雲端已經有本機CSV全部的月份，沒有需要補的資料（沒有動到任何一筆）。")
                elif _aok:
                    st.success(f"✅ 已把本機獨有的 {_an} 筆（雲端原本沒有的月份）補進雲端！按「🔄 讀取」確認。")
                    st.session_state.pop("audit_stats", None)
                else:
                    _hint = "（Google 伺服器較慢，已自動重試，請再按一次）" if "逾時" in (_aerr or "") else ""
                    st.error(f"同步失敗：{_aerr or '未知錯誤'}{_hint}")
        if "audit_stats" in st.session_state:
            df_ast = st.session_state["audit_stats"]
            if isinstance(df_ast, str) and df_ast == "empty":
                st.warning("雲端還沒有稽核歷史。請按「📤 同步本機CSV→雲端」把今年全年歷史上傳。")
            elif isinstance(df_ast, str):
                st.error(f"讀取失敗：{df_ast}")
            else:
                df_ast = df_ast.copy()
                st.caption(f"共 {len(df_ast)} 人｜淨值越小 → 稽核次少 → 下次優先被排稽核")
                edited_ast = st.data_editor(df_ast, column_config={
                    "卡號":           st.column_config.TextColumn("卡號", disabled=True),
                    "姓名":           st.column_config.TextColumn("姓名", disabled=True),
                    "稽核次":         st.column_config.NumberColumn("稽核次 ✏️", min_value=0, step=1),
                    "休次":           st.column_config.NumberColumn("休次 ✏️", min_value=0, step=1),
                    "淨值(稽核-休)":  st.column_config.NumberColumn("淨值", disabled=True),
                }, use_container_width=True, hide_index=True, key="audit_stats_edit")
                edited_ast["淨值(稽核-休)"] = edited_ast["稽核次"] - edited_ast["休次"]
                st.download_button("⬇️ 下載統計 CSV", edited_ast.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="稽核統計.csv", mime="text/csv", key="audit_stats_dl")
                # v3.41：補上跟 Tab1「印藥水統計」一模一樣的防呆。v3.35 幫印藥水那顆加了
                # 警告+必勾確認，但這顆結構完全相同的孿生按鈕被漏掉了——沒警告、沒勾選、
                # type="primary" 直接可按，一次誤觸就會把152筆稽核明細洗成「統計-稽01」假列。
                # 這正是接續包第十三節自己寫過的教訓（只修一個、沒推廣去檢查孿生函式）。
                st.warning("⚠️ 這個「存回雲端」會把「稽核歷史」整份清空重建，只留這裡的總數字，"
                            "**每個月實際誰稽核哪一區哪一班的明細會全部消失**（變成「統計-稽01」這種"
                            "沒有月份/位置的假列），連帶「最新稽核名單」也會讀不到東西。"
                            "只有在你確定要「整批重設」所有人的累計數字時才用這個，"
                            "平常要修正某個月的資料，請用「每月稽核」重排那個月、送到雲端就好，"
                            "不要在這裡改數字存檔。")
                if TEST_MODE:
                    if st.button("🧪 存回雲端（模擬）", key="audit_stats_save_test"):
                        st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
                elif APPS_SCRIPT_URL and WRITE_SECRET:
                    _confirm_wipe_ak = st.checkbox(
                        "我知道這樣會清空所有人的每月稽核明細、只留總數字，仍要繼續",
                        key="audit_stats_save_confirm")
                    if st.button("💾 存回雲端", type="primary", key="audit_stats_save",
                                 disabled=not _confirm_wipe_ak):
                        with st.spinner("儲存中…"):
                            ok2 = save_audit_stats(edited_ast)
                        if ok2:
                            st.success("✅ 稽核統計已更新！下次排稽核會自動用新數字。")
                            st.session_state["audit_stats"] = edited_ast.reset_index(drop=True)
                            st.balloons()
                        else:
                            st.error("儲存失敗，請稍後再試。")

    # ── Tab3：最新稽核名單 ──────────────────────────────────
    with tab3:
        st.caption("讀取玉繡最新一次送出的稽核名單，確認當月稽核安排。")
        if st.button("🔄 讀取最新稽核名單", type="primary", key="latest_audit_load"):
            with st.spinner("讀取中…"):
                _lm, _lr = fetch_latest_audit_result()
            if _lm is None and isinstance(_lr, str):
                st.session_state["latest_audit"] = ("error", _lr)
            elif _lm is None:
                st.session_state["latest_audit"] = ("empty", None)
            else:
                st.session_state["latest_audit"] = (_lm, _lr)
        if "latest_audit" in st.session_state:
            _la = st.session_state["latest_audit"]
            if _la[0] == "error":
                st.error(f"讀取失敗：{_la[1]}")
            elif _la[0] == "empty":
                st.warning("雲端還沒有稽核歷史，請先同步稽核紀錄.csv 到雲端。")
            else:
                _month, _df_la = _la
                st.success(f"**{_month}** 稽核名單")
                _稽核者 = _df_la[_df_la["狀態"] == "稽核"].copy().reset_index(drop=True)
                _休息者 = _df_la[_df_la["狀態"] == "休"].copy().reset_index(drop=True)
                # 若有位置欄，拆成 區/組/班次 三欄顯示成表格
                if _稽核者["位置"].str.strip().any():
                    def _split_pos(p):
                        parts = str(p).split("/") if "/" in str(p) else ["", "", str(p)]
                        while len(parts) < 3: parts.append("")
                        return parts[0], parts[1], parts[2]
                    _稽核者[["區","組","班次"]] = pd.DataFrame(
                        [_split_pos(p) for p in _稽核者["位置"]], index=_稽核者.index)
                    st.dataframe(_稽核者[["區","組","班次","姓名"]].rename(columns={"姓名":"稽核者"}),
                                 use_container_width=True, hide_index=True)
                else:
                    for _, _row in _稽核者.iterrows():
                        st.write(f"✅ {_row['姓名']}")
                if not _休息者.empty:
                    st.markdown("**本月休息：**" + "、".join(_休息者["姓名"].tolist()))
        else:
            st.info("按「🔄 讀取最新稽核名單」載入玉繡最新一次排的稽核。")

    # ── Tab4：組員名單 ──────────────────────────────────
    with tab4:
        st.caption("雲端主檔組員名單。新增/刪除組員後按「💾 存回雲端」，之後排班就會用新名單。")
        _m1, _m2 = st.columns(2)
        if _m1.button("🔄 讀取", type="primary", key="members_load"):
            with st.spinner("讀取中…"):
                _mem = fetch_members_cloud()
            st.session_state["members_cloud"] = _mem if _mem is not None else "empty"
        if _m2.button("📤 從本機 CSV 同步到雲端", key="members_sync_local",
                      help="只在雲端還沒有組員名單時可用（初始化）。雲端已經有名單後，"
                           "這顆按鈕不會再覆蓋，請直接在下方表格編輯後按「存回雲端」。"):
            # 組員名單跟排班/稽核歷史不同：真的會有人被移除（離職/退組），不能比照
            # v3.38 那種「只補雲端沒有的」合併邏輯——如果雲端上正確地移除了某人、
            # 但本機CSV還留著舊名字，合併邏輯會把這個人誤救回來。所以這裡改成更嚴格
            # 的作法：只有雲端目前完全是空的（真的是第一次初始化）才允許這顆按鈕動作，
            # 雲端已有名單就一律拒絕，逼大家改用下方表格（會先讀到雲端現況再編輯）。
            _cloud_check = fetch_members_cloud()
            if _cloud_check is not None and not _cloud_check.empty:
                st.error(f"雲端已經有組員名單（{len(_cloud_check)}人），為避免蓋掉雲端現況，"
                         f"這顆按鈕已停用。請按上面「🔄 讀取」載入雲端名單，在下方表格直接"
                         f"新增/刪除/改名字，再按「💾 存回雲端」。")
            else:
                _local_csv = os.path.join(HERE, "組員名單.csv")
                if os.path.exists(_local_csv):
                    try:
                        _ldf = pd.read_csv(_local_csv, encoding="utf-8-sig")
                        if save_members_cloud(_ldf[["卡號","姓名"]]):
                            st.session_state["members_cloud"] = _ldf[["卡號","姓名"]].reset_index(drop=True)
                            st.success(f"✅ 已同步 {len(_ldf)} 人到雲端！")
                        else:
                            st.error("同步失敗，請稍後再試。")
                    except Exception as _e:
                        st.error(f"讀取本機 CSV 失敗：{_e}")
                else:
                    st.error("找不到本機 組員名單.csv，請確認 repo 裡有這個檔。")
        if "members_cloud" not in st.session_state:
            st.info("按「🔄 讀取」載入雲端組員名單；若第一次使用，按「📤 從本機 CSV 同步到雲端」初始化。")
        elif isinstance(st.session_state["members_cloud"], str):
            st.warning("雲端還沒有組員名單，請手動新增後存回雲端。")
            _empty = pd.DataFrame(columns=["卡號","姓名"])
            _new = st.data_editor(_empty, num_rows="dynamic", use_container_width=True,
                                  hide_index=True, key="members_edit_empty")
            if st.button("💾 存回雲端", type="primary", key="members_save_empty"):
                if save_members_cloud(_new):
                    st.success("✅ 組員名單已儲存！")
                    st.session_state["members_cloud"] = _new
                    st.balloons()
                else:
                    st.error("儲存失敗。")
        else:
            df_mem = st.session_state["members_cloud"].copy()
            st.caption(f"共 {len(df_mem)} 人｜可新增列（點最下方 + 號）或直接改名字/卡號")
            edited_mem = st.data_editor(df_mem, num_rows="dynamic",
                                        use_container_width=True, hide_index=True, key="members_edit")
            st.download_button("⬇️ 下載組員名單 CSV", edited_mem.to_csv(index=False).encode("utf-8-sig"),
                               file_name="組員名單.csv", mime="text/csv", key="members_dl")
            if TEST_MODE:
                if st.button("🧪 存回雲端（模擬）", key="members_save_test"):
                    st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
            elif APPS_SCRIPT_URL and WRITE_SECRET:
                if st.button("💾 存回雲端", type="primary", key="members_save"):
                    with st.spinner("儲存中…"):
                        ok3 = save_members_cloud(edited_mem)
                    if ok3:
                        st.success("✅ 組員名單已更新！下次排班自動套用。")
                        st.session_state["members_cloud"] = edited_mem.reset_index(drop=True)
                        st.balloons()
                    else:
                        st.error("儲存失敗，請稍後再試。")

    # ── Tab5：休診日（v3.42，單一來源）──────────────────────
    with tab5:
        st.caption("過年、國定假日這種「沒診、不上班」的日子。**週日不用列，程式自動跳過。**")
        st.info("🔗 這份清單是**唯一來源**：排班演算法算「印藥水日」往前推幾天，"
                "跟 LINE 小幫手算「提醒日」往前推幾天，都讀這一份。"
                "在這裡改一次，兩邊自動一致，不會再出現「排的日期」跟「LINE 通知的日期」對不上。")
        _h1, _h2 = st.columns(2)
        if _h1.button("🔄 讀取", type="primary", key="hol_load"):
            with st.spinner("讀取中…"):
                _hdf, _herr = fetch_holidays_cloud()
            st.session_state["holidays_cloud"] = _hdf if _hdf is not None else ("err:" + _herr)
        if _h2.button("📤 從本機 CSV 同步到雲端", key="hol_sync_local",
                      help="只在雲端「休診日」分頁還完全是空的時候可用（初始化）。"
                           "雲端已經有資料後，這顆按鈕不會覆蓋，請直接在下方表格編輯後存回雲端。"):
            # 比照 v3.40 組員名單的作法：休診日跟排班/稽核歷史不同，真的會需要「刪除」
            # （例如原本排的補班日取消了），不能用 v3.38「只補雲端沒有的」合併邏輯，
            # 否則刪掉的日子會被本機舊 CSV 救回來。所以只允許在雲端全空時初始化。
            _hchk, _herr2 = fetch_holidays_cloud()
            if _hchk is None:
                st.error(f"讀不到雲端休診日，先不動作以免蓋掉資料：{_herr2}")
            elif not _hchk.empty:
                st.error(f"雲端已經有 {len(_hchk)} 筆休診日，為避免蓋掉雲端現況，這顆按鈕已停用。"
                         "請按上面「🔄 讀取」載入後，在下方表格直接新增/刪除，再按「💾 存回雲端」。")
            else:
                _lh = os.path.join(HERE, "休診日.csv")
                if not os.path.exists(_lh):
                    st.error("找不到本機 休診日.csv。")
                else:
                    try:
                        _ldf = pd.read_csv(_lh, encoding="utf-8-sig", dtype=str).fillna("")
                        if "日期" not in _ldf.columns:
                            st.error("本機 休診日.csv 沒有「日期」欄位。")
                        elif _ldf.empty:
                            st.info("本機 休診日.csv 也是空的，沒有東西可以同步"
                                    "（代表目前確實沒有登記任何休診日，這是正常狀態）。")
                        else:
                            if "說明" not in _ldf.columns: _ldf["說明"] = ""
                            _ok, _n, _e = save_holidays_cloud(_ldf[["日期", "說明"]])
                            if _ok:
                                st.success(f"✅ 已同步 {_n} 筆休診日到雲端！")
                                st.session_state["holidays_cloud"] = _ldf[["日期", "說明"]].reset_index(drop=True)
                            else:
                                st.error(f"同步失敗：{_e}")
                    except Exception as _e:
                        st.error(f"讀取本機 CSV 失敗：{_e}")

        _hstate = st.session_state.get("holidays_cloud")
        if _hstate is None:
            st.info("按「🔄 讀取」載入雲端休診日。")
        elif isinstance(_hstate, str):
            st.error("讀取失敗：" + _hstate[4:])
            st.caption("⚠️ 讀不到的期間，排班會退回用本機 休診日.csv，"
                       "跟 LINE 小幫手讀的雲端分頁可能不一致——請先修好再排班。")
        else:
            _hdf = _hstate.copy()
            if _hdf.empty:
                st.warning("雲端目前沒有登記任何休診日。若今年有過年/連假要跳過，請在下面新增。")
                _hdf = pd.DataFrame(columns=["日期", "說明"])
            else:
                st.caption(f"共 {len(_hdf)} 天｜點最下方 ➕ 新增一列，或把整列清空來刪除")
            _edited_h = st.data_editor(
                _hdf, num_rows="dynamic", use_container_width=True, hide_index=True,
                column_config={
                    "日期": st.column_config.TextColumn(
                        "日期（YYYY-MM-DD）", help="一定要打成 2026-01-01 這種格式（西元、月日補零）"),
                    "說明": st.column_config.TextColumn("說明（例：春節）"),
                }, key="hol_edit")
            # 存出去之前先自己檢查格式，不要等 GAS 那邊靜默吃掉
            _bad = [str(v).strip() for v in _edited_h["日期"].tolist()
                    if str(v).strip() and not HOLIDAY_RE.match(str(v).strip())]
            if _bad:
                st.error("這幾筆日期格式不對（要 2026-01-01 這種）：" + "、".join(_bad))
            st.download_button("⬇️ 下載休診日 CSV", _edited_h.to_csv(index=False).encode("utf-8-sig"),
                               file_name="休診日.csv", mime="text/csv", key="hol_dl")
            if TEST_MODE:
                if st.button("🧪 存回雲端（模擬）", key="hol_save_test"):
                    st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
            elif APPS_SCRIPT_URL and WRITE_SECRET:
                if st.button("💾 存回雲端", type="primary", key="hol_save", disabled=bool(_bad)):
                    with st.spinner("儲存中…"):
                        _ok, _n, _e = save_holidays_cloud(_edited_h)
                    if _ok:
                        st.success(f"✅ 已存回雲端（{_n} 天）！排班演算法與 LINE 小幫手都會立刻用新清單。")
                        st.session_state["holidays_cloud"] = _edited_h.reset_index(drop=True)
                        st.balloons()
                    else:
                        st.error(f"儲存失敗：{_e}")
        st.caption("💡 repo 裡的 `休診日.csv` 從 v3.42 起只是**離線備份**（雲端讀不到時的保底），"
                   "平常請一律在這一頁改，不要去改那個檔案。")
