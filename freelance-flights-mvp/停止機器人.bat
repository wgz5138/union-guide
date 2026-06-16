@echo off
chcp 65001 >nul
rem 停止背景執行的 bot（結束所有 pythonw 程序）。
taskkill /im pythonw.exe /f >nul 2>&1
if %errorlevel%==0 (
  echo 已停止背景機器人。
) else (
  echo 目前沒有在背景跑的機器人（或已經停了）。
)
echo （註：這會結束所有 pythonw 背景程式；你電腦通常只有這支在用 pythonw。）
echo.
pause
