# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）
玉繡用法：手機開網址 → 選模式 → 上傳班表 Excel → 出名單。
  • 每週印藥水：上傳當週班表 → 選那一週分頁 → 出印藥水名單
  • 每月稽核  ：上傳當月班表 → 選月份     → 出整月 AK 名單
"""
import os, io, tempfile, shutil, subprocess, sys
import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = ["組員名單.csv", "床號分區.csv", "不可印班別.csv", "休診日.csv",
          "排班紀錄.csv", "稽核紀錄.csv"]


def run_tool(script, xls_bytes, extra_args):
    """在臨時資料夾跑 排班.py / 稽核.py（不動到 repo 內的記憶檔）。回傳 (文字輸出, {檔名:bytes})。"""
    work = tempfile.mkdtemp()
    for fn in CONFIG + [script]:
        src = os.path.join(HERE, fn)
        if os.path.exists(src):
            shutil.copy(src, work)
    xlsp = os.path.join(work, "上傳班表.xls")
    with open(xlsp, "wb") as f:
        f.write(xls_bytes)
    cmd = [sys.executable, script, xlsp] + list(extra_args)
    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=180)
    out = r.stdout + (("\n⚠ " + r.stderr) if r.stderr.strip() else "")
    files = {}
    od = os.path.join(work, "輸出")
    if os.path.isdir(od):
        for f in sorted(os.listdir(od)):
            with open(os.path.join(od, f), "rb") as fh:
                files[f] = fh.read()
    return out, files


def sheet_names(xls_bytes):
    try:
        return pd.ExcelFile(io.BytesIO(xls_bytes)).sheet_names
    except Exception as e:
        st.error(f"讀不到班表分頁：{e}")
        return []


st.set_page_config(page_title="透析藥水排班", page_icon="💊", layout="centered")
st.title("💊 透析藥水排班")
st.caption("上傳班表 Excel，自動排出名單。跨區會標 🔺。")

mode = st.radio("要排哪一種？", ["🟦 每週印藥水", "🟩 每月稽核"], horizontal=True)
up = st.file_uploader("上傳班表 Excel（.xls / .xlsx）", type=["xls", "xlsx"])

if up:
    data = up.read()
    sheets = sheet_names(data)

    if mode.startswith("🟦"):  # 每週印藥水
        if sheets:
            sheet = st.selectbox("選「這一週」的分頁", sheets, index=len(sheets) - 1)
            if st.button("➡️ 排印藥水", type="primary", use_container_width=True):
                with st.spinner("排班中…"):
                    out, files = run_tool("排班.py", data, [sheet])
                st.text(out)
                for fn, b in files.items():
                    st.download_button(f"⬇️ 下載 {fn}", b, file_name=fn, use_container_width=True)

    else:  # 每月稽核
        c1, c2 = st.columns(2)
        yy = c1.number_input("年", 2024, 2100, 2026)
        mm = c2.number_input("月", 1, 12, 6)
        if st.button("➡️ 排稽核", type="primary", use_container_width=True):
            with st.spinner("排稽核中…"):
                out, files = run_tool("稽核.py", data, [f"{int(yy)}-{int(mm):02d}"])
            st.text(out)
            for fn, b in files.items():
                st.download_button(f"⬇️ 下載 {fn}", b, file_name=fn, use_container_width=True)
else:
    st.info("👆 先上傳班表 Excel。班表就是平常那種含每人每天班別/床號的檔。")
