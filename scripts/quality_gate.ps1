$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Missing .venv. Run scripts/bootstrap_python.ps1 first."
}

& $python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m mypy scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& git diff --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Quality gate PASS"
