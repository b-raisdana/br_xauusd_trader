@echo off
setlocal
cd /d "%~dp0"
echo XAUUSD Python/Polars research bootstrap v3
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_project.ps1"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo PY DATA / EQUIVALENCE GATE: PASS
) else (
  echo PY DATA / EQUIVALENCE GATE: FAIL - see evidence and PY_BOOTSTRAP_CONSOLE.log
)
echo.
echo This window will stay open. Press any key to close.
pause >nul
exit /b %RC%
