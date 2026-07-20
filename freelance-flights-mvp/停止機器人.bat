@echo off
chcp 950 >nul
rem 停止機票 bot：不管是背景（pythonw）還是前景視窗（python）點開的都關掉。
rem 舊版只殺 pythonw.exe，若你也開過『啟動聊天機器人.bat』（前景 python.exe）
rem 會殺不掉、留著繼續跟新開的那份互相 409 衝突，所以改用命令列比對
rem 「有沒有在跑 telegram_bot.py」，兩種都抓得到，也不會誤殺電腦上其他
rem 跟這支無關的 python 程式。

powershell -NoProfile -Command ^
  "$found = $false; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*telegram_bot.py*' } | ForEach-Object { $found = $true; Stop-Process -Id $_.ProcessId -Force; Write-Host ('已關閉 PID ' + $_.ProcessId) }; if (-not $found) { Write-Host '目前沒有在跑的機器人，或是已經停了。' }"

echo.
echo 註：這會找出「命令列含 telegram_bot.py」的程序並關閉，
echo 不管是背景（pythonw）還是前景視窗（python）都會抓到；
echo 電腦上其他跟這支無關的 python 程式不會被動到。
echo.
pause
