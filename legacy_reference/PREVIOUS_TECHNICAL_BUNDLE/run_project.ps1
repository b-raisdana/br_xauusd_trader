$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$required=@('settings.ps1','candidate_settings.ps1','run_tests.ps1','analyze_ar_ops_01.ps1','test_matrix.csv','ea\XAUUSD_EA_MVP_F2_AR_OPS_01_v0_1.mq5','data\ranges.csv','reference\AR_RISK_01_RESULT_MATRIX.csv')
$miss=@();foreach($r in $required){if(-not(Test-Path(Join-Path $Root $r))){$miss+=$r}}
if($miss.Count -gt 0){Write-Host ("PRE-FLIGHT FAIL: "+($miss -join '; ')) -ForegroundColor Red;exit 2}
$rows=@(Import-Csv(Join-Path $Root 'test_matrix.csv')|Where-Object{$_.enabled -eq '1' -and $_.phase -eq 'AR_OPS_01'})
if($rows.Count -ne 6){Write-Host "PRE-FLIGHT FAIL: expected 6 FAST scenarios, found $($rows.Count)." -ForegroundColor Red;exit 2}
if(@($rows|Where-Object{$_.mvp_profile -ne '4' -or $_.risk_mode -ne '2' -or $_.risk_pct -ne '15' -or $_.qa_discovery -ne 'false'}).Count -gt 0){
 Write-Host "PRE-FLIGHT FAIL: all scenarios must be frozen F2 + GROSS15 + QA=false." -ForegroundColor Red;exit 2
}
Write-Host "PRE-FLIGHT PASS: 6 FAST scenarios = 2 full controls + 4 targeted restart windows." -ForegroundColor Green
. (Join-Path $Root 'settings.ps1')
$stamp=(Get-Date).ToString('yyyyMMdd_HHmmss');$ev=Join-Path(Join-Path $Root 'evidence')("AR_OPS_01_FAST_VALIDATION_"+$stamp);New-Item -ItemType Directory -Force -Path $ev|Out-Null
$hostExe=(Get-Process -Id $PID).Path;$args=@('-NoProfile');if($hostExe -match '(?i)powershell\.exe$'){$args+=@('-ExecutionPolicy','Bypass')};$args+=@('-File',(Join-Path $Root 'run_tests.ps1'),'-Phase','AR_OPS_01','-Resume')
Write-Host "Starting AR-OPS-01 FAST Real-Tick batch..." -ForegroundColor Cyan
& $hostExe @args;$te=$LASTEXITCODE;if($null -eq $te){$te=0}
$ae=99;if($te -eq 0){& $hostExe @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $Root 'analyze_ar_ops_01.ps1'));$ae=$LASTEXITCODE;if($null -eq $ae){$ae=0}}
foreach($n in @('run_tests.ps1','run_project.ps1','analyze_ar_ops_01.ps1','settings.ps1','candidate_settings.ps1','test_matrix.csv','README_FA.md','STATIC_QA.md','SHA256_KIT.txt')){$p=Join-Path $Root $n;if(Test-Path $p){Copy-Item $p $ev -Force}}
foreach($d in @('ea','data','reference','generated','results')){$p=Join-Path $Root $d;if(Test-Path $p){Copy-Item $p (Join-Path $ev $d) -Recurse -Force}}
$g=Join-Path $Root 'AR_OPS_01_VALIDATION_GATE.txt';if(Test-Path $g){Copy-Item $g $ev -Force}else{@("AR_OPS_01_VALIDATION_GATE=FAIL","TEST_EXIT=$te","ANALYSIS_EXIT=$ae")|Set-Content -Encoding UTF8 (Join-Path $ev 'AR_OPS_01_VALIDATION_GATE.txt')}
@("TEST_EXIT=$te","ANALYSIS_EXIT=$ae")|Add-Content -Encoding UTF8 (Join-Path $ev 'AR_OPS_01_VALIDATION_GATE.txt')
$cl=Join-Path $DataDir 'MQL5\Experts\XAUUSD_AR_OPS_01\XAUUSD_EA_MVP_F2_AR_OPS_01_v0_1.log';if(Test-Path $cl){Copy-Item $cl (Join-Path $ev 'METAEDITOR_COMPILE.log') -Force}
$mf=Join-Path $ev 'SHA256_EVIDENCE.txt';Get-ChildItem $ev -Recurse -File|Where-Object{$_.FullName -ne $mf}|Sort-Object FullName|ForEach-Object{"$((Get-FileHash $_.FullName -Algorithm SHA256).Hash)  $($_.FullName.Substring($ev.Length+1))"}|Set-Content -Encoding ASCII $mf
$zip=$ev+'.zip';if(Test-Path $zip){Remove-Item $zip -Force};Compress-Archive -Path(Join-Path $ev '*') -DestinationPath $zip -Force
Write-Host '';Get-Content(Join-Path $ev 'AR_OPS_01_VALIDATION_GATE.txt');Write-Host "Evidence bundle: $zip" -ForegroundColor Cyan
if($te -ne 0 -or $ae -ne 0){exit 2};$gt=Get-Content(Join-Path $ev 'AR_OPS_01_VALIDATION_GATE.txt') -Raw;if($gt -notmatch '(?m)^AR_OPS_01_VALIDATION_GATE=PASS\s*$'){exit 2};exit 0
