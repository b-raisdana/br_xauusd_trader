$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$phase='AR_RISK_01'
$resPath=Join-Path $Root "results\RESULT_MATRIX_$phase.csv"
$checksPath=Join-Path $Root "results\REGRESSION_CHECKS_$phase.csv"
$prevPath=Join-Path $Root 'reference\PREV_ACCEPTANCE_RESULT_MATRIX.csv'
foreach($p in @($resPath,$checksPath,$prevPath)){if(-not(Test-Path $p)){throw "Required input missing: $p"}}

function Num($v){if([string]::IsNullOrWhiteSpace("$v")){return 0.0};return [double]::Parse("$v",[Globalization.CultureInfo]::InvariantCulture)}
function ParseKV([string]$s,[string]$k){if($s -match ("(?:^|\s)"+[regex]::Escape($k)+"=([-+0-9.]+)")){return Num $Matches[1]};return 0.0}
function PF($rows){$gp=0.0;$gl=0.0;foreach($r in $rows){$p=Num $r.net_pnl;if($p -gt 0.01){$gp+=$p}elseif($p -lt -0.01){$gl+=-$p}};if($gl -le 0){if($gp -gt 0){return 9999.0};return 0.0};return $gp/$gl}

$results=@(Import-Csv $resPath)
$checks=@(Import-Csv $checksPath)
$prev=@(Import-Csv $prevPath)
$matrix=@(Import-Csv (Join-Path $Root 'test_matrix.csv'))
$byId=@{};foreach($r in $results){$byId[$r.run_id]=$r}
$cb=@{};foreach($r in $checks){$cb[$r.run_id]=$r}
$mb=@{};foreach($r in $matrix){$mb[$r.run_id]=$r}

$prev200=$prev|Where-Object{$_.run_id -eq 'ACC_F2_MVP200_MAX3_B23'}|Select-Object -First 1
$prev300=$prev|Where-Object{$_.run_id -eq 'ACC_F2_MVP300_MAX5_B23'}|Select-Object -First 1
$c200=$byId['RISK200_OFF'];$c300=$byId['RISK300_OFF']
function EqRun($a,$b){return ([math]::Abs((Num $a.net_pnl)-(Num $b.net_pnl)) -le 0.05 -and [int]$a.trades -eq [int]$b.trades -and [math]::Abs((Num $a.profit_factor)-(Num $b.profit_factor)) -le 0.005)}
$eq200=EqRun $c200 $prev200;$eq300=EqRun $c300 $prev300

$zoneDays=@((Import-Csv (Join-Path $Root 'data\ranges.csv'))|Where-Object{("$($_.enabled)").Trim().ToLowerInvariant() -notin @('false','0','no','n')}|ForEach-Object{$_.date}|Sort-Object -Unique)
$train=@($zoneDays|Select-Object -First 15);$forward=@($zoneDays|Select-Object -Skip 15)

$detail=@();$split=@()
foreach($r in $results){
  $m=$mb[$r.run_id];$sp=Join-Path $Root ("results\"+$r.run_id+"\"+$r.run_id+"_summary.csv");$sr=@(Import-Csv $sp)
  $risk=@($sr|Where-Object{$_.category -eq 'PORTFOLIO_RISK'})
  $blocks=@($risk|Where-Object{$_.event -eq 'ENTRY_BLOCKED_PORTFOLIO_RISK'})
  $cancels=@($risk|Where-Object{$_.event -eq 'PENDING_CANCELLED_PORTFOLIO_RISK'})
  $overflow=@($risk|Where-Object{$_.event -eq 'PORTFOLIO_RISK_OVERFLOW'})
  $cancelFail=@($risk|Where-Object{$_.event -eq 'PORTFOLIO_RISK_CANCEL_FAILED'})
  $stateErr=@($risk|Where-Object{$_.event -eq 'PORTFOLIO_RISK_STATE_ERROR'})
  $peakUsed=0.0;$peakCommit=0.0;$minRemain=1e99
  foreach($x in $risk){$used=ParseKV $x.note 'used';$new=ParseKV $x.note 'new';$rem=ParseKV $x.note 'remaining';if($used -gt $peakUsed){$peakUsed=$used};if(($used+$new)-gt $peakCommit){$peakCommit=$used+$new};if($x.note -match 'remaining=' -and $rem -lt $minRemain){$minRemain=$rem}}
  if($minRemain -eq 1e99){$minRemain=0.0}
  $c=$cb[$r.run_id]
  $tech=($r.regression_status -eq 'PASS' -and [int]$r.margin_blocked -eq 0 -and [int]$c.unclosed_positions -eq 0 -and $overflow.Count -eq 0 -and $cancelFail.Count -eq 0 -and $stateErr.Count -eq 0)
  $detail += [pscustomobject]@{run_id=$r.run_id;deposit=$r.deposit;risk_mode=$m.risk_mode;risk_pct=$m.risk_pct;trades=$r.trades;pnl=$r.net_pnl;pf=$r.profit_factor;max_concurrent=$r.max_concurrent_positions;max_dd=$r.max_realized_drawdown;daily_giveback=$r.max_daily_realized_giveback;daily_loss_stop=$r.daily_loss_stop;risk_blocks=$blocks.Count;pending_cancels=$cancels.Count;risk_overflow=$overflow.Count;cancel_fail=$cancelFail.Count;state_error=$stateErr.Count;peak_reserved_used=[math]::Round($peakUsed,2);peak_preentry_commit=[math]::Round($peakCommit,2);min_remaining=[math]::Round($minRemain,2);technical_status=if($tech){'PASS'}else{'FAIL'}}
  foreach($scope in @('TRAIN','FORWARD','ALL')){
    $ds=if($scope -eq 'TRAIN'){$train}elseif($scope -eq 'FORWARD'){$forward}else{$zoneDays}
    $closed=@($sr|Where-Object{$_.category -eq 'PRIMARY_TRADE' -and $_.event -eq 'POSITION_CLOSED' -and $_.counted_in_pnl -eq 'true' -and $_.server_time.Substring(0,10) -in $ds})
    $pnl=0.0;foreach($x in $closed){$pnl+=Num $x.net_pnl}
    $split += [pscustomobject]@{run_id=$r.run_id;scope=$scope;trades=$closed.Count;pnl=[math]::Round($pnl,2);pf=[math]::Round((PF $closed),3)}
  }
}
$detail|Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $Root 'results\AR_RISK_01_DETAIL.csv')
$split|Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $Root 'results\AR_RISK_01_TRAIN_FORWARD.csv')

$pairs=@()
foreach($mode in @(1,2)){
 foreach($pct in @(8,10,12.5,15,20)){
  $tag=("$pct").Replace('.','P');$mn=if($mode -eq 1){'NET'}else{'GROSS'}
  $id200="RISK200_${mn}_${tag}";$id300="RISK300_${mn}_${tag}"
  $d200=$detail|Where-Object{$_.run_id -eq $id200}|Select-Object -First 1;$d300=$detail|Where-Object{$_.run_id -eq $id300}|Select-Object -First 1
  $t200=$split|Where-Object{$_.run_id -eq $id200 -and $_.scope -eq 'TRAIN'}|Select-Object -First 1;$f200=$split|Where-Object{$_.run_id -eq $id200 -and $_.scope -eq 'FORWARD'}|Select-Object -First 1
  $t300=$split|Where-Object{$_.run_id -eq $id300 -and $_.scope -eq 'TRAIN'}|Select-Object -First 1;$f300=$split|Where-Object{$_.run_id -eq $id300 -and $_.scope -eq 'FORWARD'}|Select-Object -First 1
  $ret200=[int]$d200.trades/[double][int]$c200.trades;$ret300=[int]$d300.trades/[double][int]$c300.trades;$active=([int]$d200.risk_blocks+[int]$d300.risk_blocks -gt 0)
  $robust=($d200.technical_status -eq 'PASS' -and $d300.technical_status -eq 'PASS' -and $t200.pnl -gt 0 -and $f200.pnl -gt 0 -and $t300.pnl -gt 0 -and $f300.pnl -gt 0 -and $t200.pf -gt 1.0 -and $f200.pf -gt 1.0 -and $t300.pf -gt 1.0 -and $f300.pf -gt 1.0 -and $ret200 -ge 0.70 -and $ret300 -ge 0.70 -and (Num $d200.max_dd) -le (Num $c200.max_realized_drawdown)+0.05 -and (Num $d300.max_dd) -le (Num $c300.max_realized_drawdown)+0.05 -and $active)
  $pairs += [pscustomobject]@{mode=$mn;risk_pct=$pct;pnl200=$d200.pnl;pf200=$d200.pf;forward_pnl200=$f200.pnl;forward_pf200=$f200.pf;dd200=$d200.max_dd;blocks200=$d200.risk_blocks;retention200=[math]::Round($ret200,3);pnl300=$d300.pnl;pf300=$d300.pf;forward_pnl300=$f300.pnl;forward_pf300=$f300.pf;dd300=$d300.max_dd;blocks300=$d300.risk_blocks;retention300=[math]::Round($ret300,3);robust_pf=[math]::Round([math]::Min([math]::Min($t200.pf,$f200.pf),[math]::Min($t300.pf,$f300.pf)),3);portable_status=if($robust){'PASS'}else{'FAIL'}}
 }
}
$pairs=$pairs|Sort-Object @{Expression='portable_status';Descending=$true},@{Expression='robust_pf';Descending=$true},@{Expression='risk_pct';Descending=$false}
$pairs|Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $Root 'results\AR_RISK_01_PORTABLE_BUDGETS.csv')
$allTech=@($detail|Where-Object{$_.technical_status -ne 'PASS'}).Count -eq 0;$gate=($eq200 -and $eq300 -and $allTech);$short=@($pairs|Where-Object{$_.portable_status -eq 'PASS'})
@(
 ("AR_RISK_01_VALIDATION_GATE="+$(if($gate){'PASS'}else{'FAIL'})),
 ("F2_200_OFF_EQUIVALENCE="+$(if($eq200){'PASS'}else{'FAIL'})),
 ("F2_300_OFF_EQUIVALENCE="+$(if($eq300){'PASS'}else{'FAIL'})),
 ("ALL_TECHNICAL_QA="+$(if($allTech){'PASS'}else{'FAIL'})),
 ("PORTABLE_SHORTLIST_COUNT="+$short.Count),
 ("SCENARIOS="+$results.Count),
 "NOTE=Ranking valid only after control equivalence + technical QA PASS."
)|Set-Content -Encoding UTF8 (Join-Path $Root 'AR_RISK_01_VALIDATION_GATE.txt')
Get-Content (Join-Path $Root 'AR_RISK_01_VALIDATION_GATE.txt')
foreach($x in $short){Write-Host ("SHORTLIST {0} {1}% | 200 PnL={2} PF={3} Fwd={4}/PF{5} DD={6} Blocks={7} | 300 PnL={8} PF={9} Fwd={10}/PF{11} DD={12} Blocks={13} | robustPF={14}" -f $x.mode,$x.risk_pct,$x.pnl200,$x.pf200,$x.forward_pnl200,$x.forward_pf200,$x.dd200,$x.blocks200,$x.pnl300,$x.pf300,$x.forward_pnl300,$x.forward_pf300,$x.dd300,$x.blocks300,$x.robust_pf)}
exit 0
