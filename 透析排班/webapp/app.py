# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）v2.3
  • Fix1：公平歷史學玉繡實際決定，而非程式原排
  • Fix2：稽核送出後 LINE 通知每位稽核者責任班次
  • Fix3：自動選最接近今天的班表分頁
"""
import os, io, re, csv, json, tempfile, shutil, subprocess, sys
from datetime import date, datetime
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


# ── Fix3：自動選最接近今天的班表分頁 ─────────────────────
def _best_sheet_index(sheets):
    """分頁名稱有日期（如 2026-06-16）→ 選最接近今天的；否則選最後一頁。"""
    today = date.today()
    best_idx = len(sheets) - 1
    best_delta = None
    for i, sn in enumerate(sheets):
        m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", str(sn))
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
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
        # 只看正常的「YYYY-MM」月份，跳過草稿那筆
        months = [str(r[iM]).strip() for r in rows[1:]
                  if re.match(r"^\d{4}-\d{2}$", str(r[iM]).strip())]
        if not months: return {}
        last = max(months)
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

# ── 💬 意見回饋：借用稽核歷史（特殊鍵「意見-時間」）存放，不動 LINE 程式 ──
APP_VER = "v2.7"
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

def fetch_feedback_list():
    """讀回所有回饋（稽核歷史裡 月份 以『意見-』開頭的列），新到舊。"""
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
                "留言者": str(r[iN]).strip(),
            })
        out.reverse()   # 新的在最上面
        return out
    except Exception:
        return []

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
            df_h = pd.read_csv(io.BytesIO(prev_hist_bytes), encoding="utf-8-sig")
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
    if not APPS_SCRIPT_URL or not WRITE_SECRET or not hist_bytes: return False
    try:
        df = pd.read_csv(io.BytesIO(hist_bytes), encoding="utf-8-sig")
        key_col = df.columns[0]
        week_rows = df[df[key_col].astype(str) == str(key)].values.tolist()
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": action, "secret": WRITE_SECRET,
                                   "key": key, "rows": week_rows},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception: return False

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
    if not notices: return 0, 0
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action":"sendAuditNotice","secret":WRITE_SECRET,
                                   "month":month_key,"notices":notices},
                             timeout=20)
        if resp.ok:
            d = resp.json()
            return d.get("sent",0), d.get("miss",0)
    except Exception: pass
    return 0, 0


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

st.title("💊 透析藥水排班")
st.caption("上傳班表 Excel → 出名單(表格)。可直接點格子改人名。跨區標 🔺。")
st.caption("🟢 版本 v2.7（💬 意見回饋＋🔊 語音導覽＋稽核快速模式＋💾草稿暫存）· 2026-06-23")

with st.expander("📖 第一次用？點我看「3 步驟」（給玉繡）", expanded=False):
    st.markdown("""
### 每週印藥水，只要 3 步：
**1️⃣ 上傳班表** → 選「🟦 每週印藥水」，把這週班表 Excel 傳上來。
**2️⃣ 排 + 微調** → 選「這一週」分頁 → 按「➡️ 排印藥水」。想換人就直接點格子改名字。
**3️⃣ 產生定案 → 送到雲端** → 按「✅ 產生定案」→「🚀 送到雲端」。完成！系統每晚自動 LINE 提醒。

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
    "最後，按送到雲端。看到畫面有氣球飛出來，就成功囉。"
    "這樣就好了。系統會自己用 LINE 提醒要印的人，你不用再做別的事，輕鬆一下。"
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
      <button style="BTN background:#6b7280" onclick="window.speechSynthesis.cancel()">⏹ 停止</button>
      <p style="color:#666;font-size:13px;margin-top:8px">點藍色聽「印藥水」、綠色聽「稽核」；要停就按停止。</p>
    </div>
    <script>
      var YAO = __YAO__;
      var JI  = __JI__;
      function sayIt(t){
        try{ window.speechSynthesis.cancel(); }catch(e){}
        var u = new SpeechSynthesisUtterance(t);
        u.lang = 'zh-TW';
        u.rate = 0.8;          // 語速慢一點
        window.speechSynthesis.speak(u);
      }
    </script>
    """
    _voice_html = (_voice_html
                   .replace("BTN", _btn)
                   .replace("__YAO__", json.dumps(_VOICE_YAO))
                   .replace("__JI__", json.dumps(_VOICE_JI)))
    components.html(_voice_html, height=150)

# ── 💬 回報問題／給建議（誰都能填，存到雲端給管理者看）──────────────
with st.expander("💬 有問題？回報一下（會存起來，管理者會看到）", expanded=False):
    st.caption("不用很會講～照下面選一選、簡單打幾個字就好。")
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

# ── 🔧 管理者：看大家的回報（用管理密碼進入）─────────────────────
with st.expander("🔧 管理者：看大家的回報", expanded=False):
    fb_pw = st.text_input("輸入管理密碼", type="password", key="fb_admin_pw")
    if fb_pw:
        if fb_pw == WRITE_SECRET:
            fbs = fetch_feedback_list()
            if not fbs:
                st.info("目前還沒有任何回報。")
            else:
                st.caption(f"共 {len(fbs)} 則（新到舊）")
                st.dataframe(pd.DataFrame(fbs), use_container_width=True, hide_index=True)
        else:
            st.error("密碼不對。")

st.markdown("#### 1️⃣ 選種類")
mode = st.radio("要排哪一種？", ["🟦 每週印藥水", "🟩 每月稽核"], horizontal=True)

# 每月稽核可選「快速點選（免上傳）」或「上傳班表分析」
audit_quick = False
if mode.startswith("🟩"):
    method = st.radio("稽核方式", ["⚡ 快速點選（免上傳 Excel，推薦）", "📤 上傳班表分析"],
                      horizontal=True)
    audit_quick = method.startswith("⚡")

data = None; sheets = []
if not audit_quick:                       # 需要 Excel 的兩條路：每週印藥水 / 上傳班表稽核
    up = st.file_uploader("上傳班表 Excel（.xls / .xlsx）", type=["xls","xlsx"])
    if not up:
        st.info("👆 先上傳班表 Excel（含每人每天班別/床號的那種檔）。截圖不行喔！")
        st.stop()
    fk = _file_key(up)
    if st.session_state.get("_last_file") != fk:
        for k in ["yao","cloud_rows","cloud_disp","cloud_sheet0","ak","ak_shifts","ak_month_key"]:
            st.session_state.pop(k, None)
        st.session_state["_last_file"] = fk
    data = up.read()
    try:
        sheets = pd.ExcelFile(io.BytesIO(data)).sheet_names
    except Exception as e:
        st.error(f"讀不到班表分頁：{e}"); st.stop()


# ═══════════════════════ 每週印藥水 ═══════════════════════
if mode.startswith("🟦"):
    st.markdown("#### 2️⃣ 選這一週 → 排班 → 微調")
    # Fix3：自動選最接近今天的分頁
    best = _best_sheet_index(sheets)
    sheet = st.selectbox("選「這一週」的分頁", sheets, index=best)

    if st.button("➡️ 排印藥水", type="primary"):
        with st.spinner("讀取雲端歷史 + 排班中…"):
            config_overrides = {}
            if APPS_SCRIPT_URL and WRITE_SECRET:
                hist_csv = fetch_history_csv("getScheduleHistory")
                if hist_csv: config_overrides["排班紀錄.csv"] = hist_csv
            out, files, updated_hist = run_tool("排班.py", data, [sheet], config_overrides)
            st.session_state["yao"] = (out, files, sheet, updated_hist)

    if "yao" in st.session_state:
        out, files, sheet0, updated_hist = st.session_state["yao"]
        fn, b = pick(files, ".xlsx")
        if not b:
            st.error("沒產生名單，請看下方訊息。"); st.code(out); st.stop()
        grid  = pd.read_excel(io.BytesIO(b), index_col=0).fillna("")
        names, dates, marks = parse_grid(grid)
        yr    = year_from_cloud(files)

        st.subheader(f"印藥水名單（{sheet0}）")
        st.caption("👇 想換人就直接點格子改名字（日期自動沿用）。改好再按「產生定案」。")
        edited = st.data_editor(names, use_container_width=True, key="yao_edit")
        for n in extract_notes(out): st.write("・" + n)

        st.markdown("#### 3️⃣ 產生定案 → 送到雲端")
        if st.button("✅ 產生定案（套用修改）", type="primary"):
            disp = edited.copy(); rows = []
            for r in edited.index:
                for c in edited.columns:
                    nm = str(edited.loc[r,c]).strip()
                    dt = dates.loc[r,c]; mk = marks.loc[r,c]
                    if nm and nm != "❌排不出":
                        disp.loc[r,c] = f"{nm}({dt}印){mk}" if dt else nm
                        if dt:
                            mo,dy = dt.split("/")
                            rows.append([f"{yr}-{int(mo):02d}-{int(dy):02d}", r, nm])
                    else:
                        disp.loc[r,c] = nm
            rows.sort(key=lambda x:(x[0],x[1]))
            st.session_state["cloud_rows"]   = rows
            st.session_state["cloud_disp"]   = disp
            st.session_state["cloud_sheet0"] = sheet0

        if "cloud_rows" in st.session_state:
            rows   = st.session_state["cloud_rows"]
            disp   = st.session_state["cloud_disp"]
            sheet0 = st.session_state["cloud_sheet0"]
            st.success("✅ 定案完成！")
            st.dataframe(disp, use_container_width=True)

            if APPS_SCRIPT_URL and WRITE_SECRET:
                if st.button("🚀 送到雲端（自動排提醒）", type="primary"):
                    with st.spinner("送出中，請稍候…"):
                        try:
                            resp = requests.post(
                                APPS_SCRIPT_URL,
                                json={"action":"setWeek","secret":WRITE_SECRET,
                                      "rows":[[str(x) for x in r] for r in rows]},
                                timeout=45)
                            if resp.ok and '"ok":true' in resp.text:
                                st.success(f"🎉 已送到雲端！共 {len(rows)} 筆。系統會自動 LINE 提醒，你不用再做任何事。")
                                st.balloons()
                                # Fix1：用玉繡實際定案重建歷史，推送雲端
                                _, _, _, updated_hist = st.session_state.get("yao",(None,None,None,{}))
                                corrected = build_corrected_history(
                                    rows, sheet0, (updated_hist or {}).get("排班紀錄.csv"))
                                ok2 = push_history("setScheduleHistory", corrected, sheet0)
                                if ok2: st.caption("✅ 排班歷史已同步（依玉繡實際定案），下週公平輪序更準確。")
                            else:
                                st.error(f"送出失敗（{resp.status_code}）：{resp.text[:200]}")
                        except Exception as e:
                            st.error(f"送出失敗：{e}")
            else:
                st.warning("雲端直送尚未設定（請在 Streamlit Secrets 填 APPS_SCRIPT_URL 與 WRITE_SECRET）。")

            with st.expander("📋 手動備援（複製貼到試算表 / 下載 CSV）"):
                cloud = pd.DataFrame(rows, columns=["印日期","區","姓名"])
                tsv = cloud.to_csv(index=False, sep="\t")
                st.markdown("① 按右上角複製鈕　→　② 開試算表「本週名單」　→　③ 點 A1 貼上")
                st.code(tsv, language=None)
                st.link_button("🔗 開啟試算表（本週名單）", SHEET_URL)
                st.download_button("⬇️ 下載 CSV 檔",
                                   cloud.to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"雲端貼上_{sheet0}.csv", mime="text/csv")

        with st.expander("⬇️ 其他檔案下載（列印用 xlsx / 貼 LINE 用 txt）"):
            for fn, b in files.items():
                st.download_button(f"⬇️ {fn}", b, file_name=fn, key="dl_"+fn)


# ═══════════════════════ 每月稽核 ═══════════════════════
else:
    c1, c2 = st.columns(2)
    yy = c1.number_input("年", 2024, 2100, 2026)
    mm = c2.number_input("月", 1, 12, pd.Timestamp.now().month)
    month_key = f"{int(yy)}-{int(mm):02d}"

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
            typ, area = draft.get(nm) or prefill.get(nm, ("白班", "一區"))
            if typ not in ("白班","小夜"): typ = "白班"
            if area not in ("一區","二區"): area = "一區"
            base.append({"卡號": m["卡號"], "姓名": nm, "班型": typ, "區": area})
        df_q = pd.DataFrame(base)
        edited_q = st.data_editor(
            df_q,
            column_config={
                "卡號": st.column_config.TextColumn("卡號", disabled=True),
                "姓名": st.column_config.TextColumn("姓名", disabled=True),
                "班型": st.column_config.SelectboxColumn("班型 ✏️", options=["白班","小夜"], required=True),
                "區":   st.column_config.SelectboxColumn("區 ✏️",   options=["一區","二區"], required=True),
            },
            use_container_width=True, hide_index=True, key="quick_edit"
        )
        n_white = int((edited_q["班型"] == "白班").sum())
        n_night = int((edited_q["班型"] == "小夜").sum())
        st.caption(f"目前：白班 {n_white} 人、小夜 {n_night} 人，共 {len(edited_q)} 人。")

        # 💾 暫存 / 🗑 清除暫存（雲端草稿，可分次填、明天再回來接續）
        if APPS_SCRIPT_URL and WRITE_SECRET:
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
            with st.spinner("讀取雲端歷史 + 排稽核中…"):
                quick_csv = edited_q.to_csv(index=False).encode("utf-8-sig")
                config_overrides = {"快速名冊.csv": quick_csv}
                if APPS_SCRIPT_URL and WRITE_SECRET:
                    hist_csv = fetch_history_csv("getAuditHistory")
                    if hist_csv: config_overrides["稽核紀錄.csv"] = hist_csv
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
                        hist_csv = fetch_history_csv("getAuditHistory")
                        if hist_csv: config_overrides["稽核紀錄.csv"] = hist_csv
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

        if APPS_SCRIPT_URL and WRITE_SECRET:
            if st.button("🚀 送稽核結果到雲端", type="primary"):
                with st.spinner("送出中，請稍候…"):
                    ak_hist_b = files.get("稽核紀錄_輸出.csv")
                    ok_hist = False
                    if ak_hist_b:
                        ok_hist = push_history("setAuditResult", ak_hist_b, month_key)

                    # Fix2：LINE 通知每位稽核者
                    sent, miss = send_audit_notices(month_key, edited_ak)

                    if ok_hist:
                        st.success(f"🎉 稽核歷史已送到雲端（{month_key}），下個月公平輪序更準確。")
                    if sent > 0:
                        st.success(f"📱 已 LINE 通知 {sent} 位稽核者各自的責任班次。")
                        st.balloons()
                    if miss > 0:
                        st.warning(f"⚠️ {miss} 人缺 userId，無法 LINE 通知（請確認「對照」分頁）。")
                    if not ok_hist and sent == 0:
                        st.error("送出失敗，請稍後再試或下載備用。")

        st.download_button("⬇️ 下載稽核名單（已套用修改）",
                           edited_ak.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"稽核名單_{month_key}.csv", mime="text/csv")
        with st.expander("⬇️ 其他檔案下載"):
            for fn, b in files.items():
                st.download_button(f"⬇️ {fn}", b, file_name=fn, key="akdl_"+fn)
