@echo off
rem ============================================================
rem  一鍵打包：把 排班.py / 稽核.py 變成免安裝 .exe
rem  用法：放在「排班.py、稽核.py、打包EXE.py」同一資料夾，雙擊我即可。
rem  ※ 第一次會自動裝 PyInstaller(需要網路)；之後不用。
rem ============================================================
chcp 65001 >nul
title 透析排班 - 一鍵打包成 EXE

rem 用裝了 pandas 的那個 Python(medbid)；若路徑變了改這行
set "PYEXE=C:\Users\wgz51\.conda\envs\medbid\python.exe"
if not exist "%PYEXE%" (
  where python >nul 2>nul && set "PYEXE=python"
)

"%PYEXE%" "%~dp0打包EXE.py"

echo.
pause
