# Pre-commit wrapper for Windows - uses active venv or repo .venv
$repoRoot = git rev-parse --show-toplevel

if ($env:VIRTUAL_ENV) {
    $python = "$env:VIRTUAL_ENV\Scripts\python.exe"
} elseif (Test-Path "$repoRoot\.venv\Scripts\python.exe") {
    $python = "$repoRoot\.venv\Scripts\python.exe"
} else {
    $python = "python"
}

Write-Host "Using Python: $python"
& $python -m pre_commit run @args
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    exit $exitCode
}

exit 0