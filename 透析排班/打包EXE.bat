@echo off
rem ===== Dialysis: one-click build EXE (ASCII only to avoid garbled text) =====
chcp 65001 >nul
title Dialysis - Build EXE
set "PYTHONIOENCODING=utf-8"

rem Use the Python that has pandas (medbid). If path changed, edit next line.
set "PYEXE=C:\Users\wgz51\.conda\envs\medbid\python.exe"
if not exist "%PYEXE%" (
  where python >nul 2>nul && set "PYEXE=python"
)

"%PYEXE%" "%~dp0build_exe.py"

echo.
pause
