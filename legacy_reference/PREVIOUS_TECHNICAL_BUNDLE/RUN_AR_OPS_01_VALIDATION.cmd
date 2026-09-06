@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_project.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo AR-OPS-01 VALIDATION: PASS
) else (
  echo AR-OPS-01 VALIDATION: FAIL - send the evidence ZIP; do not rerun individual tests.
)
echo.
pause
exit /b %RC%
