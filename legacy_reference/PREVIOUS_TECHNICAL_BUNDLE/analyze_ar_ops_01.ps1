$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$phase='AR_OPS_01'
$res=@(Import-Csv (Join-Path $Root "results\RESULT_MATRIX_$phase.csv"))
$checks=@(Import-Csv (Join-Path $Root "results\REGRESSION_CHECKS_$phase.csv"))
$matrix=@(Import-Csv (Join-Path $Root 'test_matrix.csv'))
$ref=@(Import-Csv (Join-Path $Root 'reference\AR_RISK_01_RESULT_MATRIX.csv'))
$by=@{};foreach($x in $res){$by[$x.run_id]=$x}
$cb=@{};foreach($x in $checks){$cb[$x.run_id]=$x}
$rb=@{};foreach($x in $ref){$rb[$x.run_id]=$x}
$mb=@{};foreach($x in $matrix){$mb[$x.run_id]=$x}

function Num($v){if([string]::IsNullOrWhiteSpace("$v")){return 0.0};return [double]::Parse("$v",[Globalization.CultureInfo]::InvariantCulture)}
function Eq($a,$b){return ([math]::Abs((Num $a.net_pnl)-(Num $b.net_pnl)) -le 0.05 -and [int]$a.trades -eq [int]$b.trades -and [math]::Abs((Num $a.profit_factor)-(Num $b.profit_factor)) -le 0.005)}

$eq200=Eq $by['OPSFAST200_CONTROL'] $rb['RISK200_GROSS_15']
$eq300=Eq $by['OPSFAST300_CONTROL'] $rb['RISK300_GROSS_15']

$audit=@()
$allOps=$true
foreach($m in $matrix|Where-Object{$_.run_role -eq 'RESTART'}){
  $id=$m.run_id
  $sp=Join-Path $Root ("results\"+$id+"\"+$id+"_summary.csv")
  $s=@(Import-Csv $sp)
  $locks=@($s|Where-Object{$_.category -eq 'OPS_RECOVERY' -and $_.event -eq 'OPS_RESTART_DAY_LOCK_ENTERED'})
  $flatFail=@($s|Where-Object{$_.category -eq 'OPS_RECOVERY' -and $_.event -eq 'OPS_POSITION_FLAT_FAILED'})
  $cancelFail=@($s|Where-Object{$_.category -eq 'OPS_RECOVERY' -and $_.event -eq 'OPS_PENDING_CANCEL_FAILED'})
  $riskOverflow=@($s|Where-Object{$_.event -eq 'PORTFOLIO_RISK_OVERFLOW'})
  $rt=[datetime]::ParseExact($m.restart_time,'yyyy.MM.dd HH:mm:ss',[Globalization.CultureInfo]::InvariantCulture)
  $day=$rt.ToString('yyyy.MM.dd')
  $next=$rt.Date.AddDays(1)
  # Because weekends/non-zone days may intervene, any later-day fill proves the lock did not become permanent.
  $filled=@($s|Where-Object{$_.category -eq 'PRIMARY_TRADE' -and $_.event -eq 'ORDER_FILLED'})
  $sameDayAfter=@($filled|Where-Object{
     $t=[datetime]::ParseExact($_.server_time.Substring(0,19),'yyyy.MM.dd HH:mm:ss',[Globalization.CultureInfo]::InvariantCulture)
     $t -ge $rt -and $t.ToString('yyyy.MM.dd') -eq $day
  })
  $laterDay=@($filled|Where-Object{
     $t=[datetime]::ParseExact($_.server_time.Substring(0,19),'yyyy.MM.dd HH:mm:ss',[Globalization.CultureInfo]::InvariantCulture)
     $t.Date -gt $rt.Date
  })
  $tech=($cb[$id].unclosed_positions -eq '0' -and [int]$by[$id].margin_blocked -eq 0)
  $pass=($locks.Count -eq 1 -and $sameDayAfter.Count -eq 0 -and $laterDay.Count -gt 0 -and $flatFail.Count -eq 0 -and $cancelFail.Count -eq 0 -and $riskOverflow.Count -eq 0 -and $tech)
  if(-not $pass){$allOps=$false}
  $audit += [pscustomobject]@{
    run_id=$id;restart_time=$m.restart_time;lock_events=$locks.Count;
    same_day_fills_after_restart=$sameDayAfter.Count;later_day_fills=$laterDay.Count;
    flat_fail=$flatFail.Count;pending_cancel_fail=$cancelFail.Count;risk_overflow=$riskOverflow.Count;
    technical_status=if($tech){'PASS'}else{'FAIL'};ops_status=if($pass){'PASS'}else{'FAIL'}
  }
}
$audit|Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $Root 'results\AR_OPS_01_RESTART_AUDIT.csv')

$allTech=@($res|Where-Object{$_.regression_status -ne 'PASS'}).Count -eq 0
$gate=($eq200 -and $eq300 -and $allTech -and $allOps)
@(
 ("AR_OPS_01_VALIDATION_GATE="+$(if($gate){'PASS'}else{'FAIL'})),
 ("GROSS15_200_CONTROL_EQUIVALENCE="+$(if($eq200){'PASS'}else{'FAIL'})),
 ("GROSS15_300_CONTROL_EQUIVALENCE="+$(if($eq300){'PASS'}else{'FAIL'})),
 ("ALL_REGRESSION_QA="+$(if($allTech){'PASS'}else{'FAIL'})),
 ("ALL_RESTART_CASES="+$(if($allOps){'PASS'}else{'FAIL'})),
 ("RESTART_CASES="+$audit.Count),
 "NOTE=PASS means same-day restart is fail-closed: all EA exposure is flattened/cancelled, no new fills occur that broker day, and trading resumes on a later day."
)|Set-Content -Encoding UTF8 (Join-Path $Root 'AR_OPS_01_VALIDATION_GATE.txt')
Get-Content (Join-Path $Root 'AR_OPS_01_VALIDATION_GATE.txt')
$audit|Format-Table -AutoSize
exit 0
