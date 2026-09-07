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

$testerRoot = Join-Path $DataRoot "Tester"
$beforeLineCounts = @{}
Get-ChildItem -LiteralPath $testerRoot -Filter "*.log" -Recurse -File `
    -ErrorAction SilentlyContinue | ForEach-Object {
        $beforeLineCounts[$_.FullName] = @(Get-Content -LiteralPath $_.FullName).Count
    }
$started = Get-Date
$process = Start-Process -FilePath $TerminalPath `
    -ArgumentList "/config:`"$config`"" -WindowStyle Hidden -Wait -PassThru
$newLogLines = @(Get-ChildItem -LiteralPath $testerRoot -Filter "*.log" -Recurse -File `
        -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $started } | ForEach-Object {
            $allLines = @(Get-Content -LiteralPath $_.FullName)
            $skip = if ($beforeLineCounts.ContainsKey($_.FullName) -and
                $beforeLineCounts[$_.FullName] -lt $allLines.Count) {
                $beforeLineCounts[$_.FullName]
            } else { 0 }
            $allLines | Select-Object -Skip $skip
        })
$done = @($newLogLines | Select-String -Pattern `
        "CURRENT_EVENT_LOOP_DONE breakout=\d+ reversal=\d+ pullback=\d+ attempts=([1-9]\d*) accepted=(\d+) rejected=(\d+) cancellations=(\d+) session_closes=(\d+) session_flattened=1 failed=0 mode=tester")
if ($done.Count -eq 0) {
    throw "Successful tester lifecycle completion marker not found (exit $($process.ExitCode))."
}
$marker = $done[-1].Matches[0].Value
$riskDone = @($newLogLines | Select-String -Pattern `
        "TESTER_RISK_DONE net=(-?\d+\.\d+) gross_loss=(\d+\.\d+) max_positions=(\d+) daily_blocks=(\d+) gross_blocks=(\d+) concurrency_blocks=(\d+) margin_blocks=(\d+) protection_blocks=(\d+) space_blocks=(\d+) initial_blocks=(\d+) invalid_price_rejects=(\d+) other_broker_rejects=(\d+) protection_modifies=(\d+) modify_rejects=(\d+) sl_loosen=(\d+) mode=tester")
if ($riskDone.Count -eq 0) {
    throw "Tester risk completion marker not found."
}
$riskMatch = $riskDone[-1].Matches[0]
$maxPositions = [int]$riskMatch.Groups[3].Value
$marginBlocks = [int]$riskMatch.Groups[7].Value
$otherBrokerRejects = [int]$riskMatch.Groups[12].Value
$slLoosen = [int]$riskMatch.Groups[15].Value
$is300 = Select-String -LiteralPath $config -SimpleMatch "InpStrategyCapital=300.0"
$allowedPositions = if ($is300) { 5 } else { 3 }
if ($maxPositions -gt $allowedPositions -or $marginBlocks -ne 0 -or `
        $otherBrokerRejects -ne 0 -or $slLoosen -ne 0) {
    throw "Tester risk acceptance failed: max_positions=$maxPositions margin_blocks=$marginBlocks other_rejects=$otherBrokerRejects sl_loosen=$slLoosen."
}
"MT5 Strategy Tester acceptance PASS: $marker"
"MT5 Strategy Tester risk PASS: $($riskMatch.Value)"
