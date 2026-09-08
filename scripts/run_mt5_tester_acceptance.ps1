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
$isRestart = Select-String -LiteralPath $config -SimpleMatch "InpSimulateSameDayRestart=true"
$donePattern = if ($isRestart) {
    "CURRENT_EVENT_LOOP_DONE breakout=\d+ reversal=\d+ pullback=\d+ attempts=0 accepted=0 rejected=0 cancellations=0 session_closes=0 session_flattened=1 failed=0 mode=tester"
} else {
    "CURRENT_EVENT_LOOP_DONE breakout=\d+ reversal=\d+ pullback=\d+ attempts=([1-9]\d*) accepted=(\d+) rejected=(\d+) cancellations=(\d+) session_closes=(\d+) session_flattened=1 failed=0 mode=tester"
}
$done = @($newLogLines | Select-String -Pattern $donePattern)
if ($done.Count -eq 0) {
    throw "Successful tester lifecycle completion marker not found (exit $($process.ExitCode))."
}
$marker = $done[-1].Matches[0].Value
$symbolSpec = @($newLogLines | Select-String -Pattern `
        "TESTER_SYMBOL_SPEC digits=\d+ point=[0-9.]+ contract=[0-9.]+ tick_size=[0-9.]+ tick_value=[0-9.]+ stops=\d+ freeze=\d+ volume_min=[0-9.]+ volume_step=[0-9.]+ session_from=.+ session_to=.+ mode=tester")
if ($symbolSpec.Count -eq 0) {
    throw "Tester symbol specification marker not found."
}
if ($isRestart -and @($newLogLines | Select-String -Pattern `
            "TESTER_RESTART_FLAT cancellations=\d+ closes=\d+ broker_day=\d{4}-\d{2}-\d{2} mode=tester").Count -eq 0) {
    throw "Same-day restart flatten marker not found."
}
$riskDone = @($newLogLines | Select-String -Pattern `
        "TESTER_RISK_DONE net=(-?\d+\.\d+) gross_loss=(\d+\.\d+) max_positions=(\d+) daily_blocks=(\d+) gross_blocks=(\d+) concurrency_blocks=(\d+) margin_blocks=(\d+) protection_blocks=(\d+) space_blocks=(\d+) initial_blocks=(\d+) invalid_price_rejects=(\d+) other_broker_rejects=(\d+) protection_modifies=(\d+) modify_rejects=(\d+) sl_loosen=(\d+) mode=tester")
if ($riskDone.Count -eq 0) {
    throw "Tester risk completion marker not found."
}
$riskMatch = $riskDone[-1].Matches[0]
$tpDone = @($newLogLines | Select-String -Pattern `
        "TESTER_TP_DONE extensions=(\d+) restores=(\d+) market_closes=(\d+) modify_rejects=(\d+) close_rejects=(\d+) mode=tester")
if ($tpDone.Count -eq 0) {
    throw "Tester Pullback TP completion marker not found."
}
$tpMatch = $tpDone[-1].Matches[0]
$breakoutDone = @($newLogLines | Select-String -Pattern `
        "TESTER_BREAKOUT_DONE conflict_closes=\d+ mode=tester")
if ($breakoutDone.Count -eq 0) {
    throw "Tester Breakout completion marker not found."
}
$attribution = @($newLogLines | Select-String -Pattern `
        "TESTER_ATTRIBUTION bo_normal=\d+/\d+/\d+ bo_high=\d+/\d+/\d+ rev_normal=\d+/\d+/\d+ rev_high=\d+/\d+/\d+ pb_normal=\d+/\d+/\d+ pb_high=\d+/\d+/\d+ mode=tester")
if ($attribution.Count -eq 0) {
    throw "Tester attribution marker not found."
}
$maxPositions = [int]$riskMatch.Groups[3].Value
$marginBlocks = [int]$riskMatch.Groups[7].Value
$otherBrokerRejects = [int]$riskMatch.Groups[12].Value
$slLoosen = [int]$riskMatch.Groups[15].Value
$tpModifyRejects = [int]$tpMatch.Groups[4].Value
$tpCloseRejects = [int]$tpMatch.Groups[5].Value
$is300 = Select-String -LiteralPath $config -SimpleMatch "InpStrategyCapital=300.0"
$allowedPositions = if ($is300) { 5 } else { 3 }
if ($maxPositions -gt $allowedPositions -or $marginBlocks -ne 0 -or `
        $otherBrokerRejects -ne 0 -or $slLoosen -ne 0 -or `
        $tpModifyRejects -ne 0 -or $tpCloseRejects -ne 0) {
    throw "Tester risk acceptance failed: max_positions=$maxPositions margin_blocks=$marginBlocks other_rejects=$otherBrokerRejects sl_loosen=$slLoosen tp_modify_rejects=$tpModifyRejects tp_close_rejects=$tpCloseRejects."
}
if ($isRestart -and $maxPositions -ne 0) {
    throw "Same-day restart acceptance failed: max_positions=$maxPositions."
}
"MT5 Strategy Tester acceptance PASS: $marker"
"MT5 Strategy Tester symbol specification PASS: $($symbolSpec[-1].Matches[0].Value)"
"MT5 Strategy Tester risk PASS: $($riskMatch.Value)"
"MT5 Strategy Tester Pullback TP PASS: $($tpMatch.Value)"
"MT5 Strategy Tester Breakout PASS: $($breakoutDone[-1].Matches[0].Value)"
"MT5 Strategy Tester attribution PASS: $($attribution[-1].Matches[0].Value)"
