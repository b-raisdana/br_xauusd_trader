@echo off
setlocal
cd /d "%~dp0"
echo.
echo XAUUSD PB Window Exact-Tick Research Replay v2
set "PY=%~dp0.runtime\python312_embed\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Existing project Python runtime not found. Do not reinstall Python or redownload ticks.
    echo Copy this patch into the existing XAUUSD_PY_RESEARCH_BOOTSTRAP_v4 root.
    pause
    exit /b 2
  )
  set "PY=python"
)
"%PY%" "%~dp0pb_window_replay.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo PB WINDOW REPLAY: PASS
) else (
  echo PB WINDOW REPLAY: FAIL - send newest PB_WINDOW_REPLAY_*.zip from evidence. No MT5 rerun.
)
echo.
pause
exit /b %RC%
