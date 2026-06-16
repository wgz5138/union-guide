@echo off
rem 給「工作排程器」自動跑用（無 pause，跑完自動關）。平常手動請用「查Google機票.bat」。
rem 強化：整支程式若硬當掉（例如瀏覽器啟動失敗），自動重跑最多 3 次；每次排程結果記進 logs\schedule_runs.log。
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist "logs" mkdir logs

set TRIES=3
set N=0

:run
set /a N+=1
echo [%date% %time%] 第 %N% 次嘗試排程抓取>> "logs\schedule_runs.log"
python gflights_scraper.py
if "%errorlevel%"=="0" (
  echo [%date% %time%] 第 %N% 次成功完成>> "logs\schedule_runs.log"
  goto done
)
echo [%date% %time%] 第 %N% 次失敗（errorlevel=%errorlevel%）>> "logs\schedule_runs.log"
if %N% lss %TRIES% (
  rem 失敗等 60 秒再重跑（ping 當 sleep，Windows 內建）
  ping -n 61 127.0.0.1 >nul
  goto run
)
echo [%date% %time%] 已重試 %TRIES% 次仍失敗，放棄本次排程>> "logs\schedule_runs.log"

:done
