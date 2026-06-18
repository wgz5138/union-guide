@echo off
chcp 65001 >nul
echo ============================================
echo   設定「每天自動查機票 + 推 Telegram」
echo ============================================
echo.
set TASKTIME=09:00
set /p TASKTIME=要每天幾點自動查？（24小時制，例 09:00；直接按 Enter 用 09:00）：
echo.
schtasks /create /tn "機票每日查價" /tr "\"%~dp0_排程自動執行.bat\"" /sc daily /st %TASKTIME% /f
echo.
if %errorlevel%==0 (
  echo [成功] 以後每天 %TASKTIME% 電腦會自動查價，撿到便宜票就推到你 Telegram。
  echo         電腦關機或睡眠時不會跑，開機狀態才會。
  echo         想取消：點「取消每天自動跑.bat」。
) else (
  echo [失敗] 如果上面寫「存取被拒 / Access denied」，
  echo         請對本檔案按右鍵 → 以系統管理員身分執行，再試一次。
)
echo.
pause
