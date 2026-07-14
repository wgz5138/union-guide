@echo off
chcp 65001 >nul
schtasks /delete /tn "Google機票每日抓取" /f
echo.
echo 已取消「Google 機票每日抓取」。想再開啟就點「設定Google機票每天自動跑.bat」。
echo.
pause
