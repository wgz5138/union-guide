@echo off
chcp 65001 >nul
echo ============================================
echo   設定「每天自動抓 Google 機票」
echo ============================================
echo.
set TASKTIME=08:00
set /p TASKTIME=要每天幾點自動抓？24小時制，例 08:00，直接 Enter 用 08:00：
echo.
schtasks /create /tn "Google機票每日抓取" /tr "\"%~dp0_Google機票排程執行.bat\"" /sc daily /st %TASKTIME% /f
echo.
if not %errorlevel%==0 goto fail

echo [成功] 每天 %TASKTIME% 會自動抓 Google 機票並存進 data\gflights.csv。
echo         注意：Google 需要真的開瀏覽器視窗才穩，到時會自動彈出瀏覽器視窗，屬正常現象。
echo         電腦關機或睡眠時不會執行；想取消請點「取消Google機票排程.bat」。
goto end

:fail
echo [失敗] 若上方顯示「存取被拒」，請對本檔按右鍵，選「以系統管理員身分執行」再試一次。

:end
echo.
pause
