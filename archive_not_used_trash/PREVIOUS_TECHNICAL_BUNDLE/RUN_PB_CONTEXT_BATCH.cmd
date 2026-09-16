@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title XAUUSD PB Context Batch

echo.
echo XAUUSD PB Context Batch

set "PY="
if exist ".runtime\python312_embed\python.exe" set "PY=.runtime\python312_embed\python.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"

if not defined PY (
  echo ERROR: No Python runtime found. Reuse the existing project runtime; do not reinstall unless it is actually missing.
  echo.
  pause
  exit /b 2
)

"%PY%" ".\pb_context_batch.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo PB CONTEXT BATCH: PASS - send the newest PB_CONTEXT_BATCH_*.zip from evidence.
) else (
  echo PB CONTEXT BATCH: FAIL - send the newest evidence ZIP or console error. Do not rerun prior tests.
)
echo.
pause
exit /b %RC%
