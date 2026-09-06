@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0.runtime\python312_embed\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: Project-local Python was not found.
  echo Copy this patch into the SAME XAUUSD_PY_RESEARCH_BOOTSTRAP_v4 folder that already contains .runtime or .venv.
  pause
  exit /b 2
)
echo.
echo XAUUSD Trend Initialization Screen
"%PY%" "%~dp0trend_init_screen.py" --root "%~dp0"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo TREND INIT SCREEN: PASS - upload the newest TREND_INIT_SCREEN_*.zip from evidence.
) else (
  echo TREND INIT SCREEN: FAIL - send the console error. Do not rerun expensive MT5 tests.
)
echo.
pause
exit /b %RC%
