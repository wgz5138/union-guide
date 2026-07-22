@echo off
chcp 950 >nul
cd /d "%~dp0"
rem 一鍵更新：拉最新程式碼＋自動重開機器人。
rem 緣由：之前發現使用者這台電腦的檔案停在很舊的版本（沒有一鍵拉更新的工具，
rem 容易忘記手動 git pull；就算 pull 了，Python 也不會自動吃到新程式碼，
rem 舊的 process 還在跑就等於白 pull），這支把「拉新版」跟「重開讓它生效」
rem 兩步合成一步，之後不用再記兩件事。

echo ============================================
echo  第 1 步：清掉暫存的價格記憶檔（避免跟遠端衝突）...
echo ============================================
rem price_state.json 只是「上次查到的價格」暫存檔，用來判斷有沒有降價，
rem 不是重要資料，遺失也只是下次查價時被當成第一次看到而已。
rem 本機用 bot 查過價（含探索模式）就會更新這個檔案，容易跟遠端版本
rem 衝突擋住 git pull，所以每次更新前先把「本機這一份」蓋掉、以遠端為準。
git checkout -- price_state.json >nul 2>&1

echo.
echo ============================================
echo  第 2 步：拉最新程式碼...
echo ============================================
git pull origin main
if errorlevel 1 (
    echo.
    echo 更新失敗！可能是網路問題，或本機有其他跟遠端衝突的修改
    echo （不是 price_state.json 的話，上一步不會處理）。
    echo 請把上面完整的錯誤訊息複製給 Claude，不要自己亂試。
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  第 3 步：停止舊版機器人...
echo ============================================
powershell -NoProfile -Command "$found = $false; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*telegram_bot.py*' } | ForEach-Object { $found = $true; Stop-Process -Id $_.ProcessId -Force; Write-Host ('已關閉 PID ' + $_.ProcessId) }; if (-not $found) { Write-Host '原本沒有在跑的機器人（第一次啟動，正常）。' }"

echo.
echo ============================================
echo  第 4 步：背景啟動新版機器人...
echo ============================================
set PYTHONUTF8=1
start "" pythonw telegram_bot.py

echo.
echo ============================================
echo  完成！新版機器人已經在背景啟動（沒有視窗，正常）。
echo  用手機傳「說明」給 bot 測試看看有沒有回應。
echo ============================================
echo.
pause
