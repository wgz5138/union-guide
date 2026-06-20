# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）
  • 每週印藥水：上傳當週班表 → 選分頁 → 表格顯示名單(可直接改人名) → 產生定案/下載
  • 每月稽核  ：上傳當月班表 → 選年月 → 表格顯示 AK 名單(可改) → 下載
名單用「表格」呈現，自動對齊；跨區標 🔺。
"""
import os, io, re, tempfile, shutil, subprocess, sys
import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = ["組員名單.csv", "床號分區.csv", "不可印班別.csv", "休診日.csv",
          "排班紀錄.csv", "稽核紀錄.csv"]
CELL_RE = re.compile(r'^(.*?)\((\d+)/(\d+)印\)(.*)$')


def run_tool(script, xls_bytes, extra_args):
    work = tempfile.mkdtemp()
    for fn in CONFIG + [script]:
        src = os.path.join(HERE, fn)
        if os.path.exists(src):
            shutil.copy(src, work)
    xlsp = os.path.join(work, "上傳班表.xls")
    with open(xlsp, "wb") as f:
        f.write(xls_bytes)
    r = subprocess.run([sys.executable, script, xlsp] + list(extra_args),
                       cwd=work, capture_output=True, text=True, timeout=180)
    files = {}
    od = os.path.join(work, "輸出")
    if os.path.isdir(od):
        for fn in sorted(os.listdir(od)):
            with open(os.path.join(od, fn), "rb") as fh:
                files[fn] = fh.read()
    return r.stdout + (("\n" + r.stderr) if r.stderr.strip() else ""), files


def pick(files, suffix):
    for fn, b in files.items():
        if fn.endswith(suffix):
            return fn, b
    return None, None


def extract_notes(stdout):
    """抓「本週/本月休息」與「提醒/警告」幾行給玉繡看。"""
    notes = []
    for ln in stdout.splitlines():
        s = ln.strip()
        if any(k in s for k in ("休息", "↳", "※", "❌", "借")) and "【公平累計】" not in s:
            notes.append(s)
    return notes


def parse_grid(df):
    """印藥水格子 → (名字表, 日期表M/D, 記號表)。"""
    names = df.copy(); dates = df.copy(); marks = df.copy()
    for r in df.index:
        for c in df.columns:
            v = str(df.loc[r, c])
            m = CELL_RE.match(v)
            if m:
                names.loc[r, c] = m.group(1)
                dates.loc[r, c] = f"{int(m.group(2))}/{int(m.group(3))}"
                marks.loc[r, c] = m.group(4)
            else:
                names.loc[r, c] = v; dates.loc[r, c] = ""; marks.loc[r, c] = ""
    return names, dates, marks


def year_from_cloud(files):
    _, b = pick(files, ".csv")
    if b:
        try:
            d = pd.read_csv(io.BytesIO(b), encoding="utf-8-sig")
            return int(str(d["印日期"].iloc[0]).split("-")[0])
        except Exception:
            pass
    return pd.Timestamp.now().year


st.set_page_config(page_title="透析藥水排班", page_icon="💊", layout="wide")
st.title("💊 透析藥水排班")
st.caption("上傳班表 Excel → 出名單(表格)。可直接點格子改人名。跨區標 🔺。")

mode = st.radio("要排哪一種？", ["🟦 每週印藥水", "🟩 每月稽核"], horizontal=True)
up = st.file_uploader("上傳班表 Excel（.xls / .xlsx）", type=["xls", "xlsx"])

if not up:
    st.info("👆 先上傳班表 Excel（含每人每天班別/床號的那種檔）。")
    st.stop()

data = up.read()
try:
    sheets = pd.ExcelFile(io.BytesIO(data)).sheet_names
except Exception as e:
    st.error(f"讀不到班表分頁：{e}")
    st.stop()

# ============ 每週印藥水 ============
if mode.startswith("🟦"):
    sheet = st.selectbox("選「這一週」的分頁", sheets, index=len(sheets) - 1)
    if st.button("➡️ 排印藥水", type="primary"):
        with st.spinner("排班中…"):
            st.session_state["yao"] = run_tool("排班.py", data, [sheet]) + (sheet,)

    if "yao" in st.session_state:
        out, files, sheet0 = st.session_state["yao"]
        fn, b = pick(files, ".xlsx")
        if not b:
            st.error("沒產生名單，請看下方訊息。"); st.code(out); st.stop()
        grid = pd.read_excel(io.BytesIO(b), index_col=0).fillna("")
        names, dates, marks = parse_grid(grid)
        yr = year_from_cloud(files)

        st.subheader(f"印藥水名單（{sheet0}）")
        st.caption("可直接點格子改人名（日期會自動沿用）。")
        edited = st.data_editor(names, use_container_width=True, key="yao_edit")

        for n in extract_notes(out):
            st.write("・" + n)

        if st.button("✅ 產生定案（套用修改）"):
            disp = edited.copy()
            rows = []
            for r in edited.index:
                for c in edited.columns:
                    nm = str(edited.loc[r, c]).strip()
                    dt = dates.loc[r, c]; mk = marks.loc[r, c]
                    if nm and nm != "❌排不出":
                        disp.loc[r, c] = f"{nm}({dt}印){mk}" if dt else nm
                        if dt:
                            mo, dy = dt.split("/")
                            rows.append([f"{yr}-{int(mo):02d}-{int(dy):02d}", r, nm])
                    else:
                        disp.loc[r, c] = nm
            st.success("定案完成！")
            st.dataframe(disp, use_container_width=True)
            cloud = pd.DataFrame(rows, columns=["印日期", "區", "姓名"])
            st.download_button("⬇️ 下載「雲端貼上版」(給 LINE 提醒)",
                               cloud.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"雲端貼上_{sheet0}.csv", mime="text/csv")
        # 原始檔下載
        for fn, b in files.items():
            st.download_button(f"⬇️ {fn}", b, file_name=fn, key="dl_" + fn)

# ============ 每月稽核 ============
else:
    c1, c2 = st.columns(2)
    yy = c1.number_input("年", 2024, 2100, 2026)
    mm = c2.number_input("月", 1, 12, 6)
    if st.button("➡️ 排稽核", type="primary"):
        with st.spinner("排稽核中…"):
            st.session_state["ak"] = run_tool("稽核.py", data, [f"{int(yy)}-{int(mm):02d}"])

    if "ak" in st.session_state:
        out, files = st.session_state["ak"]
        fn, b = pick(files, ".xlsx")
        if not b:
            st.error("沒產生名單，請看下方訊息。"); st.code(out); st.stop()
        df = pd.read_excel(io.BytesIO(b)).fillna("")
        st.subheader(f"稽核 AK 名單（{int(yy)}-{int(mm):02d}）")
        st.caption("可直接點「稽核者」欄改人名。")
        edited = st.data_editor(df, use_container_width=True, key="ak_edit", hide_index=True)
        for n in extract_notes(out):
            st.write("・" + n)
        st.download_button("⬇️ 下載稽核名單(已套用修改)",
                           edited.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"稽核名單_{int(yy)}-{int(mm):02d}.csv", mime="text/csv")
        for fn, b in files.items():
            st.download_button(f"⬇️ {fn}", b, file_name=fn, key="akdl_" + fn)
