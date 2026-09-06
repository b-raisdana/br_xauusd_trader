param(
    [string]$TerminalPath = (Join-Path $env:ProgramFiles "MetaTrader 5\terminal64.exe"),
    [string]$DataRoot = ""
)

$ErrorActionPreference = "Stop"

$source = (Resolve-Path ".\src\mt5\XAUUSD_MVP.ex5").Path
$config = (Resolve-Path ".\config\mt5\contract_smoke.ini").Path
if (-not (Test-Path -LiteralPath $TerminalPath)) {
    throw "MetaTrader terminal not found: $TerminalPath"
}
if (Get-Process -Name terminal64 -ErrorAction SilentlyContinue) {
    throw "Close the running MetaTrader terminal before the isolated contract smoke."
}

if ([string]::IsNullOrWhiteSpace($DataRoot)) {
    $terminalStore = Join-Path $env:APPDATA "MetaQuotes\Terminal"
    $installRoot = (Split-Path -Parent (Resolve-Path -LiteralPath $TerminalPath).Path).TrimEnd("\")
    $matches = @(Get-ChildItem -LiteralPath $terminalStore -Directory | Where-Object {
            $origin = Join-Path $_.FullName "origin.txt"
            (Test-Path -LiteralPath $origin) -and
            ((Get-Content -LiteralPath $origin -Raw).Trim().TrimEnd("\") -eq $installRoot)
        })
    if ($matches.Count -ne 1) {
        throw "Expected one MT5 data root for $installRoot; pass -DataRoot explicitly."
    }
    $DataRoot = $matches[0].FullName
}

$expertsRoot = [IO.Path]::GetFullPath((Join-Path $DataRoot "MQL5\Experts"))
$targetDir = [IO.Path]::GetFullPath((Join-Path $expertsRoot "XAUUSD_Current"))
if (-not $targetDir.StartsWith($expertsRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Resolved target escaped the MT5 Experts directory."
}
$target = Join-Path $targetDir "XAUUSD_MVP.ex5"
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $target -Force
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {
    throw "Compiled EA copy failed hash verification."
}

$started = Get-Date
$process = Start-Process -FilePath $TerminalPath `
    -ArgumentList "/config:`"$config`"" -WindowStyle Hidden -Wait -PassThru
$newLogs = @(Get-ChildItem -LiteralPath (Join-Path $DataRoot "Tester") -Filter "*.log" `
        -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $started })
$pass = @($newLogs | Select-String -SimpleMatch "CORE_VECTOR_SMOKE_PASS vectors=16 mode=inert")
if ($pass.Count -eq 0) {
    throw "Runtime success marker not found after terminal exit code $($process.ExitCode)."
}
$nativePass = @($newLogs | Select-String -SimpleMatch `
        "NATIVE_ADAPTER_SMOKE_PASS symbol/session/risk/margin mode=read-only")
if ($nativePass.Count -eq 0) {
    throw "Native adapter success marker not found after terminal exit code $($process.ExitCode)."
}
$visualPass = @($newLogs | Select-String -SimpleMatch `
        "VISUAL_PAYLOAD_SMOKE_PASS labels/tooltip mode=render-only")
if ($visualPass.Count -eq 0) {
    throw "Visual payload success marker not found after terminal exit code $($process.ExitCode)."
}
$timeProbe = @($newLogs | Select-String -SimpleMatch "TIME_BASIS_PROBE index=")
if ($timeProbe.Count -lt 5) {
    throw "Five time-basis probe markers not found after terminal exit code $($process.ExitCode)."
}

"MT5 runtime smoke PASS (16 vectors; native/visual adapters; time probe; inert mode)."
