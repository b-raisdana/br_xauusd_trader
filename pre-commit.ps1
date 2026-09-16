# Pre-commit wrapper for Windows - uses active venv or repo .venv
$repoRoot = git rev-parse --show-toplevel

if ($env:VIRTUAL_ENV) {
    $scriptsDir = Join-Path $env:VIRTUAL_ENV 'Scripts'
    $python = Join-Path $scriptsDir 'python.exe'
} elseif (Test-Path -LiteralPath (Join-Path $repoRoot '.venv\Scripts\python.exe')) {
    $scriptsDir = Join-Path $repoRoot '.venv\Scripts'
    $python = Join-Path $scriptsDir 'python.exe'
} else {
    $scriptsDir = $null
    $python = 'python'
}

if ($scriptsDir) {
    $env:PATH = "$scriptsDir;$env:PATH"
}

Write-Host "Using Python: $python"
& $python -m pre_commit run @args
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    exit $exitCode
}

exit 0
