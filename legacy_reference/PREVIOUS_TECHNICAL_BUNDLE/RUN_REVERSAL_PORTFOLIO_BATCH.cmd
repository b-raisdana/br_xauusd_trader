@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo XAUUSD Reversal + Portfolio Batch v2
echo.

set "PY=%CD%\.runtime\python312_embed\python.exe"
if not exist "%PY%" set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: Existing project Python runtime was not found.
  echo Do not reinstall Python or redownload ticks. Send this console output.
  pause
  exit /b 2
)

if not exist "%CD%\reversal_portfolio_batch.py" (
  echo ERROR: reversal_portfolio_batch.py is missing beside this CMD.
  echo Extract the patch into Project Root. Do not rerun MT5.
  pause
  exit /b 2
)

echo PRECHECK_PYTHON=PASS
echo PRECHECK_MAIN_SCRIPT=PASS
"%PY%" "%CD%\reversal_portfolio_batch.py"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo REVERSAL + PORTFOLIO BATCH: PASS
) else (
  echo REVERSAL + PORTFOLIO BATCH: FAIL - send the generated evidence ZIP or console output.
  echo Do not rerun MT5 tests or redownload ticks.
)
echo.
pause
exit /b %RC%
