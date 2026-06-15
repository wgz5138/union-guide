@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
echo 機票聊天機器人啟動中… 去 Telegram 傳訊息給你的 bot 試試！
echo （要停止：在這個視窗按 Ctrl + C）
python telegram_bot.py
pause
