@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_project.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo MVP B23 ACCEPTANCE: PASS
) else (
  echo MVP B23 ACCEPTANCE: FAIL - send the evidence ZIP. Do not rerun individual MT5 tests.
)
echo.
pause
exit /b %RC%
