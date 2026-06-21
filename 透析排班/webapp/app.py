# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）v2.2
  • 每週印藥水：上傳班表 → 排班 → 微調 → 送雲端（自動 LINE 提醒）
  • 每月稽核  ：上傳班表 → Stage1 確認班型 → 排稽核 → 送雲端（存稽核歷史）
  • 雲端歷史學習：排班/稽核紀錄存 Google 試算表，下次自動讀取，公平輪序越來越準
"""
import os, io, re, csv, tempfile, shutil, subprocess, sys
from datetime import date, datetime
import pandas as pd
import streamlit as st
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = ["組員名單.csv", "床號分區.csv", "不可印班別.csv", "休診日.csv",
          "排班紀錄.csv", "稽核紀錄.csv"]
CELL_RE = re.compile(r'^(.*?)\((\d+)/(\d+)印\)(.*)$')

def _detect_ext(b): return ".xlsx" if b[:4] == b'PK\x03\x04' else ".xls"


# ── 核心工具執行器 ────────────────────────────────────────
def run_tool(script, xls_bytes, extra_args, config_overrides=None):
    """執行排班/稽核子程序。
    config_overrides: {檔名: bytes} — 蓋掉 HERE 的設定檔（如雲端歷史 CSV）
    回傳 (stdout_str, output_files_dict, updated_history_dict)
    """
    work = tempfile.mkdtemp()
    try:
        for fn in CONFIG + [script]:
            src = os.path.join(HERE, fn)
            if os.path.exists(src):
                shutil.copy(src, work)
        if config_overrides:
            for fn, content in config_overrides.items():
                with open(os.path.join(work, fn), "wb") as f:
                    f.write(content)
        ext  = _detect_ext(xls_bytes)
        xlsp = os.path.join(work, f"上傳班表{ext}")
        with open(xlsp, "wb") as f: f.write(xls_bytes)
        r = subprocess.run([sys.executable, script, xlsp] + list(extra_args),
                           cwd=work, capture_output=True, text=True, timeout=180)
        files = {}
        od = os.path.join(work, "輸出")
        if os.path.isdir(od):
            for fn in sorted(os.listdir(od)):
                with open(os.path.join(od, fn), "rb") as fh:
                    files[fn] = fh.read()
        # 同步讀取更新後的歷史檔（排班紀錄.csv / 稽核紀錄.csv）
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
        if any(k in s for k in ("休息", "↳", "※", "❌", "借")) and "【公平累計】" not in s:
            notes.append(s)
    return notes


def parse_grid(df):
    names = df.copy(); dates = df.copy(); marks = df.copy()
    for r in df.index:
        for c in df.columns:
            v = str(df.loc[r, c]); m = CELL_RE.match(v)
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


# ── 雲端歷史：讀取 / 推送 ──────────────────────────────────
def fetch_history_csv(action):
    """從 Apps Script 取歷史紀錄，回傳 CSV bytes 或 None。"""
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
    """把更新後的歷史紀錄（某週/某月）推送到 Apps Script。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET or not hist_bytes: return False
    try:
        df = pd.read_csv(io.BytesIO(hist_bytes), encoding="utf-8-sig")
        key_col = df.columns[0]           # 第一欄是 週次 or 月份
        week_rows = df[df[key_col].astype(str) == str(key)].values.tolist()
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": action, "secret": WRITE_SECRET,
                                   "key": key, "rows": week_rows},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception: return False


# ── 月稽核 Stage 1：從 Excel 快速偵測班型 ─────────────────
def detect_shifts_quick(data, yy, mm):
    """從上傳的 Excel 讀取目標月份資料，判斷每人白/夜班型。
    回傳 DataFrame: 卡號 | 姓名 | 程式猜測 | 確認班型"""
    person = {}   # card_or_name -> {card, name, white, night}
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
        for sn in xls.sheet_names:
            try: df = pd.read_excel(io.BytesIO(data), sheet_name=sn, header=None)
            except Exception: continue
            # 找表頭列
            hr = None
            for i in range(len(df)):
                c0 = str(df.iat[i,0]).strip() if not pd.isna(df.iat[i,0]) else ""
                c1 = str(df.iat[i,1]).strip() if not pd.isna(df.iat[i,1]) else ""
                if c0 == "卡號" and c1 == "姓名": hr=i; break
            if hr is None: continue
            blocks=[c for c in range(df.shape[1])
                    if (not pd.isna(df.iat[hr,c])) and str(df.iat[hr,c]).strip()=="類別"]
            # 取各欄日期
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
                if key not in person:
                    person[key]={"card":card,"name":name,"white":0,"night":0}
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
st.caption("🟢 版本 v2.2（雲端歷史學習 / 稽核班型確認）· 2026-06-22")

with st.expander("📖 第一次用？點我看「3 步驟」（給玉繡）", expanded=False):
    st.markdown("""
### 每週印藥水，只要 3 步：
**1️⃣ 上傳班表** → 選「🟦 每週印藥水」，把這週班表 Excel 傳上來。
**2️⃣ 排 + 微調** → 選「這一週」分頁 → 按「➡️ 排印藥水」。想換人就直接點格子改名字。
**3️⃣ 產生定案 → 送到雲端** → 按「✅ 產生定案」→「🚀 送到雲端」。完成！系統每晚自動 LINE 提醒。

---
### 每月稽核，3 步：
**1️⃣ 上傳班表 + 選月份** → 選「🟩 每月稽核」，傳班表、選年月。
**2️⃣ 確認班型** → 按「📊 預覽班型」→ 核對/修改每人白班/夜班 → 按「✅ 確認班型 → 排稽核」。
**3️⃣ 送到雲端** → 排出名單後按「🚀 送稽核結果到雲端」。

⚠️ 班表要「Excel 檔本人」，截圖不行。重送會自動蓋掉上次。
""")

st.markdown("#### 1️⃣ 選種類 + 上傳班表")
mode = st.radio("要排哪一種？", ["🟦 每週印藥水", "🟩 每月稽核"], horizontal=True)
up   = st.file_uploader("上傳班表 Excel（.xls / .xlsx）", type=["xls","xlsx"])

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
    sheet = st.selectbox("選「這一週」的分頁", sheets, index=len(sheets)-1)

    if st.button("➡️ 排印藥水", type="primary"):
        with st.spinner("讀取雲端歷史 + 排班中…"):
            config_overrides = {}
            if APPS_SCRIPT_URL and WRITE_SECRET:
                hist_csv = fetch_history_csv("getScheduleHistory")
                if hist_csv:
                    config_overrides["排班紀錄.csv"] = hist_csv
            out, files, updated_hist = run_tool("排班.py", data, [sheet], config_overrides)
            st.session_state["yao"] = (out, files, sheet, updated_hist)

    if "yao" in st.session_state:
        out, files, sheet0, updated_hist = st.session_state["yao"]
        fn, b = pick(files, ".xlsx")
        if not b:
            st.error("沒產生名單，請看下方訊息。"); st.code(out); st.stop()
        grid = pd.read_excel(io.BytesIO(b), index_col=0).fillna("")
        names, dates, marks = parse_grid(grid)
        yr = year_from_cloud(files)

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
            cloud = pd.DataFrame(rows, columns=["印日期","區","姓名"])

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
                                # 同步推送排班歷史（讓下週公平輪序記住這週）
                                _,_,_,updated_hist = st.session_state.get("yao",(None,None,None,{}))
                                hist_b = (updated_hist or {}).get("排班紀錄.csv")
                                if hist_b:
                                    ok2 = push_history("setScheduleHistory", hist_b, sheet0)
                                    if ok2: st.caption("✅ 排班歷史已同步，下週公平輪序更準確。")
                            else:
                                st.error(f"送出失敗（{resp.status_code}）：{resp.text[:200]}")
                        except Exception as e:
                            st.error(f"送出失敗：{e}")
            else:
                st.warning("雲端直送尚未設定（請在 Streamlit Secrets 填 APPS_SCRIPT_URL 與 WRITE_SECRET）。")

            with st.expander("📋 手動備援（複製貼到試算表 / 下載 CSV）"):
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

    # 月份改變時清舊結果
    if st.session_state.get("ak_month_key") != month_key:
        st.session_state.pop("ak_shifts", None)
        st.session_state.pop("ak", None)
        st.session_state["ak_month_key"] = month_key

    # ── Stage 1：預覽 & 確認班型 ──────────────────────────
    st.markdown("#### 2️⃣ 確認班型（程式猜測 → 玉繡確認）")
    st.caption("程式從第二週班資料判斷白/夜，不確定的顯示 ❓，請手動改。")

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
        st.caption("👇 確認後才可以排稽核。可直接點「確認班型」欄改選項。")
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
            st.warning(f"⚠️ 還有 {uncertain} 人班型是 ❓，程式排稽核時這些人會暫時略過。")

        if st.button("✅ 確認班型 → 排稽核", type="primary"):
            with st.spinner("讀取雲端歷史 + 排稽核中…"):
                # 把確認的班型寫成 CSV，傳給稽核.py 做覆蓋
                override_df = edited_shifts[["卡號","姓名","確認班型"]].rename(columns={"確認班型":"班型"})
                override_csv = override_df.to_csv(index=False).encode("utf-8-sig")

                config_overrides = {"班型覆蓋.csv": override_csv}
                if APPS_SCRIPT_URL and WRITE_SECRET:
                    hist_csv = fetch_history_csv("getAuditHistory")
                    if hist_csv:
                        config_overrides["稽核紀錄.csv"] = hist_csv

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
                    hist_b = updated_hist.get("稽核紀錄.csv")
                    # 稽核.py 把本月紀錄輸出到 "稽核紀錄_輸出.csv"（在 files 裡）
                    ak_hist_b = files.get("稽核紀錄_輸出.csv")
                    if ak_hist_b:
                        ok2 = push_history("setAuditResult", ak_hist_b, month_key)
                        if ok2:
                            st.success(f"🎉 稽核歷史已送到雲端（{month_key}），下個月公平輪序更準確。")
                            st.balloons()
                        else:
                            st.warning("稽核歷史送出失敗，可下載備用。")
                    else:
                        st.warning("沒有找到稽核歷史輸出檔，請確認稽核.py 是否正常執行。")

        st.download_button("⬇️ 下載稽核名單（已套用修改）",
                           edited_ak.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"稽核名單_{month_key}.csv", mime="text/csv")
        with st.expander("⬇️ 其他檔案下載"):
            for fn, b in files.items():
                st.download_button(f"⬇️ {fn}", b, file_name=fn, key="akdl_"+fn)
