# R0 self-contained settings bootstrap v1
# Engineering-only bootstrap. It does not change EA strategy rules.

function Resolve-MT5Terminal {
  if($env:XAUUSD_TERMINAL_EXE -and (Test-Path $env:XAUUSD_TERMINAL_EXE)){ return $env:XAUUSD_TERMINAL_EXE }
  $candidates=@()
  foreach($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)){
    if([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path $root)){ continue }
    $candidates += @(Get-ChildItem -Path $root -Filter terminal64.exe -File -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
  }
  $candidates=@($candidates | Sort-Object -Unique)
  if($candidates.Count -eq 1){ return $candidates[0] }
  if($candidates.Count -eq 0){ throw 'terminal64.exe not found. Set XAUUSD_TERMINAL_EXE or pass it through run_project.ps1.' }
  throw ('Multiple terminal64.exe installations found. Set XAUUSD_TERMINAL_EXE explicitly: ' + ($candidates -join '; '))
}

function Resolve-MT5DataDir([string]$terminalExe){
  if($env:XAUUSD_DATA_DIR -and (Test-Path $env:XAUUSD_DATA_DIR)){ return $env:XAUUSD_DATA_DIR }
  $root=Join-Path $env:APPDATA 'MetaQuotes\Terminal'
  if(-not (Test-Path $root)){ throw 'MetaQuotes Terminal data root not found. Set XAUUSD_DATA_DIR explicitly.' }
  $dirs=@(Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName 'MQL5') })
  $terminalFolder=Split-Path $terminalExe -Parent
  $matched=@()
  foreach($d in $dirs){
    $origin=Join-Path $d.FullName 'origin.txt'
    if(Test-Path $origin){
      $txt=(Get-Content $origin -Raw -ErrorAction SilentlyContinue).Trim()
      if($txt -and ($txt.TrimEnd('\\') -ieq $terminalFolder.TrimEnd('\\'))){ $matched += $d.FullName }
    }
  }
  if($matched.Count -eq 1){ return $matched[0] }
  if($dirs.Count -eq 1){ return $dirs[0].FullName }
  throw ('Unable to uniquely resolve MT5 data directory. Set XAUUSD_DATA_DIR explicitly. Candidates: ' + (($dirs | Select-Object -ExpandProperty FullName) -join '; '))
}

$TerminalExe = Resolve-MT5Terminal
$MetaEditorExe = if($env:XAUUSD_METAEDITOR_EXE){$env:XAUUSD_METAEDITOR_EXE}else{Join-Path (Split-Path $TerminalExe -Parent) 'metaeditor64.exe'}
$DataDir = Resolve-MT5DataDir $TerminalExe

$EAFileName = 'XAUUSD_EA_MVP_F2_AR_OPS_01_v0_1.mq5'
$RangesFileName = 'ranges.csv'
$ExpertFolder = 'XAUUSD_AR_OPS_01'
$Symbol = 'XAUUSD'
$Period = 'M15'
$Model = 4
$ExecutionMode = 0
$Currency = 'USD'
$Leverage = '1:100'
$FromDate = '2026.07.29'
$ToDate = '2026.08.29'
