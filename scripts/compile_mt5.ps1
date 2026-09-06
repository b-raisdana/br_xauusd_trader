param(
    [string]$MetaEditorPath = (Join-Path $env:ProgramFiles "MetaTrader 5\MetaEditor64.exe")
)

$ErrorActionPreference = "Stop"

$source = (Resolve-Path ".\src\mt5\XAUUSD_MVP.mq5").Path
$log = Join-Path (Resolve-Path ".\artifacts").Path "mt5_compile.log"

if (-not (Test-Path -LiteralPath $MetaEditorPath)) {
    throw "MetaEditor not found: $MetaEditorPath"
}
if (Test-Path -LiteralPath $log) {
    Remove-Item -LiteralPath $log
}

$process = Start-Process -FilePath $MetaEditorPath `
    -ArgumentList "/compile:$source", "/log:$log" `
    -WindowStyle Hidden -Wait -PassThru

$result = Select-String -LiteralPath $log -Pattern '^Result: (\d+) errors, (\d+) warnings'
if ($null -eq $result) {
    throw "MetaEditor result missing (process exit $($process.ExitCode)): $log"
}
if ($result.Matches[0].Groups[1].Value -ne "0" -or $result.Matches[0].Groups[2].Value -ne "0") {
    Get-Content -LiteralPath $log
    throw "MT5 compile gate failed"
}

Get-Content -LiteralPath $log
