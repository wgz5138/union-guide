@echo off
chcp 950 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
python ask_flights.py
echo.
pause
