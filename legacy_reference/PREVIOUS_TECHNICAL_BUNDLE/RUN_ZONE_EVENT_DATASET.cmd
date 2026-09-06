@echo off
setlocal
cd /d "%~dp0"
echo XAUUSD Zone Reaction/Event Dataset - Python fast path
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_zone_dataset.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo ZONE EVENT DATASET: PASS
  echo Upload the ZIP created under the evidence folder.
) else (
  echo ZONE EVENT DATASET: FAIL
  echo Upload the ZIP if created, otherwise send the last console error.
)
echo.
pause
exit /b %RC%
