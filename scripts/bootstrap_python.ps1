$ErrorActionPreference = "Stop"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available on PATH."
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$python = Join-Path (Resolve-Path ".venv") "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-dev.txt
if (Test-Path "requirements.txt") {
    & $python -m pip install -r requirements.txt
}

Write-Host "Python environment ready: $python"
