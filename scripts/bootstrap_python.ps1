$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv venv --python 3.11 .venv
        if ($LASTEXITCODE -ne 0) { throw "uv failed to create .venv." }
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "py failed to create .venv." }
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "python failed to create .venv." }
    } else {
        throw "Python 3.11 or uv is required. Neither is available on PATH."
    }
}

$python = Join-Path (Resolve-Path ".venv") "Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment creation failed: $python is missing."
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv pip install --python $python -r requirements-dev.txt -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "uv dependency installation failed." }
} else {
    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
    & $python -m pip install -r requirements-dev.txt -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip dependency installation failed." }
}

Write-Host "Python environment ready: $python"
