# -*- coding: utf-8 -*-
"""
自動打包工具：把「排班.py(印藥水)」「稽核.py」變成免安裝 .exe（放文書電腦用）。
------------------------------------------------------------------
你不用手動改任何程式！這支會自動做好「打包成 exe 需要的小修正」再打包：
  1) 讓 exe 把設定檔/輸出存在「exe 旁邊」(PyInstaller 預設會存到暫存區，會掉)。
  2) 跑完視窗會停住等你按 Enter(才看得到結果)。
原始的 排班.py / 稽核.py 不會被改動，會另外產生 _exe.py 暫存檔來打包。

用法：把這支放在「排班.py、稽核.py」同一個資料夾，執行「打包EXE.bat」即可。
完成後 exe 會在 dist 資料夾。
"""
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = [("排班.py", "排名單"), ("稽核.py", "稽核")]   # (原始檔, 產生的exe名)

OLD_BASE = "BASE = os.path.dirname(os.path.abspath(__file__))"
NEW_BASE = (
    'if getattr(sys, "frozen", False):\n'
    '    BASE = os.path.dirname(sys.executable)   # 打包成 exe 後，設定檔放 exe 旁邊\n'
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

def make_patched(src_path):
    s = open(src_path, encoding="utf-8").read()
    if OLD_BASE in s:
        s = s.replace(OLD_BASE, NEW_BASE)
    else:
        print(f"   ⚠ 在 {os.path.basename(src_path)} 找不到 BASE 那行，仍照原樣打包（設定檔位置可能要注意）")
    if OLD_MAIN in s:
        s = s.replace(OLD_MAIN, NEW_MAIN)
    out = src_path[:-3] + "_exe.py"
    open(out, "w", encoding="utf-8").write(s)
    return out

def main():
    print("== 透析排班 一鍵打包成 EXE ==\n")
    # 確保有 PyInstaller（第一次會自動裝，需要網路）
    try:
        import PyInstaller  # noqa
    except Exception:
        print("第一次使用，正在安裝 PyInstaller（需要網路）…")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=False)

    built = []
    for src, name in TARGETS:
        p = os.path.join(HERE, src)
        if not os.path.exists(p):
            print(f"⚠ 找不到 {src}，略過（要打包它就把它放進同資料夾）")
            continue
        patched = make_patched(p)
        print(f"\n→ 打包 {src} 成 {name}.exe …")
        r = subprocess.run([sys.executable, "-m", "PyInstaller", "--onefile",
                            "--noconfirm", "--clean", "--name", name,
                            "--hidden-import", "xlrd", "--hidden-import", "openpyxl",
                            patched], check=False)
        if r.returncode == 0:
            built.append(name + ".exe")
        try: os.remove(patched)
        except Exception: pass

    print("\n========================================")
    if built:
        print("✔ 打包完成！檔案在 dist 資料夾：")
        for b in built: print("   dist\\" + b)
        print("\n下一步：把 dist 裡的 .exe 和你的 .csv 設定檔，一起複製到文書電腦。")
    else:
        print("❌ 沒有成功打包任何檔，請把畫面拍給小巫看。")
    print("========================================")

if __name__ == "__main__":
    main()
