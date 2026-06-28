# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）v2.5
  • Fix1：公平歷史學玉繡實際決定，而非程式原排
  • Fix2：稽核送出後 LINE 通知每位稽核者責任班次
  • Fix3：自動選最接近今天的班表分頁
  • Fix4：定案草稿跨 session 保留，重開 app 可恢復
  • Fix5：定案後可下載排班圖片（PNG）
"""
import os, io, re, csv, json, tempfile, shutil, subprocess, sys
from datetime import date, datetime
import pandas as pd
import streamlit as st
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = ["組員名單.csv", "床號分區.csv", "不可印班別.csv", "休診日.csv",
          "排班紀錄.csv", "稽核紀錄.csv"]
CELL_RE = re.compile(r'^(.*?)\((\d+)/(\d+)印\)(.*)$')
DRAFT_PATH = os.path.join(HERE, "last_schedule_draft.json")

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
        if xls_bytes is not None:
            ext  = _detect_ext(xls_bytes)
            xlsp = os.path.join(work, f"上傳班表{ext}")
            with open(xlsp, "wb") as f: f.write(xls_bytes)
            cmd = [sys.executable, script, xlsp] + list(extra_args)
        else:
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
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return {}
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        rows = resp.json().get("rows") or []
        if len(rows) < 2: return {}
        hdr = [str(x).strip() for x in rows[0]]
        iM, iN, iP = hdr.index("月份"), hdr.index("姓名"), hdr.index("位置")
        months = [str(r[iM]).strip() for r in rows[1:] if str(r[iM]).strip()]
        if not months: return {}
        last = max(months)
        pf = {}
        for r in rows[1:]:
            if str(r[iM]).strip() != last: continue
            name = str(r[iN]).strip(); pos = str(r[iP]).strip()
            if not name or not pos: continue
            area = pos.split("/")[0].strip()
            typ  = "小夜" if "第三班" in pos else "白班"
            pf[name] = (typ, area)
        return pf
    except Exception:
        return {}

def build_corrected_history(cloud_rows, sheet_name, prev_hist_bytes):
    roster = _load_roster_names()
    if not roster: return prev_hist_bytes
    printed_names = {str(r[2]).strip() for r in cloud_rows if r[2]}
    headers = ["週次","卡號","姓名","狀態","治療日"]
    existing = []
    if prev_hist_bytes:
        try:
            df_h = pd.read_csv(io.BytesIO(prev_hist_bytes), encoding="utf-8-sig")
            existing = df_h[df_h["週次"].astype(str) != str(sheet_name)].values.tolist()
        except Exception: pass
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

def send_audit_notices(month_key, audit_df):
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


# ── LINE 公告文字格式 ─────────────────────────────────────
def _build_line_txt(rows):
    """產生和截圖一模一樣的 LINE 公告格式文字。"""
    from datetime import datetime as _dt
    DOW = {0:"週一",1:"週二",2:"週三",3:"週四",4:"週五",5:"週六",6:"週日"}

    day_map = {}
    for r in rows:
        d_str, area, name = str(r[0]), str(r[1]), str(r[2])
        if not name or name in ("", "❌排不出"): continue
        if d_str not in day_map: day_map[d_str] = {}
        day_map[d_str][area] = name

    if not day_map: return ""

    def fmt(d_str):
        d = _dt.strptime(d_str, "%Y-%m-%d")
        return f"{DOW[d.weekday()]} {d.month}/{d.day}"

    sorted_dates = sorted(day_map.keys())
    header = f"印藥水名單 (治療日 {fmt(sorted_dates[0])}~ {fmt(sorted_dates[-1])})"
    lines = [header, ""]

    for d_str in sorted_dates:
        line = fmt(d_str)
        for area in ["一區","二區","三區"]:
            nm = day_map[d_str].get(area, "")
            if nm: line += f"\t{area}:{nm}"
        lines.append(line)

    roster = _load_roster_full()
    if roster:
        printing = {str(r[2]) for r in rows if r[2]}
        resting = [m["姓名"] for m in roster if m["姓名"] not in printing]
        if resting:
            lines += ["", "休息：" + "、".join(resting)]

    return "\n".join(lines)


# ── Fix4：定案草稿跨 session 保留 ────────────────────────
def _save_draft(rows, sheet0, disp_df):
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
        with open(DRAFT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass

def _load_draft():
    if not os.path.exists(DRAFT_PATH): return None
    try:
        with open(DRAFT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _clear_draft():
    try:
        if os.path.exists(DRAFT_PATH): os.remove(DRAFT_PATH)
    except Exception:
        pass


# ── Fix5：排班表轉 PNG 圖片 ──────────────────────────────
def _disp_to_png(disp_df, title=""):
    try:
        import glob as _glob
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm

        font_path = None
        for pat in ["/usr/share/fonts/opentype/noto/*CJK*",
                    "/usr/share/fonts/truetype/noto/*CJK*",
                    "/usr/share/fonts/*/noto/*CJK*",
                    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                    "/usr/share/fonts/wqy/*.ttc"]:
            hits = _glob.glob(pat)
            if hits: font_path = hits[0]; break

        if font_path:
            fm.fontManager.addfont(font_path)
            plt.rcParams["font.family"] = fm.FontProperties(fname=font_path).get_name()

        df = disp_df.fillna("").astype(str).replace({"nan": "", "None": ""})
        rows_idx = list(df.index)
        cols_lbl = list(df.columns)
        cell_data = [[df.loc[r, c] for c in cols_lbl] for r in rows_idx]

        ncols, nrows = len(cols_lbl), len(rows_idx)
        fig, ax = plt.subplots(figsize=(max(10, ncols * 2.2), max(3, nrows * 1.4 + 2.2)))
        ax.set_axis_off()

        t = ax.table(cellText=cell_data, rowLabels=rows_idx,
                     colLabels=cols_lbl, loc="center", cellLoc="center")
        t.auto_set_font_size(False)
        t.set_fontsize(10)
        t.scale(1.0, 2.4)

        fp_prop = fm.FontProperties(fname=font_path) if font_path else None
        for j in range(ncols):
            cell = t[0, j]
            cell.set_facecolor("#1F497D")
            cell.set_text_props(color="white", fontweight="bold",
                                **({} if not fp_prop else {"fontproperties": fp_prop}))
        for i in range(nrows):
            cell = t[i + 1, -1]
            cell.set_facecolor("#DCE6F1")
            cell.set_text_props(fontweight="bold",
                                **({} if not fp_prop else {"fontproperties": fp_prop}))
            for j in range(ncols):
                if cell_data[i][j]:
                    bg = "#EEF4FB" if i % 2 == 0 else "white"
                    t[i + 1, j].set_facecolor(bg)
                    if fp_prop:
                        t[i + 1, j].get_text().set_fontproperties(fp_prop)

        if title:
            kw = {"fontproperties": fp_prop} if fp_prop else {}
            ax.set_title(title, fontsize=13, fontweight="bold", pad=14, **kw)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


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
st.caption("🟢 版本 v2.5（定案自動儲存可恢復 / 排班表直向顯示手機友善 / 下載排班圖片）· 2026-06-28")

with st.expander("📖 第一次用？點我看「3 步驟」（給玉繡）", expanded=False):
    st.markdown("""
### 每週印藥水，只要 3 步：
**1️⃣ 上傳班表** → 選「🟦 每週印藥水」，把這週班表 Excel 傳上來。
**2️⃣ 排 + 微調** → 選「這一週」分頁 → 按「➡️ 排印藥水」。想換人就直接點格子改名字。
**3️⃣ 產生定案 → 送到雲端** → 按「✅ 產生定案」→「🚀 送到雲端」。完成！系統每晚自動 LINE 提醒。

> 💡 **定案自動儲存**：按完「產生定案」後，定案會自動存檔。就算關掉 app 再回來，點「📂 恢復上次定案」即可繼續，不用重新上傳班表。

---
### 每月稽核（推薦「⚡ 快速點選」，免上傳）：
**1️⃣ 切換模式** → 上方選「🟩 每月稽核」→ 稽核方式留在「⚡ 快速點選」，選好「年」「月」。
**2️⃣ 點選白/夜＋區** → 畫面列出組員，系統已帶出上個月的設定；只要改這個月有變動的人，點一下白班/小夜、一區/二區即可。
**3️⃣ 排稽核** → 按「✅ 排稽核（快速）」。
**4️⃣ 送到雲端** → 名單排出來後按「🚀 送稽核結果到雲端」。每位稽核者馬上收到 LINE 通知，告訴他們「這個月負責哪一班稽核」。

> 也可改用「📤 上傳班表分析」：傳這個月的週班表 Excel，系統自己猜白/夜＋區，你再確認。班表要「Excel 檔本人」，截圖不行。
""")

st.markdown("#### 1️⃣ 選種類")
mode = st.radio("要排哪一種？", ["🟦 每週印藥水", "🟩 每月稽核"], horizontal=True)

audit_quick = False
if mode.startswith("🟩"):
    method = st.radio("稽核方式", ["⚡ 快速點選（免上傳 Excel，推薦）", "📤 上傳班表分析"],
                      horizontal=True)
    audit_quick = method.startswith("⚡")

data = None; sheets = []
if not audit_quick:
    up = st.file_uploader("上傳班表 Excel（.xls / .xlsx）", type=["xls","xlsx"])
    if up:
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
    elif "cloud_rows" not in st.session_state:
        # No file, no restored draft → show hint and stop
        st.info("👆 先上傳班表 Excel（含每人每天班別/床號的那種檔）。截圖不行喔！")
        st.stop()


# ═══════════════════════ 每週印藥水 ═══════════════════════
if mode.startswith("🟦"):

    # Fix4：草稿恢復提示（只在尚未有定案、且有草稿時顯示）
    if "cloud_rows" not in st.session_state:
        _draft = _load_draft()
        if _draft:
            st.info(f"📂 找到上次的定案（{_draft.get('sheet0','')}），要恢復嗎？")
            col_y, col_n = st.columns(2)
            if col_y.button("✅ 恢復上次定案，直接送雲端"):
                try:
                    d = _draft["disp"]
                    disp_r = pd.DataFrame(d["data"], index=d["index"], columns=d["columns"])
                    st.session_state["cloud_rows"]   = _draft["rows"]
                    st.session_state["cloud_disp"]   = disp_r
                    st.session_state["cloud_sheet0"] = _draft["sheet0"]
                    st.rerun()
                except Exception as e:
                    st.error(f"恢復失敗：{e}")
            if col_n.button("❌ 不用，重新排"):
                _clear_draft()
                st.rerun()

    # 正常排班流程（需要班表檔）
    if data is not None:
        st.markdown("#### 2️⃣ 選這一週 → 排班 → 微調")
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
            st.caption("👇 想換人就直接點姓名格子改（日期自動沿用）。改好再按「產生定案」。")
            _edit_T = st.data_editor(names.T, use_container_width=True, key="yao_edit")
            edited = _edit_T.T   # 轉回 area×day 格式供後續邏輯使用
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
                _save_draft(rows, sheet0, disp)   # Fix4：自動存檔

    # 定案顯示（有定案就顯示，不管是否剛排班）
    if "cloud_rows" in st.session_state:
        rows   = st.session_state["cloud_rows"]
        disp   = st.session_state["cloud_disp"]
        sheet0 = st.session_state["cloud_sheet0"]
        st.success("✅ 定案完成！")
        st.dataframe(disp.T, use_container_width=True)   # 轉置：日期當列，區當欄，手機友善

        # LINE 公告文字（可長按複製 / 下載 txt 傳群組）
        _line_txt = _build_line_txt(rows)
        if _line_txt:
            st.markdown("**📋 LINE 群組公告格式**")
            st.text_area("長按複製，或下載 txt 直接傳 LINE 群組",
                         _line_txt, height=220, key="line_txt_preview")
            st.download_button("⬇️ 下載 txt 傳 LINE 群組",
                               _line_txt.encode("utf-8"),
                               file_name=f"印藥水名單_{sheet0}.txt",
                               mime="text/plain")

        with st.expander("🖼️ 下載排班圖片（PNG）"):
            _png = _disp_to_png(disp.T, title=f"印藥水名單（{sheet0}）")
            if _png:
                st.download_button("⬇️ 下載 PNG", _png,
                                   file_name=f"排班_{sheet0}.png", mime="image/png")
            else:
                st.caption("（圖片產生失敗，請用上方文字格式）")

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
                            _, _, _, updated_hist = st.session_state.get("yao",(None,None,None,{}))
                            corrected = build_corrected_history(
                                rows, sheet0, (updated_hist or {}).get("排班紀錄.csv"))
                            ok2 = push_history("setScheduleHistory", corrected, sheet0)
                            if ok2: st.caption("✅ 排班歷史已同步（依玉繡實際定案），下週公平輪序更準確。")
                            _clear_draft()   # 送出成功後清除草稿
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

    if "yao" in st.session_state and data is not None:
        _, files, _, _ = st.session_state["yao"]
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
        st.markdown("#### 2️⃣ 點選每人「白/夜」＋「區」→ 排稽核")
        st.caption("免上傳 Excel。系統已帶出上個月的設定，只要改這個月有變動的人即可。")
        roster = _load_roster_full()
        if not roster:
            st.error("找不到組員名單（組員名單.csv）。請先確認 repo 裡有這個檔。"); st.stop()
        prefill = fetch_last_audit_prefill()
        base = []
        for m in roster:
            typ, area = prefill.get(m["姓名"], ("白班", "一區"))
            if typ not in ("白班","小夜"): typ = "白班"
            if area not in ("一區","二區"): area = "一區"
            base.append({"卡號": m["卡號"], "姓名": m["姓名"], "班型": typ, "區": area})
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
