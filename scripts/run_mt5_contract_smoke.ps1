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
$pass = @($newLogLines | Select-String -SimpleMatch "CORE_VECTOR_SMOKE_PASS vectors=19 mode=inert")
if ($pass.Count -eq 0) {
    throw "Runtime success marker not found after terminal exit code $($process.ExitCode)."
}
$executionPass = @($newLogLines | Select-String -SimpleMatch `
        "EXECUTION_PROJECTOR_SMOKE_PASS lifecycle/protection/correlation/persistence/orchestration mode=inert")
if ($executionPass.Count -eq 0) {
    throw "Execution projector success marker not found after terminal exit code $($process.ExitCode)."
}
$callbackPass = @($newLogLines | Select-String -SimpleMatch `
        "NATIVE_CALLBACK_SMOKE_PASS opt-in/correlation/persist-before-state mode=inert")
if ($callbackPass.Count -eq 0) {
    throw "Guarded Native callback success marker not found after terminal exit code $($process.ExitCode)."
}
$statePass = @($newLogLines | Select-String -SimpleMatch `
        "STATE_ORDER_SMOKE_PASS tick/trend/bar-close mode=inert")
if ($statePass.Count -eq 0) {
    throw "State-ordering success marker not found after terminal exit code $($process.ExitCode)."
}
$coordinatorPass = @($newLogLines | Select-String -SimpleMatch `
        "COORDINATOR_SMOKE_PASS day/bar/tick/trend/engagement/signal/close mode=inert")
if ($coordinatorPass.Count -eq 0) {
    throw "Coordinator success marker not found after terminal exit code $($process.ExitCode)."
}
$safetyPass = @($newLogLines | Select-String -SimpleMatch `
        "SAFETY_REQUEST_SMOKE_PASS daily/gross/concurrency/margin/operations mode=inert")
if ($safetyPass.Count -eq 0) {
    throw "Safety/request success marker not found after terminal exit code $($process.ExitCode)."
}
$preparedPass = @($newLogLines | Select-String -SimpleMatch `
        "PREPARED_REQUEST_SMOKE_PASS space/risk/safety/audit/attempt mode=inert")
if ($preparedPass.Count -eq 0) {
    throw "Prepared-request success marker not found after terminal exit code $($process.ExitCode)."
}
$auditPass = @($newLogLines | Select-String -SimpleMatch `
        "AUDIT_REQUEST_SMOKE_PASS durable-before-state mode=inert")
if ($auditPass.Count -eq 0) {
    throw "Audit/request success marker not found after terminal exit code $($process.ExitCode)."
}
$nativePass = @($newLogLines | Select-String -SimpleMatch `
        "NATIVE_ADAPTER_SMOKE_PASS symbol/session/risk/margin/deal-map mode=read-only")
if ($nativePass.Count -eq 0) {
    throw "Native adapter success marker not found after terminal exit code $($process.ExitCode)."
}
$visualPass = @($newLogLines | Select-String -SimpleMatch `
        "VISUAL_PAYLOAD_SMOKE_PASS labels/tooltip mode=render-only")
if ($visualPass.Count -eq 0) {
    throw "Visual payload success marker not found after terminal exit code $($process.ExitCode)."
}
$timeProbe = @($newLogLines | Select-String -SimpleMatch "TIME_BASIS_PROBE index=")
if ($timeProbe.Count -lt 5) {
    throw "Five time-basis probe markers not found after terminal exit code $($process.ExitCode)."
}
$eventLoopReady = @($newLogLines | Select-String -SimpleMatch "CURRENT_EVENT_LOOP_READY zones=")
if ($eventLoopReady.Count -eq 0) {
    throw "Current event-loop runtime marker not found after terminal exit code $($process.ExitCode)."
}
$eventLoopDone = @($newLogLines | Select-String -Pattern `
        "CURRENT_EVENT_LOOP_DONE breakout=\d+ reversal=\d+ pullback=\d+ attempts=0 accepted=0 rejected=0 cancellations=0 session_closes=0 session_flattened=0 failed=0 mode=inert")
if ($eventLoopDone.Count -eq 0) {
    throw "Successful current event-loop completion marker not found after terminal exit code $($process.ExitCode)."
}

"MT5 runtime smoke PASS (19 vectors; execution/native/visual adapters; time probe; inert mode)."
