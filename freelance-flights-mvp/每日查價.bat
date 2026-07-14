@echo off
chcp 950 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
python travelpayouts_flights.py
echo.
pause
