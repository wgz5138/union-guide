@echo off
chcp 65001 >nul
echo ============================================
echo   設定「每天自動抓 Google 機票」
echo ============================================
echo.
set TASKTIME=08:00
set /p TASKTIME=要每天幾點自動抓？（24小時制，例 08:00；直接 Enter 用 08:00）：
echo.
schtasks /create /tn "Google機票每日抓取" /tr "\"%~dp0_Google機票排程執行.bat\"" /sc daily /st %TASKTIME% /f
echo.
if %errorlevel%==0 (
  rem 加「錯過就盡快補跑」：到時電腦若關機/睡眠沒跑到，下次開機會自動補抓一次。
  powershell -NoProfile -Command "try{ $s=New-ScheduledTaskSettingsSet -StartWhenAvailable; Set-ScheduledTask -TaskName 'Google機票每日抓取' -Settings $s | Out-Null; Write-Host '[成功] 已開啟「錯過自動補跑」' }catch{ Write-Host '[提示] 補跑設定略過（不影響每日排程）' }" 2>nul
  echo [成功] 每天 %TASKTIME% 會自動抓 Google 機票並存進 data\gflights.csv。
  echo         每次排程結果記在 logs\schedule_runs.log。
  echo         注意：Google 需「非無頭模式」，到時會自動彈出瀏覽器視窗（正常）。
  echo         那個時間若關機/睡眠，開機後會自動補跑一次；取消請點「取消Google機票排程.bat」。
) else (
  echo [失敗] 若顯示「存取被拒」，請對本檔右鍵→以系統管理員身分執行再試。
)
echo.
pause
