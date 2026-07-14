@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
python gflights_scraper.py
echo.
pause
