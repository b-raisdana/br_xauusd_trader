# Pre-commit wrapper for Windows - runs using active Python (venv when activated)
Write-Host "Using Python: $(python -c \"import sys; print(sys.executable)\")"
python -m pre_commit run @args
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    exit $exitCode
}

exit 0