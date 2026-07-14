@echo off
chcp 950 >nul
schtasks /delete /tn "機票每日查價" /f
echo.
if not %errorlevel%==0 goto notfound

echo 已取消「每天自動查價」。想再開啟就點「設定每天自動跑.bat」。
goto end

:notfound
echo 找不到這個排程，可能本來就沒設定過，或已經取消過了。

:end
echo.
pause
