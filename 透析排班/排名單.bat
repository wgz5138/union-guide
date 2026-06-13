@echo off
rem ============================================================
rem  透析印藥水排班 - 一鍵產生名單  (排名單.bat)
rem  用法1：把醫院的班表 Excel「拖」到這個檔案上放開
rem  用法2：直接「雙擊」這個檔案，再貼上班表路徑
rem  放置位置：請放在「排班.py」同一個資料夾（例如 F:\透析排班\）
rem ============================================================
chcp 65001 >nul
setlocal
title 透析印藥水排班 - 一鍵產生名單
set "PYTHONIOENCODING=utf-8"

rem ===== 若 Python 路徑換了，改下面這一行就好 =====
set "PYEXE=C:\Users\wgz51\.conda\envs\medbid\python.exe"

rem 找不到上面那個 Python 就改用系統 PATH 上的 python
if not exist "%PYEXE%" (
  where python >nul 2>nul && set "PYEXE=python"
)

rem 排班.py 跟本檔放同一資料夾(%~dp0 = 本檔所在資料夾)
set "SCRIPT=%~dp0排班.py"
if not exist "%SCRIPT%" (
  echo [錯誤] 找不到排班程式：%SCRIPT%
  echo 請把這個 .bat 放在「排班.py」同一個資料夾裡，再試一次。
  goto end
)

rem 取得拖進來的班表檔(%~1)；若沒有就請使用者貼路徑
set "XLS=%~1"
if "%XLS%"=="" (
  echo.
  echo 請把醫院的班表 Excel「拖」到這個檔案上放開即可自動產生名單。
  echo 或在下面直接貼上班表的完整路徑後按 Enter：
  set /p "XLS=班表路徑："
)
if "%XLS%"=="" (
  echo [提醒] 沒有提供班表檔，結束。
  goto end
)
if not exist "%XLS%" (
  echo [錯誤] 找不到這個班表檔：%XLS%
  goto end
)

echo.
echo ====== 開始產生名單 ======
"%PYEXE%" "%SCRIPT%" "%XLS%"

:end
echo.
echo ====== 結束（看完訊息後，按任意鍵關閉視窗）======
pause >nul
endlocal
