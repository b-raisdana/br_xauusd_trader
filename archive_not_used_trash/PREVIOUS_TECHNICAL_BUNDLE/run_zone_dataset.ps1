$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp=(Get-Date).ToString('yyyyMMdd_HHmmss')
$evidenceRoot=Join-Path $root 'evidence'
$out=Join-Path $evidenceRoot ("ZONE_EVENT_{0}" -f $stamp)
New-Item -ItemType Directory -Force -Path $out | Out-Null
$log=Join-Path $out 'ZONE_EVENT_CONSOLE.log'
$rc=1
$transcript=$false
try {
  Start-Transcript -Path $log -Force | Out-Null; $transcript=$true
  $py=Join-Path $root '.runtime\python312_embed\python.exe'
  if(-not (Test-Path -LiteralPath $py)){
    throw "Project-local Python not found at $py . Copy/extract this patch into the SAME XAUUSD_PY_RESEARCH_BOOTSTRAP_v4 folder that already passed the data gate."
  }
  $cacheRoot=Join-Path $env:LOCALAPPDATA 'XAUUSD_PY_RESEARCH_CACHE'
  if(-not (Test-Path -LiteralPath $cacheRoot)){throw "Research cache root not found: $cacheRoot"}
  $cache=Get-ChildItem -Path $cacheRoot -Directory -ErrorAction Stop |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'm15_bars_server.csv.gz') } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if(-not $cache){throw 'No completed XAUUSD Python research cache was found.'}
  Write-Host "Using cache: $($cache.FullName)" -ForegroundColor Cyan
  Write-Host 'Building TP/SL-independent Zone Reaction/Event Dataset...' -ForegroundColor Cyan
  & $py (Join-Path $root 'zone_event_dataset.py') `
      --cache-dir $cache.FullName `
      --ranges (Join-Path $root 'reference\ranges.csv') `
      --summary (Join-Path $root 'reference\R2_ALLFLAT_H4S15_100K_summary.csv') `
      --output-dir $out
  $rc=$LASTEXITCODE
  if($rc -ne 0){throw "Zone dataset builder failed with exit code=$rc"}
}
catch {
  Write-Host ("ERROR: " + $_.Exception.Message) -ForegroundColor Red
  ("ZONE_EVENT_DATASET_GATE=FAIL`r`nERROR="+$_.Exception.Message) | Set-Content -Path (Join-Path $out 'RUNNER_GATE.txt') -Encoding UTF8
  $rc=1
}
finally {
  if($transcript){try{Stop-Transcript | Out-Null}catch{}; $transcript=$false}
  Start-Sleep -Milliseconds 250
  New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
  $zip=Join-Path $evidenceRoot ("ZONE_EVENT_DATASET_{0}.zip" -f $stamp)
  try {
    Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip -Force
    Write-Host "Evidence bundle: $zip" -ForegroundColor Yellow
  } catch {
    Write-Host ("WARNING: ZIP packaging failed, but result files remain at: " + $out) -ForegroundColor Yellow
  }
}
exit $rc
