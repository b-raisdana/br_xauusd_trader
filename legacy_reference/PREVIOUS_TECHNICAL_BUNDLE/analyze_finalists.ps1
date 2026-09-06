$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$phase='FINALIST_MT5'
$resPath=Join-Path $Root "results\RESULT_MATRIX_$phase.csv"
$dailyPath=Join-Path $Root "results\DAILY_MATRIX_$phase.csv"
$checksPath=Join-Path $Root "results\REGRESSION_CHECKS_$phase.csv"
$refPath=Join-Path $Root 'reference\R2_ALLFLAT_H4S15_100K_summary.csv'
foreach($p in @($resPath,$dailyPath,$checksPath,$refPath)){if(-not(Test-Path $p)){throw "Required analysis input missing: $p"}}

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
function SumP($rows){$s=0.0;foreach($r in $rows){$s+=Num $r.net_pnl};return $s}

$results=@(Import-Csv $resPath)
$daily=@(Import-Csv $dailyPath)
$checks=@(Import-Csv $checksPath)
$matrix=@(Import-Csv (Join-Path $Root 'test_matrix.csv'))
$byId=@{};foreach($r in $results){$byId[$r.run_id]=$r}
$checkById=@{};foreach($r in $checks){$checkById[$r.run_id]=$r}
$matrixById=@{};foreach($r in $matrix){$matrixById[$r.run_id]=$r}

$ctrl=$byId['MT5_CTRL_ALLFLAT_H4S15_100K']
if($null -eq $ctrl){throw 'Control result missing'}

# Exact reference control fill/close signature audit.
$ref=@(Import-Csv $refPath)
$ctrlSummary=Join-Path $Root 'results\MT5_CTRL_ALLFLAT_H4S15_100K\MT5_CTRL_ALLFLAT_H4S15_100K_summary.csv'
if(-not(Test-Path $ctrlSummary)){throw "Control summary missing: $ctrlSummary"}
$cur=@(Import-Csv $ctrlSummary)
function TradeKeys($rows,[string]$event){
  $h=@{}
  foreach($r in $rows | Where-Object {$_.category -eq 'PRIMARY_TRADE' -and $_.event -eq $event -and $_.counted_in_pnl -eq 'true'}){
    $k="$($r.server_time)|$($r.zone_id)|$($r.signal)|$($r.parent_breakout_id)|$($r.reversal_ordinal)"
    $h[$k]=$true
  }
  return $h
}
$rk=TradeKeys $ref 'ORDER_FILLED'
$ck=TradeKeys $cur 'ORDER_FILLED'
$match=0;foreach($k in $rk.Keys){if($ck.ContainsKey($k)){$match++}}
$fillRatio=if($rk.Count -gt 0){$match/[double]$rk.Count}else{0.0}

$ctrlPass=([math]::Abs((Num $ctrl.net_pnl)-72.13) -le 0.05 -and [int]$ctrl.trades -eq 495 -and [math]::Abs((Num $ctrl.profit_factor)-1.046) -le 0.005 -and $fillRatio -ge 0.998 -and $ctrl.regression_status -eq 'PASS')

# Train / Forward: first 15 zone days vs final 8, exactly as research.
$zoneDays=@((Import-Csv (Join-Path $Root 'data\ranges.csv')) | Where-Object {("$($_.enabled)").Trim().ToLowerInvariant() -notin @('false','0','no','n')} | ForEach-Object {$_.date} | Sort-Object -Unique)
$trainDays=@($zoneDays | Select-Object -First 15)
$forwardDays=@($zoneDays | Select-Object -Skip 15)

$splitRows=@()
foreach($run in $results){
  foreach($scope in @('TRAIN','FORWARD','ALL')){
    $ds=if($scope -eq 'TRAIN'){$trainDays}elseif($scope -eq 'FORWARD'){$forwardDays}else{$zoneDays}
    $d=@($daily | Where-Object {$_.run_id -eq $run.run_id -and $_.date -in $ds})
    $pnl=0.0;$tr=0;$pos=0;$neg=0;$best=0.0;$worst=0.0
    if($d.Count -gt 0){
      foreach($x in $d){$pnl+=Num $x.net_pnl;$tr+=[int]$x.trades;if((Num $x.net_pnl)-gt 0.01){$pos++}elseif((Num $x.net_pnl)-lt -0.01){$neg++}}
      $best=($d|Measure-Object net_pnl -Maximum).Maximum
      $worst=($d|Measure-Object net_pnl -Minimum).Minimum
    }
    # PF from actual trade rows for the requested day set.
    $sp=Join-Path $Root ("results\"+$run.run_id+"\"+$run.run_id+"_summary.csv")
    $trades=@()
    if(Test-Path $sp){
      $trades=@(Import-Csv $sp | Where-Object {$_.category -eq 'PRIMARY_TRADE' -and $_.event -eq 'POSITION_CLOSED' -and $_.counted_in_pnl -eq 'true' -and $_.server_time.Substring(0,10) -in $ds})
    }
    $splitRows += [pscustomobject]@{run_id=$run.run_id;scope=$scope;pnl=[math]::Round($pnl,2);trades=$tr;pf=[math]::Round((PF $trades),3);positive_days=$pos;negative_days=$neg;best_day=[math]::Round($best,2);worst_day=[math]::Round($worst,2)}
  }
}
$splitPath=Join-Path $Root 'results\TRAIN_FORWARD_FINALISTS.csv'
$splitRows | Export-Csv -NoTypeInformation -Encoding UTF8 $splitPath

# Deployment + tail audit.
$deployment=@()
$allTechnical=$true
foreach($r in $results){
  $m=$matrixById[$r.run_id]
  $c=$checkById[$r.run_id]
  $summaryPath=Join-Path $Root ("results\"+$r.run_id+"\"+$r.run_id+"_summary.csv")
  $rows=@(Import-Csv $summaryPath)
  $closed=@($rows|Where-Object{$_.category -eq 'PRIMARY_TRADE' -and $_.event -eq 'POSITION_CLOSED' -and $_.counted_in_pnl -eq 'true'})
  $worstR=0.0
  foreach($x in $closed){
    $r0=Num $x.r0;$p=Num $x.net_pnl
    if($r0 -gt 0){
      $rr=$p/$r0
      if($rr -lt $worstR){$worstR=$rr}
    }
  }
  $overflow=@($rows|Where-Object{$_.event -eq 'POSITION_CAP_OVERFLOW'}).Count
  $blockedCap=@($rows|Where-Object{$_.event -eq 'ENTRY_BLOCKED_POSITION_CAP'}).Count
  $tech=($r.regression_status -eq 'PASS' -and [int]$r.missing_zone_days -eq 0 -and [int]$c.unclosed_positions -eq 0 -and $overflow -eq 0)
  if(-not $tech){$allTechnical=$false}
  $deployment += [pscustomobject]@{
    run_id=$r.run_id;role=$m.run_role;profile=$m.mvp_profile;deposit=$r.deposit;max_live_positions=$m.max_live_positions;
    net_pnl=$r.net_pnl;profit_factor=$r.profit_factor;trades=$r.trades;max_concurrent_positions=$r.max_concurrent_positions;
    margin_blocked=$r.margin_blocked;min_free_margin=$r.min_free_margin;min_margin_level=$r.min_margin_level;
    peak_initial_risk_usd=$r.peak_initial_risk_usd;peak_initial_risk_pct=$r.peak_initial_risk_pct;
    max_realized_drawdown=$r.max_realized_drawdown;max_daily_realized_giveback=$r.max_daily_realized_giveback;
    worst_trade_r=[math]::Round($worstR,3);position_cap_blocks=$blockedCap;position_cap_overflow=$overflow;
    technical_status=if($tech){'PASS'}else{'FAIL'}
  }
}
$depPath=Join-Path $Root 'results\DEPLOYMENT_TAIL_AUDIT.csv'
$deployment | Export-Csv -NoTypeInformation -Encoding UTF8 $depPath

# Automatic research-to-MT5 shortlist status, deliberately not a final live-money promotion.
$decision=@()
foreach($id in @('MT5_F1_SPACE15_HIGH_H2_100K_UNCAPPED','MT5_F2_SPACE15_HIGHSPACE_H2_100K_UNCAPPED')){
  $tr=$splitRows|Where-Object{$_.run_id -eq $id -and $_.scope -eq 'TRAIN'}|Select-Object -First 1
  $fw=$splitRows|Where-Object{$_.run_id -eq $id -and $_.scope -eq 'FORWARD'}|Select-Object -First 1
  $r=$byId[$id]
  $robust=($r.regression_status -eq 'PASS' -and $tr.pnl -gt 0 -and $fw.pnl -gt 0 -and $tr.pf -gt 1.0 -and $fw.pf -gt 1.0)
  $decision += [pscustomobject]@{run_id=$id;train_pnl=$tr.pnl;train_pf=$tr.pf;forward_pnl=$fw.pnl;forward_pf=$fw.pf;all_pnl=$r.net_pnl;all_pf=$r.profit_factor;mt5_robust_status=if($robust){'PASS'}else{'FAIL'}}
}
$decPath=Join-Path $Root 'results\FINALIST_MT5_DECISION_TABLE.csv'
$decision | Export-Csv -NoTypeInformation -Encoding UTF8 $decPath

$deployIds=@('MT5_F1_MVP200_MAX3','MT5_F2_MVP200_MAX3','MT5_F1_MVP300_MAX5','MT5_F2_MVP300_MAX5')
$deployTech=($deployment|Where-Object{$_.run_id -in $deployIds -and $_.technical_status -ne 'PASS'}).Count -eq 0
$gate=($ctrlPass -and $allTechnical -and $deployTech)

$lines=@(
  "MT5_FINALIST_VALIDATION_GATE="+$(if($gate){'PASS'}else{'FAIL'}),
  "CONTROL_EQUIVALENCE="+$(if($ctrlPass){'PASS'}else{'FAIL'}),
  "CONTROL_PNL=$($ctrl.net_pnl)",
  "CONTROL_TRADES=$($ctrl.trades)",
  "CONTROL_PF=$($ctrl.profit_factor)",
  "CONTROL_FILL_KEY_MATCH=$match/$($rk.Count)",
  ("CONTROL_FILL_KEY_MATCH_RATIO={0:F6}" -f $fillRatio),
  "ALL_RUNS_TECHNICAL_QA="+$(if($allTechnical){'PASS'}else{'FAIL'}),
  "DEPLOYMENT_TECHNICAL_QA="+$(if($deployTech){'PASS'}else{'FAIL'}),
  "F1_MT5_ROBUST="+(($decision|Where-Object{$_.run_id -like 'MT5_F1*'}|Select-Object -First 1).mt5_robust_status),
  "F2_MT5_ROBUST="+(($decision|Where-Object{$_.run_id -like 'MT5_F2*'}|Select-Object -First 1).mt5_robust_status),
  "NOTE=This gate validates implementation/equivalence/deployment mechanics. It does not authorize real-money LIVE_SELECTIVE; deferred portfolio risk controls still apply."
)
$gatePath=Join-Path $Root 'MT5_FINALIST_VALIDATION_GATE.txt'
$lines | Set-Content -Encoding UTF8 $gatePath
Get-Content $gatePath
