@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
rem 用 pythonw 在「背景」啟動，不會留一個黑視窗。
start "" pythonw telegram_bot.py
echo ============================================
echo  機票 bot 已在背景啟動（沒有視窗，繼續在線聽你訊息）。
echo  你可以直接關掉這個視窗，bot 仍在背景跑。
echo.
echo  想停止它：點「停止機器人.bat」，或重開機。
echo ============================================
echo.
pause
