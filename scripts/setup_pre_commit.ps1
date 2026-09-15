$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$toolRoot = Join-Path $repoRoot 'br_pre_commit'

function Invoke-GitChecked {
    & git @args
    if ($LASTEXITCODE -ne 0) { throw "Git failed: $args" }
}

Invoke-GitChecked -C $repoRoot submodule update --init br_pre_commit
# NTFS executable bits differ between Git for Windows and WSL.
Invoke-GitChecked -C $repoRoot config core.fileMode false
Invoke-GitChecked -C $repoRoot config core.autocrlf true
Invoke-GitChecked -C $toolRoot config core.fileMode false
Invoke-GitChecked -C $toolRoot config core.autocrlf false

# Keep the upstream commit intact while making its shell launchers usable in WSL.
$utf8 = New-Object System.Text.UTF8Encoding($false)
foreach ($name in @('install.sh', 'pre-commit', 'ratchet', 'run')) {
    $path = Join-Path $toolRoot $name
    [IO.File]::WriteAllText($path, [IO.File]::ReadAllText($path).Replace("`r`n", "`n"), $utf8)
}

$gitRoot = Split-Path (Split-Path (Get-Command git).Source -Parent) -Parent
$bash = Join-Path $gitRoot 'bin/bash.exe'
if (-not (Test-Path $bash)) { throw "Git Bash not found: $bash" }
& $bash (Join-Path $toolRoot 'install.sh') $repoRoot
if ($LASTEXITCODE -ne 0) { throw 'Shared pre-commit installation failed.' }
Write-Host 'Hook installed. Requires Ubuntu-24.04 WSL and conda environment tf with pre-commit, Ruff and project test dependencies.'
