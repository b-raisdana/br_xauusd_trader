$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$resPath=Join-Path $Root 'results\RESULT_MATRIX_FINALIST_MT5.csv'
$dailyPath=Join-Path $Root 'results\DAILY_MATRIX_FINALIST_MT5.csv'
$checksPath=Join-Path $Root 'results\REGRESSION_CHECKS_FINALIST_MT5.csv'
$prevPath=Join-Path $Root 'reference\PREV_RESULT_MATRIX_FINALIST_MT5.csv'
foreach($p in @($resPath,$dailyPath,$checksPath,$prevPath)){if(-not(Test-Path $p)){throw "Required input missing: $p"}}

function Num($v){ if([string]::IsNullOrWhiteSpace("$v")){return 0.0}; return [double]::Parse("$v",[Globalization.CultureInfo]::InvariantCulture) }
function PF($rows){
  $gp=0.0;$gl=0.0
  foreach($r in $rows){
    $p=Num $r.net_pnl
    if($p -gt 0.01){$gp+=$p}elseif($p -lt -0.01){$gl+=-$p}
  }
  if($gl -le 0){ if($gp -gt 0){return 9999.0}; return 0.0}
  return $gp/$gl
}

$results=@(Import-Csv $resPath)
$daily=@(Import-Csv $dailyPath)
$checks=@(Import-Csv $checksPath)
$prev=@(Import-Csv $prevPath)
$matrix=@(Import-Csv (Join-Path $Root 'test_matrix.csv'))
$byId=@{}; foreach($x in $results){$byId[$x.run_id]=$x}
$checkById=@{}; foreach($x in $checks){$checkById[$x.run_id]=$x}

$zoneDays=@((Import-Csv (Join-Path $Root 'data\ranges.csv')) | Where-Object {("$($_.enabled)").Trim().ToLowerInvariant() -notin @('false','0','no','n')} | ForEach-Object {$_.date} | Sort-Object -Unique)
$train=@($zoneDays|Select-Object -First 15)
$forward=@($zoneDays|Select-Object -Skip 15)

$split=@()
foreach($r in $results){
  $summary=Join-Path $Root ("results\"+$r.run_id+"\"+$r.run_id+"_summary.csv")
  $sr=@(Import-Csv $summary)
  foreach($scope in @('TRAIN','FORWARD','ALL')){
    $ds=if($scope -eq 'TRAIN'){$train}elseif($scope -eq 'FORWARD'){$forward}else{$zoneDays}
    $closed=@($sr|Where-Object{
      $_.category -eq 'PRIMARY_TRADE' -and $_.event -eq 'POSITION_CLOSED' -and $_.counted_in_pnl -eq 'true' -and $_.server_time.Substring(0,10) -in $ds
    })
    $pnl=0.0;foreach($x in $closed){$pnl+=Num $x.net_pnl}
    $dayRows=@($daily|Where-Object{$_.run_id -eq $r.run_id -and $_.date -in $ds})
    $split += [pscustomobject]@{
      run_id=$r.run_id;scope=$scope;trades=$closed.Count;pnl=[math]::Round($pnl,2);pf=[math]::Round((PF $closed),3);
      positive_days=@($dayRows|Where-Object{(Num $_.net_pnl)-gt 0.01}).Count;
      negative_days=@($dayRows|Where-Object{(Num $_.net_pnl)-lt -0.01}).Count
    }
  }
}
$split | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $Root 'results\ACCEPTANCE_TRAIN_FORWARD.csv')

# Verify acceptance really ran with QA bypass OFF.
$qaFalseAll=$true
foreach($m in $matrix){
  $set=Join-Path $Root ("results\"+$m.run_id+"\"+$m.run_id+".set")
  $txt=Get-Content $set -Raw
  if($txt -notmatch 'InpQADiscoveryMode=false'){ $qaFalseAll=$false }
}

# At $300, b-23 is inactive by rule, so QA=false must reproduce the prior validated results.
$prevF1=$prev|Where-Object{$_.run_id -eq 'MT5_F1_MVP300_MAX5'}|Select-Object -First 1
$prevF2=$prev|Where-Object{$_.run_id -eq 'MT5_F2_MVP300_MAX5'}|Select-Object -First 1
$newF1=$byId['ACC_F1_MVP300_MAX5_B23']
$newF2=$byId['ACC_F2_MVP300_MAX5_B23']
$eq300F1=([math]::Abs((Num $newF1.net_pnl)-(Num $prevF1.net_pnl)) -le 0.05 -and [int]$newF1.trades -eq [int]$prevF1.trades -and [math]::Abs((Num $newF1.profit_factor)-(Num $prevF1.profit_factor)) -le 0.005)
$eq300F2=([math]::Abs((Num $newF2.net_pnl)-(Num $prevF2.net_pnl)) -le 0.05 -and [int]$newF2.trades -eq [int]$prevF2.trades -and [math]::Abs((Num $newF2.profit_factor)-(Num $prevF2.profit_factor)) -le 0.005)

$decision=@()
foreach($id in @('ACC_F1_MVP200_MAX3_B23','ACC_F2_MVP200_MAX3_B23','ACC_F1_MVP300_MAX5_B23','ACC_F2_MVP300_MAX5_B23')){
  $r=$byId[$id];$c=$checkById[$id]
  $tr=$split|Where-Object{$_.run_id -eq $id -and $_.scope -eq 'TRAIN'}|Select-Object -First 1
  $fw=$split|Where-Object{$_.run_id -eq $id -and $_.scope -eq 'FORWARD'}|Select-Object -First 1
  $cap=[int](($matrix|Where-Object{$_.run_id -eq $id}).max_live_positions)
  $technical=($r.regression_status -eq 'PASS' -and [int]$r.missing_zone_days -eq 0 -and [int]$r.margin_blocked -eq 0 -and [int]$c.unclosed_positions -eq 0 -and [int]$r.max_concurrent_positions -le $cap)
  $robust=($technical -and $tr.pnl -gt 0 -and $fw.pnl -gt 0 -and $tr.pf -gt 1.0 -and $fw.pf -gt 1.0)
  $decision += [pscustomobject]@{
    run_id=$id;deposit=$r.deposit;trades=$r.trades;pnl=$r.net_pnl;pf=$r.profit_factor;
    daily_loss_stop=$r.daily_loss_stop;max_concurrent=$r.max_concurrent_positions;margin_blocked=$r.margin_blocked;
    train_pnl=$tr.pnl;train_pf=$tr.pf;forward_pnl=$fw.pnl;forward_pf=$fw.pf;
    technical_status=if($technical){'PASS'}else{'FAIL'};robust_status=if($robust){'PASS'}else{'FAIL'}
  }
}
$decision|Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $Root 'results\MVP_ACCEPTANCE_DECISION.csv')

$allTech=@($decision|Where-Object{$_.technical_status -ne 'PASS'}).Count -eq 0
$f1_200=($decision|Where-Object{$_.run_id -eq 'ACC_F1_MVP200_MAX3_B23'}).robust_status
$f2_200=($decision|Where-Object{$_.run_id -eq 'ACC_F2_MVP200_MAX3_B23'}).robust_status
$f1_300=($decision|Where-Object{$_.run_id -eq 'ACC_F1_MVP300_MAX5_B23'}).robust_status
$f2_300=($decision|Where-Object{$_.run_id -eq 'ACC_F2_MVP300_MAX5_B23'}).robust_status
$gate=($qaFalseAll -and $allTech -and $eq300F1 -and $eq300F2)

$lines = @()
$lines += ("MVP_ACCEPTANCE_B23_GATE=" + $(if($gate){'PASS'}else{'FAIL'}))
$lines += ("QA_DISCOVERY_FALSE_ALL=" + $(if($qaFalseAll){'PASS'}else{'FAIL'}))
$lines += ("ALL_TECHNICAL_QA=" + $(if($allTech){'PASS'}else{'FAIL'}))
$lines += ("F1_300_EQUIVALENCE=" + $(if($eq300F1){'PASS'}else{'FAIL'}))
$lines += ("F2_300_EQUIVALENCE=" + $(if($eq300F2){'PASS'}else{'FAIL'}))
$lines += ("F1_200_ROBUST=" + $f1_200)
$lines += ("F2_200_ROBUST=" + $f2_200)
$lines += ("F1_300_ROBUST=" + $f1_300)
$lines += ("F2_300_ROBUST=" + $f2_300)
$lines += "NOTE=Final b-23 acceptance with QA bypass OFF. LIVE_SELECTIVE remains blocked by deferred AR-RISK-01 portfolio-risk validation."
$gatePath=Join-Path $Root 'MVP_ACCEPTANCE_B23_GATE.txt'
$lines | Set-Content -Encoding UTF8 $gatePath
Get-Content $gatePath
exit 0
