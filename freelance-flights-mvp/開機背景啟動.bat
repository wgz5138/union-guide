@echo off
rem 給「開機自動啟動」用：靜默、無視窗在背景啟動聊天 bot。
rem 把這個檔案的「捷徑」放到開機啟動資料夾即可（做法見 README / 對話說明）。
cd /d "%~dp0"
set PYTHONUTF8=1
start "" pythonw telegram_bot.py
