$ErrorActionPreference = "Continue"

Write-Host "=== Environment Check ==="
$tools = @(
    @{Name="Git"; Command="git"; Args="--version"},
    @{Name="GitHub CLI"; Command="gh"; Args="--version"},
    @{Name="Python"; Command="python"; Args="--version"}
)

foreach ($t in $tools) {
    try {
        $result = & $t.Command $t.Args 2>&1 | Select-Object -First 1
        Write-Host ("[OK] {0}: {1}" -f $t.Name, $result)
    } catch {
        Write-Host ("[MISSING] {0}" -f $t.Name)
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
