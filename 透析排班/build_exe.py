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

def make_patched(src_path, ascii_name):
    s = open(src_path, encoding="utf-8").read()
    if OLD_BASE in s:
        s = s.replace(OLD_BASE, NEW_BASE)
    else:
        print("   warn: %s found no BASE line (setting-file location may need check)"
              % os.path.basename(src_path))
    if OLD_MAIN in s:
        s = s.replace(OLD_MAIN, NEW_MAIN)
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
    print("== Dialysis: build EXE ==\n")
    try:
        import PyInstaller  # noqa
    except Exception:
        print("First time: installing PyInstaller (needs internet)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=False)

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
               "--hidden-import", "xlrd", "--hidden-import", "openpyxl",
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
