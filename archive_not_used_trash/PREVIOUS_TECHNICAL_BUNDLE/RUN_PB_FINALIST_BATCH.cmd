@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title XAUUSD PB Finalist Batch

echo.
echo XAUUSD PB Finalist / Runner / Conflict Batch

set "PY=%~dp0.runtime\python312_embed\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: project-local Python runtime not found.
  echo Keep this patch inside the existing XAUUSD_PY_RESEARCH_BOOTSTRAP_v4 root.
  pause
  exit /b 2
)

"%PY%" "%~dp0pb_finalist_batch.py"
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (
  echo.
  echo PB FINALIST BATCH: PASS
) else (
  echo.
  echo PB FINALIST BATCH: FAIL - send the newest PB_FINALIST_BATCH_*.zip. Do not rerun old stages or MT5.
)
echo.
pause
exit /b %RC%
