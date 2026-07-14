@echo off
rem 這支是給「工作排程器」在背景自動跑用的（沒有 pause，跑完自動關）。
rem 你平常不用點它；要手動查請用「每日查價.bat」。
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
python travelpayouts_flights.py
