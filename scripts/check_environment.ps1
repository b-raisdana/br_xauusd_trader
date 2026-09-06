$ErrorActionPreference = "Continue"

Write-Host "=== Environment Check ==="
$tools = @(
    @{Name="Git"; Command="git"; Args=@("--version")},
    @{Name="GitHub CLI"; Command="gh"; Args=@("--version")},
    @{Name="uv"; Command="uv"; Args=@("--version")}
)

foreach ($t in $tools) {
    try {
        $result = & $t.Command $t.Args 2>&1 | Select-Object -First 1
        Write-Host ("[OK] {0}: {1}" -f $t.Name, $result)
    } catch {
        Write-Host ("[MISSING] {0}" -f $t.Name)
    }
}

$projectPython = Join-Path (Resolve-Path ".") ".venv\Scripts\python.exe"
if (Test-Path $projectPython) {
    Write-Host ("[OK] Project Python: {0}" -f (& $projectPython --version 2>&1))
} else {
    Write-Host "[MISSING] Project Python: run scripts/bootstrap_python.ps1"
}

$mt5Root = "C:\Program Files\MetaTrader 5"
foreach ($name in @("terminal64.exe", "metaeditor64.exe")) {
    $path = Join-Path $mt5Root $name
    if (Test-Path $path) {
        Write-Host ("[OK] MT5 component: {0}" -f $path)
    } else {
        Write-Host ("[MISSING] MT5 component: {0}" -f $path)
    }
}

try {
    $inside = git rev-parse --is-inside-work-tree 2>$null
    if ($inside -eq "true") {
        Write-Host "[OK] Git repository detected"
        git status --short
        git remote -v
    } else {
        Write-Host "[INFO] Git repository not initialized"
    }
} catch {
    Write-Host "[INFO] Git repository not initialized"
}
