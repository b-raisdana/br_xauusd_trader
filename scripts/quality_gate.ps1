$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing .venv. Run scripts/bootstrap_python.ps1 first."
}

& $python -m ruff check .
& $python -m ruff format --check .
& $python -m pytest
Write-Host "Quality gate PASS"
