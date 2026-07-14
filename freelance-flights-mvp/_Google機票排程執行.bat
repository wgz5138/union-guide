@echo off
rem 給「工作排程器」自動跑用（無 pause，跑完自動關）。平常請用「查Google機票.bat」。
chcp 950 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
python gflights_scraper.py
