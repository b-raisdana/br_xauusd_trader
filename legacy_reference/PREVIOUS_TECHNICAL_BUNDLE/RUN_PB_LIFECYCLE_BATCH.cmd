@echo off
setlocal
cd /d "%~dp0"
title XAUUSD PB Lifecycle Batch

echo.
echo XAUUSD PB Lifecycle Batch - Structure Valid + Reuse

set "PY="
if exist "%~dp0.runtime\python312_embed\python.exe" set "PY=%~dp0.runtime\python312_embed\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY (
  for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
)
if not defined PY (
  echo ERROR: usable Python runtime not found. Keep the existing .runtime from the bootstrap.
  pause
  exit /b 2
)

echo Python: %PY%
echo Script root: %~dp0
"%PY%" "%~dp0pb_lifecycle_batch.py"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo PB LIFECYCLE BATCH: PASS - send only the newest PB_LIFECYCLE_BATCH_*.zip from evidence.
) else (
  echo PB LIFECYCLE BATCH: FAIL - send the newest evidence ZIP or this console error. Do not rerun MT5.
)
echo.
pause
exit /b %RC%
