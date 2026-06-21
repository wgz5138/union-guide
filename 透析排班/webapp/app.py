# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）
  • 每週印藥水：上傳當週班表 → 選分頁 → 表格顯示名單(可直接改人名) → 產生定案/下載
  • 每月稽核  ：上傳當月班表 → 選年月 → 表格顯示 AK 名單(可改) → 下載
名單用「表格」呈現，自動對齊；跨區標 🔺。
"""
import os, io, re, tempfile, shutil, subprocess, sys
import pandas as pd
import streamlit as st
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = ["組員名單.csv", "床號分區.csv", "不可印班別.csv", "休診日.csv",
          "排班紀錄.csv", "稽核紀錄.csv"]
CELL_RE = re.compile(r'^(.*?)\((\d+)/(\d+)印\)(.*)$')

# xlsx magic bytes = PK header
def _detect_ext(xls_bytes):
    return ".xlsx" if xls_bytes[:4] == b'PK\x03\x04' else ".xls"


def run_tool(script, xls_bytes, extra_args):
    work = tempfile.mkdtemp()
    try:
        for fn in CONFIG + [script]:
            src = os.path.join(HERE, fn)
            if os.path.exists(src):
                shutil.copy(src, work)
        ext = _detect_ext(xls_bytes)
        xlsp = os.path.join(work, f"上傳班表{ext}")
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
        stdout = r.stdout
        stderr = r.stderr.strip()
        return stdout + (("\n" + stderr) if stderr else ""), files
    finally:
        shutil.rmtree(work, ignore_errors=True)


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


def _file_key(up):
    """用檔名+大小當 key，偵測使用者是否換了新檔案。"""
    return f"{up.name}_{up.size}"


st.set_page_config(page_title="透析藥水排班", page_icon="💊", layout="wide")

# 試算表（LINE 提醒讀這張）— 產生定案後把名單貼到它的「本週名單」分頁
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UF-DjDcrIPDbp016vkIyV9zsLF6Qz5EBo6Bq-z6t-Js/edit"

# 雲端直送（玉繡按一鍵就把名單寫進試算表）— 在 Streamlit Secrets 設定，不放進公開程式碼
try:
    APPS_SCRIPT_URL = st.secrets.get("APPS_SCRIPT_URL", "")
    WRITE_SECRET = st.secrets.get("WRITE_SECRET", "")
except Exception:
    APPS_SCRIPT_URL = ""
    WRITE_SECRET = ""

st.title("💊 透析藥水排班")
st.caption("上傳班表 Excel → 出名單(表格)。可直接點格子改人名。跨區標 🔺。")
st.caption("🟢 版本 v2.1（自動偵測副檔名 / 暫存自動清除）· 2026-06-22")

# ── 互動式導覽（給第一次用的人）──────────────────────
with st.expander("📖 第一次用？點我看「3 步驟」（給玉繡）", expanded=False):
    st.markdown(
        """
        ### 每週印藥水，只要 3 步：

        **1️⃣ 上傳班表** → 在下面選「🟦 每週印藥水」，把這週的班表 Excel 傳上來。

        **2️⃣ 排 + 微調** → 選「這一週」分頁 → 按「➡️ 排印藥水」。
        名單會出現在表格，**想換人就直接點格子改名字**（程式已算好公平輪序）。

        **3️⃣ 產生定案 → 送到雲端** → 按「✅ 產生定案」→ 按「🚀 送到雲端」。
        就完成了！名單會自動進雲端，系統每晚自動 LINE 提醒明天要印的人。
        **你不用碰試算表、不用複製貼上。**

        ---
        ⚠️ **小提醒**：班表要「Excel 檔本人」，截圖不行。
        重送一次會自動蓋掉上次的，不會重複。
        """
    )
# ────────────────────────────────────────────────

st.markdown("#### 1️⃣ 選種類 + 上傳班表")
mode = st.radio("要排哪一種？", ["🟦 每週印藥水", "🟩 每月稽核"], horizontal=True)
up = st.file_uploader("上傳班表 Excel（.xls / .xlsx）", type=["xls", "xlsx"])

if not up:
    st.info("👆 先上傳班表 Excel（含每人每天班別/床號的那種檔）。截圖不行喔！")
    st.stop()

# 換新檔案時清除舊的排班結果，避免顯示到舊名單
fk = _file_key(up)
if st.session_state.get("_last_file") != fk:
    for k in ["yao", "cloud_rows", "cloud_disp", "cloud_sheet0", "ak"]:
        st.session_state.pop(k, None)
    st.session_state["_last_file"] = fk

data = up.read()
try:
    sheets = pd.ExcelFile(io.BytesIO(data)).sheet_names
except Exception as e:
    st.error(f"讀不到班表分頁：{e}")
    st.stop()

# ============ 每週印藥水 ============
if mode.startswith("🟦"):
    st.markdown("#### 2️⃣ 選這一週 → 排班 → 微調")
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
        st.caption("👇 想換人就直接點格子改名字（日期會自動沿用）。改好再按下面的「產生定案」。")
        edited = st.data_editor(names, use_container_width=True, key="yao_edit")

        for n in extract_notes(out):
            st.write("・" + n)

        st.markdown("#### 3️⃣ 產生定案 → 送到雲端")
        if st.button("✅ 產生定案（套用修改）", type="primary"):
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
            rows.sort(key=lambda x: (x[0], x[1]))
            st.session_state["cloud_rows"] = rows
            st.session_state["cloud_disp"] = disp
            st.session_state["cloud_sheet0"] = sheet0

        if "cloud_rows" in st.session_state:
            rows = st.session_state["cloud_rows"]
            disp = st.session_state["cloud_disp"]
            sheet0 = st.session_state["cloud_sheet0"]
            st.success("✅ 定案完成！")
            st.dataframe(disp, use_container_width=True)
            cloud = pd.DataFrame(rows, columns=["印日期", "區", "姓名"])

            # ── 終極版：一鍵送到雲端（自動寫進試算表「本週名單」）──
            if APPS_SCRIPT_URL and WRITE_SECRET:
                if st.button("🚀 送到雲端（自動排提醒）", type="primary"):
                    with st.spinner("送出中，請稍候…"):
                        try:
                            resp = requests.post(
                                APPS_SCRIPT_URL,
                                json={"action": "setWeek", "secret": WRITE_SECRET,
                                      "rows": [[str(x) for x in r] for r in rows]},
                                timeout=45)
                            if resp.ok and '"ok":true' in resp.text:
                                st.success(f"🎉 已送到雲端！共 {len(rows)} 筆。"
                                           "系統會自動 LINE 提醒，你不用再做任何事。")
                                st.balloons()
                            else:
                                st.error(f"送出失敗（{resp.status_code}）：{resp.text[:200]}")
                        except Exception as e:
                            st.error(f"送出失敗：{e}")
            else:
                st.warning("雲端直送尚未設定（請在 Streamlit Secrets 填 "
                           "APPS_SCRIPT_URL 與 WRITE_SECRET）。可先用下面手動備援。")

            # ── 手動備援：一鍵複製 TSV / 下載 CSV ──
            with st.expander("📋 手動備援（複製貼到試算表 / 下載 CSV）"):
                tsv = cloud.to_csv(index=False, sep="\t")
                st.markdown("① 按右上角複製鈕　→　② 開試算表「本週名單」　→　③ 點 A1 貼上")
                st.code(tsv, language=None)
                st.link_button("🔗 開啟試算表（本週名單）", SHEET_URL)
                st.download_button("⬇️ 下載 CSV 檔",
                                   cloud.to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"雲端貼上_{sheet0}.csv", mime="text/csv")
        # 原始檔下載
        with st.expander("⬇️ 其他檔案下載（列印用 xlsx / 貼 LINE 用 txt）"):
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
