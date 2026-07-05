# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）v2.3
  • Fix1：公平歷史學玉繡實際決定，而非程式原排
  • Fix2：稽核送出後 LINE 通知每位稽核者責任班次
  • Fix3：自動選最接近今天的班表分頁
"""
import os, io, re, csv, json, base64, hashlib, tempfile, shutil, subprocess, sys
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
                    if (today - d).days > 180:
                        d = date(yr + 1, mo, dy)
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
        rows = [r[1:] for r in rows_raw[1:]]
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
    """把本機排班紀錄.csv 整批上傳到 GS 排班歷史（覆蓋，初始化用）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, 0, "未設定 URL/Secret"
    csv_path = os.path.join(HERE, "排班紀錄.csv")
    if not os.path.exists(csv_path): return False, 0, "找不到排班紀錄.csv"
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str).fillna("")
        rows = [list(r) for _, r in df.iterrows()]
        return _sync_to_gs("setAllScheduleHistory", rows)
    except Exception as e:
        return False, 0, str(e)

def sync_audit_history_from_csv():
    """把本機稽核紀錄.csv 整批上傳到 GS 稽核歷史（覆蓋，初始化用）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, 0, "未設定 URL/Secret"
    csv_path = os.path.join(HERE, "稽核紀錄.csv")
    if not os.path.exists(csv_path): return False, 0, "找不到稽核紀錄.csv"
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str).fillna("")
        rows = [list(r) for _, r in df.iterrows()]
        return _sync_to_gs("setAllAuditHistory", rows)
    except Exception as e:
        return False, 0, str(e)

def _reconstruct_disp_from_rows(rows):
    """從 cloud_rows 重建簡化版 disp DataFrame（日期×區 的 pivot，供草稿檢視）。"""
    if not rows: return pd.DataFrame()
    try:
        df = pd.DataFrame([[str(v) for v in r] for r in rows], columns=["印日期","區","姓名"])
        pivot = df.pivot_table(index="區", columns="印日期", values="姓名", aggfunc="first").fillna("")
        pivot.index.name = None; pivot.columns.name = None
        return pivot
    except Exception:
        return pd.DataFrame(rows, columns=["印日期","區","姓名"])

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
        return f"{DOW[d.weekday()]} {d.month}/{d.day}"

    # treats: list of {t: 治療日str, p: 印藥水日str, a: {area: name}}
    treats = []

    if disp_df is not None:
        for col in disp_df.columns:
            t_yr, t_mo, t_dy = _parse_col(col)
            if t_yr is None: continue
            t_str = _dstr(t_yr, t_mo, t_dy)

            assigns = {}
            print_str = None   # 取第一個有(印)標注的印藥水日
            for area in ["一區","二區","三區"]:
                if area not in disp_df.index: continue
                v = str(disp_df.loc[area, col]).strip()
                if not v or v in ("nan","None","❌排不出"): continue
                nm_m = CELL_RE.match(v)
                if nm_m:
                    nm = nm_m.group(1).strip() + nm_m.group(4).strip()  # 保留 🔺
                    p_mo, p_dy = int(nm_m.group(2)), int(nm_m.group(3))
                    if print_str is None:
                        print_str = _dstr(t_yr, p_mo, p_dy)
                else:
                    nm = v
                if nm:
                    assigns[area] = nm

            if assigns:
                treats.append({"t": t_str, "p": print_str or t_str, "a": assigns})
    else:
        # fallback：印藥水日分組（可能碰撞，舊行為）
        tmp = {}
        for r in rows:
            p_str, area, name = str(r[0]), str(r[1]), str(r[2])
            if not name or name in ("","❌排不出"): continue
            if p_str not in tmp: tmp[p_str] = {}
            tmp[p_str][area] = name
        for p_str in sorted(tmp):
            treats.append({"t": p_str, "p": p_str, "a": tmp[p_str]})

    if not treats: return ""
    treats.sort(key=lambda x: x["t"])   # 依治療日排序

    # 標題用治療日範圍（說明這週涵蓋哪幾天）
    lines = [f"印藥水名單 (治療日 {fmt(treats[0]['t'])}~ {fmt(treats[-1]['t'])})", ""]

    for e in treats:
        line = fmt(e["p"])   # 左欄 = 印藥水日期
        for area in ["一區","二區","三區"]:
            nm = e["a"].get(area, "")
            if nm: line += f"\t{area}:{nm}"
        lines.append(line)

    roster = _load_roster_full()
    if roster:
        printing = set()
        for e in treats: printing.update(e["a"].values())
        resting = [m["姓名"] for m in roster if m["姓名"] not in printing]
        if resting:
            lines += ["", "休息：" + "、".join(resting)]
    return "\n".join(lines)


# ── 💬 意見回饋：借用稽核歷史（特殊鍵「意見-時間」）存放，不動 LINE 程式 ──
APP_VER = "v3.12"
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
st.caption("🟢 版本 v3.12（新增印/休明細查詢）· 2026-07-03")

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
            for k in ["yao", "cloud_rows", "cloud_disp", "cloud_sheet0"]:
                st.session_state.pop(k, None)
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
            if _cy.button("✅ 恢復，直接送雲端"):
                try:
                    _d = _wd["disp"]
                    st.session_state["cloud_rows"]   = _wd["rows"]
                    st.session_state["cloud_disp"]   = pd.DataFrame(
                        _d["data"], index=_d["index"], columns=_d["columns"])
                    st.session_state["cloud_sheet0"] = _wd["sheet0"]
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

        if st.button("➡️ 排印藥水", type="primary"):
            with st.spinner("讀取雲端歷史 + 排班中…"):
                config_overrides = {}
                if APPS_SCRIPT_URL and WRITE_SECRET:
                    hist_csv = fetch_history_csv("getScheduleHistory")
                    if hist_csv: config_overrides["排班紀錄.csv"] = hist_csv
                    mem_csv = fetch_members_as_csv()
                    if mem_csv: config_overrides["組員名單.csv"] = mem_csv
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
            yr    = year_from_cloud(files)

            # 自動套回上次定案的修改（如顏凰任→張雅雯），避免重排後又要重改
            override_names = names.copy()
            _prev_rows  = st.session_state.get("cloud_rows", [])
            _prev_sheet = st.session_state.get("cloud_sheet0", "")
            if _prev_rows and _prev_sheet == sheet0:
                for _cr in _prev_rows:
                    try:
                        _dstr, _area, _nm = _cr[0], _cr[1], _cr[2]
                        _mo = int(_dstr.split('-')[1]); _dy = int(_dstr.split('-')[2])
                        _tgt = f"{_mo}/{_dy}"
                        for _col in dates.columns:
                            if str(dates.loc[_area, _col]).strip() == _tgt:
                                override_names.loc[_area, _col] = _nm
                                break
                    except Exception:
                        pass

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
                        nm = re.sub(r'🔺', '', raw_val).strip()  # 去掉顯示用標記
                        # 以 editor 內容為準：用戶有加 🔺 就保留，有去掉就不補
                        mk = "🔺" if "🔺" in raw_val else ""
                        dt = dates.loc[r,c]
                        if nm and nm != "❌排不出":
                            disp.loc[r,c] = f"{nm}({dt}印){mk}" if dt else f"{nm}{mk}"
                            if dt:
                                mo,dy = dt.split("/")
                                rows.append([f"{yr}-{int(mo):02d}-{int(dy):02d}", r, nm])
                        else:
                            disp.loc[r,c] = nm
                rows.sort(key=lambda x:(x[0],x[1]))
                st.session_state["cloud_rows"]   = rows
                st.session_state["cloud_disp"]   = disp
                st.session_state["cloud_sheet0"] = sheet0
                _save_week_draft(rows, sheet0, disp)   # 自動存本機
                if not TEST_MODE and APPS_SCRIPT_URL and WRITE_SECRET:
                    push_week_draft(rows, sheet0)      # 自動存雲端草稿（含手動修改）

    # 定案顯示（有定案就顯示，不管是否剛排班）
    if "cloud_rows" in st.session_state:
        rows   = st.session_state["cloud_rows"]
        disp   = st.session_state["cloud_disp"]
        sheet0 = st.session_state["cloud_sheet0"]
        st.success("✅ 定案完成！")
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
        _line_txt = _build_line_txt(rows, disp_df=disp)
        if _line_txt:
            st.markdown("**📋 LINE 群組公告格式**")
            st.text_area("長按複製，或按下方按鈕下載 txt 傳 LINE",
                         _line_txt, height=220, key="line_txt_box")
            st.download_button("⬇️ 下載 txt 傳 LINE 群組",
                               _line_txt.encode("utf-8"),
                               file_name=f"印藥水名單_{sheet0}.txt",
                               mime="text/plain")

        if TEST_MODE:
            if st.button("🧪 送到雲端（測試模擬）", type="secondary"):
                st.info(f"🧪 測試模式：模擬送出 {len(rows)} 筆，但實際上**沒有**寫到雲端，也沒有送 LINE 通知。")
                st.balloons()
        elif APPS_SCRIPT_URL and WRITE_SECRET:
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
                            _clear_week_draft()         # 清除本機草稿
                            clear_week_draft_cloud()    # 清除雲端草稿（小巫偵測會消失）
                            st.session_state.pop("week_draft_auto", None)
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
                    hist_csv = fetch_history_csv("getAuditHistory")
                    if hist_csv: config_overrides["稽核紀錄.csv"] = hist_csv
                    mem_csv = fetch_members_as_csv()
                    if mem_csv: config_overrides["組員名單.csv"] = mem_csv
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
                        mem_csv = fetch_members_as_csv()
                        if mem_csv: config_overrides["組員名單.csv"] = mem_csv
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
    tab1, tab2, tab3, tab4 = st.tabs(["📋 印藥水統計", "📋 稽核統計", "📋 最新稽核名單", "👥 組員名單"])

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
                           help="把 repo 裡的排班紀錄.csv（含今年全年歷史）整批上傳到雲端，覆蓋現有資料。"):
                with st.spinner("上傳中，請稍候…"):
                    _sok, _sn, _serr = sync_schedule_history_from_csv()
                if _sok:
                    st.success(f"✅ 已同步 {_sn} 筆排班歷史到雲端！按「🔄 讀取」確認。")
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
                if TEST_MODE:
                    if st.button("🧪 存回雲端（模擬）", key="stats_save_test"):
                        st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
                elif APPS_SCRIPT_URL and WRITE_SECRET:
                    if st.button("💾 存回雲端", type="primary", key="stats_save"):
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
                           help="把 repo 裡的稽核紀錄.csv（含今年全年歷史）整批上傳到雲端，覆蓋現有資料。"):
                with st.spinner("上傳中，請稍候…"):
                    _aok, _an, _aerr = sync_audit_history_from_csv()
                if _aok:
                    st.success(f"✅ 已同步 {_an} 筆稽核歷史到雲端！按「🔄 讀取」確認。")
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
                if TEST_MODE:
                    if st.button("🧪 存回雲端（模擬）", key="audit_stats_save_test"):
                        st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
                elif APPS_SCRIPT_URL and WRITE_SECRET:
                    if st.button("💾 存回雲端", type="primary", key="audit_stats_save"):
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
                      help="第一次使用：把 repo 裡的 組員名單.csv 上傳到雲端，之後就以雲端為主。"):
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
