# -*- coding: utf-8 -*-
"""
自動打包工具：把「排班.py(印藥水)」「稽核.py」變成免安裝 .exe。
你不用手動改任何程式！這支會自動做好打包需要的小修正再打包。
原始 排班.py / 稽核.py 不會被改動（只用暫存副本打包）。
由 打包EXE.bat 呼叫執行。
"""
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")
WORK = os.path.join(HERE, "build")
# (原始檔, 打包暫用英文名, 最後改成的中文 exe 名)
TARGETS = [("排班.py", "yaoshui", "排名單"), ("稽核.py", "audit", "稽核")]

OLD_BASE = "BASE = os.path.dirname(os.path.abspath(__file__))"
NEW_BASE = (
    'if getattr(sys, "frozen", False):\n'
    '    BASE = os.path.dirname(sys.executable)   # 打包成 exe 後設定檔放 exe 旁邊\n'
    'else:\n'
    '    BASE = os.path.dirname(os.path.abspath(__file__))'
)
OLD_MAIN = 'if __name__=="__main__":\n    main()'
NEW_MAIN = (
    'if __name__=="__main__":\n'
    '    main()\n'
    '    try:\n'
    '        import sys as _s\n'
    '        if getattr(_s, "frozen", False): input("\\n按 Enter 鍵關閉視窗…")\n'
    '    except Exception: pass'
)

# 印藥水(排班.py)預設抓最後一個分頁；若最後是空白頁會報錯 → 改成抓「最後一個有卡號/姓名表頭」的分頁
OLD_SHEET = "    if sheet is None: sheet=xls.sheet_names[-1]"
NEW_SHEET = (
    "    if sheet is None:\n"
    "        sheet=xls.sheet_names[-1]\n"
    "        for _sn in reversed(xls.sheet_names):\n"
    "            try:\n"
    "                _df=pd.read_excel(path,sheet_name=_sn,header=None)\n"
    "                if any((_cell(_df,_i,0)=='卡號' and _cell(_df,_i,1)=='姓名') for _i in range(len(_df))):\n"
    "                    sheet=_sn; break\n"
    "            except Exception: pass"
)

# 在 frozen(exe) 環境，pandas 有時判不出 .xls 格式 → 直接依副檔名指定引擎
SHIM = (
    "import pandas as pd\n"
    "# === exe 相容修正：.xls→xlrd, .xlsx→openpyxl ===\n"
    "def _xl_engine(_io):\n"
    "    try:\n"
    "        _t = str(_io).lower()\n"
    "        if _t.endswith('.xlsx') or _t.endswith('.xlsm'): return 'openpyxl'\n"
    "        if _t.endswith('.xls'): return 'xlrd'\n"
    "    except Exception: pass\n"
    "    return None\n"
    "_ORIG_EF = pd.ExcelFile\n"
    "_ORIG_RE = pd.read_excel\n"
    "def _EF(io, *a, **k):\n"
    "    if not k.get('engine'):\n"
    "        e=_xl_engine(io)\n"
    "        if e: k['engine']=e\n"
    "    return _ORIG_EF(io, *a, **k)\n"
    "def _RE(io, *a, **k):\n"
    "    if not k.get('engine'):\n"
    "        e=_xl_engine(io)\n"
    "        if e: k['engine']=e\n"
    "    return _ORIG_RE(io, *a, **k)\n"
    "pd.ExcelFile = _EF\n"
    "pd.read_excel = _RE\n"
    "# === 修正結束 ==="
)

# 印藥水:多輸出一個「雲端貼上版」CSV(印日期,區,姓名)→ 玉繡貼進 Google 表
CLOUD_ANCHOR = "    # ---------- 寫回歷史(同一週覆蓋,不重複累計) ----------"
CLOUD_BLOCK = (
    "    # ---------- 雲端貼上版(印日期,區,姓名)→ 給 Google 表 / LINE 提醒 ----------\n"
    "    out_c=os.path.join(OUT_DIR,f\"雲端貼上_{sheet}.csv\")\n"
    "    try:\n"
    "        with open(out_c,\"w\",newline=\"\",encoding=\"utf-8-sig\") as f:\n"
    "            w=csv.writer(f); w.writerow([\"印日期\",\"區\",\"姓名\"])\n"
    "            for T in window:\n"
    "                for A in PRINT_AREAS:\n"
    "                    c=assign_slot.get((T,A))\n"
    "                    if not c: continue\n"
    "                    src=slot_info[(T,A)][1]\n"
    "                    w.writerow([f\"{src.year}-{src.month:02d}-{src.day:02d}\", A, nm(c)])\n"
    "        print(f\"\\u2714 雲端貼上版：{out_c}\")\n"
    "    except Exception as e:\n"
    "        warn(f\"⚠ 寫雲端貼上版失敗：{e}\")\n\n"
)


def make_patched(src_path, ascii_name):
    s = open(src_path, encoding="utf-8").read()
    if OLD_BASE in s:
        s = s.replace(OLD_BASE, NEW_BASE)
    else:
        print("   warn: %s found no BASE line (setting-file location may need check)"
              % os.path.basename(src_path))
    if OLD_MAIN in s:
        s = s.replace(OLD_MAIN, NEW_MAIN)
    if "import pandas as pd" in s and "_xl_engine" not in s:
        s = s.replace("import pandas as pd", SHIM, 1)   # 注入 Excel 引擎相容修正
    if OLD_SHEET in s:                                   # 印藥水:自動跳過空白分頁
        s = s.replace(OLD_SHEET, NEW_SHEET)
    # 印藥水:跨區標記「跨/跨區」改成 🔺(玉繡習慣的紅三角)
    s = s.replace('if isc: tag+="跨"', 'if isc: tag+="🔺"')
    s = s.replace('if isc: t+="跨區"', 'if isc: t+="🔺"')
    s = s.replace('"跨區" in v or "雙印" in v', '"🔺" in v or "雙印" in v')
    if CLOUD_ANCHOR in s and "雲端貼上" not in s:        # 印藥水:加雲端貼上版輸出
        s = s.replace(CLOUD_ANCHOR, CLOUD_BLOCK + CLOUD_ANCHOR)
    out = os.path.join(HERE, "_%s_build.py" % ascii_name)   # 純英文暫存檔名
    open(out, "w", encoding="utf-8").write(s)
    return out

def find_extra_binary_args():
    """conda 環境常缺 libffi(_ctypes 要用)。找出來用 --add-binary 一起包進去。"""
    import glob
    env = os.path.dirname(sys.executable)            # ...\envs\medbid
    cand_dirs = [os.path.join(env, "Library", "bin"),
                 os.path.join(env, "DLLs"),
                 env,
                 os.path.join(env, "Library", "mingw-w64", "bin")]
    patterns = ["libffi*.dll", "ffi*.dll"]
    found = []
    for d in cand_dirs:
        for pat in patterns:
            found += glob.glob(os.path.join(d, pat))
    found = list(dict.fromkeys(found))               # 去重
    args = []
    for dll in found:
        args += ["--add-binary", dll + os.pathsep + "."]   # Windows 上 os.pathsep=';'
    if found:
        print("找到並會打包的 DLL：")
        for f in found: print("   " + f)
    else:
        print("⚠ 沒找到 libffi DLL，若打包後仍報 _ctypes 錯，請把畫面拍給小巫。")
    return args

def main():
    print("==================================================")
    print("====  build_exe  版本 v4 (xlrd 引擎修正)  ====")
    print("==================================================\n")
    print("確認/安裝必要套件(pyinstaller, xlrd, openpyxl)，需要網路，第一次較久…")
    subprocess.run([sys.executable, "-m", "pip", "install",
                    "pyinstaller", "xlrd", "openpyxl"], check=False)
    try:
        import xlrd as _x; print("   xlrd 狀態：OK  版本 %s" % _x.__version__)
    except Exception as e:
        print("   ⚠ xlrd 仍無法載入：%s" % e)

    extra = find_extra_binary_args()
    built = []
    for src, aname, cname in TARGETS:
        p = os.path.join(HERE, src)
        if not os.path.exists(p):
            print("skip: %s not found" % src)
            continue
        patched = make_patched(p, aname)
        print("\n-> building %s  ->  %s.exe ..." % (src, cname))
        cmd = [sys.executable, "-m", "PyInstaller", "--onefile",
               "--noconfirm", "--clean", "--name", aname,
               "--distpath", DIST, "--workpath", WORK, "--specpath", HERE,
               "--collect-all", "xlrd", "--collect-all", "openpyxl",
               "--exclude-module", "matplotlib"] + extra + [patched]
        subprocess.run(cmd, check=False)
        # 打包出的是英文名 exe → 改成中文名
        src_exe = os.path.join(DIST, aname + ".exe")
        dst_exe = os.path.join(DIST, cname + ".exe")
        if os.path.exists(src_exe):
            try:
                if os.path.exists(dst_exe): os.remove(dst_exe)
                os.replace(src_exe, dst_exe); built.append(cname + ".exe")
            except Exception as e:
                print("   rename fail, exe name = %s.exe (%s)" % (aname, e))
                built.append(aname + ".exe")
        try: os.remove(patched)
        except Exception: pass

    print("\n========================================")
    if built:
        print("OK! 打包完成，檔案在 dist 資料夾：")
        for b in built: print("   dist\\" + b)
        print("\n下一步：把 dist 裡的 .exe + 你的 .csv 設定檔，複製到文書電腦。")
    else:
        print("沒有成功打包，請把整個畫面拍給小巫。")
    print("========================================")

if __name__ == "__main__":
    main()
