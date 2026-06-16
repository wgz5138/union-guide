@echo off
rem 個人專用（非交付客主）：跑 Google 機票抓取 + 降價時推 Telegram 給我自己。
rem 客主交付請用「查Google機票.bat / 設定Google機票每天自動跑.bat」（那些不含通知）。
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
python 我的機票降價通知.py
echo.
pause
