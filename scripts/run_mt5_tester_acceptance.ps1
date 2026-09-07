param(
    [string]$ConfigPath = ".\config\mt5\tester_200.ini",
    [string]$TerminalPath = (Join-Path $env:ProgramFiles "MetaTrader 5\terminal64.exe"),
    [string]$DataRoot = ""
)

$ErrorActionPreference = "Stop"
$source = (Resolve-Path ".\src\mt5\XAUUSD_MVP.ex5").Path
$config = (Resolve-Path -LiteralPath $ConfigPath).Path
if (-not (Test-Path -LiteralPath $TerminalPath)) {
    throw "MetaTrader terminal not found: $TerminalPath"
}
if (Get-Process -Name terminal64 -ErrorAction SilentlyContinue) {
    throw "Close the running MetaTrader terminal before isolated tester acceptance."
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
        throw "Expected one matching MT5 data root; pass -DataRoot explicitly."
    }
    $DataRoot = $matches[0].FullName
}
$expertsRoot = [IO.Path]::GetFullPath((Join-Path $DataRoot "MQL5\Experts"))
$targetDir = [IO.Path]::GetFullPath((Join-Path $expertsRoot "XAUUSD_Current"))
if (-not $targetDir.StartsWith($expertsRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Resolved target escaped the MT5 Experts directory."
}
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
$target = Join-Path $targetDir "XAUUSD_MVP.ex5"
Copy-Item -LiteralPath $source -Destination $target -Force
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {
    throw "Compiled EA copy failed hash verification."
}

$started = Get-Date
$process = Start-Process -FilePath $TerminalPath `
    -ArgumentList "/config:`"$config`"" -WindowStyle Hidden -Wait -PassThru
$newLogs = @(Get-ChildItem -LiteralPath (Join-Path $DataRoot "Tester") -Filter "*.log" `
        -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $started })
$done = @($newLogs | Select-String -Pattern `
        "CURRENT_EVENT_LOOP_DONE breakout=\d+ reversal=\d+ pullback=\d+ attempts=([1-9]\d*) accepted=(\d+) rejected=(\d+) failed=0 mode=tester")
if ($done.Count -eq 0) {
    throw "Successful tester lifecycle completion marker not found (exit $($process.ExitCode))."
}
$marker = $done[-1].Matches[0].Value
"MT5 Strategy Tester acceptance PASS: $marker"
