@echo off
chcp 950 >nul
schtasks /delete /tn "機票每日查價" /f
echo.
echo 已取消「每天自動查價」。想再開啟就點「設定每天自動跑.bat」。
echo.
pause
