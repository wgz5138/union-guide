@echo off
chcp 950 >nul
rem 停止背景執行的 bot，結束所有 pythonw 程序。
taskkill /im pythonw.exe /f >nul 2>&1
if %errorlevel%==0 goto stopped
if %errorlevel%==128 goto notrunning
goto failed

:stopped
echo 已停止背景機器人。
goto end

:notrunning
echo 目前沒有在背景跑的機器人，或是已經停了。
goto end

:failed
echo 停止失敗（非「找不到程序」的錯誤，可能是權限問題）。
echo 可嘗試以系統管理員身分重新執行本檔案。

:end
echo 註：這會結束所有 pythonw 背景程式，你電腦通常只有這支在用 pythonw。
echo.
pause
