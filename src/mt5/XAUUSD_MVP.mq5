#property strict
#property version "1.000"
#property description "Research-only XAUUSD MVP contract baseline"

#include "generated/CoreVectors.mqh"
#include "include/XauContracts.mqh"
#include "generated/DailyZones.mqh"
#include "include/XauExecution.mqh"
#include "include/XauAudit.mqh"
#include "include/XauNative.mqh"
#include "include/XauState.mqh"
#include "include/XauCoordinator.mqh"
#include "include/XauRequests.mqh"
#include "include/XauTesterBroker.mqh"
#include "include/XauVisual.mqh"

input bool InpEnableTrading=false;
input bool InpEmitTimeBasisProbe=false;
input bool InpObserveNativeOutcomes=false;
input long InpStrategyMagic=0;
input bool InpRunCurrentEventLoop=false;
input bool InpEnableTesterExecution=false;

int g_time_basis_probe_count=0;
XauExecutionProjection g_execution_projections[];
XauExecutionBinding g_execution_bindings[];
const string EXECUTION_BINDINGS_FILE="XAUUSD_Current\\bindings.tsv";
XauMarketCoordinator g_market_state;
datetime g_current_bar_time=0;
bool g_event_loop_ready=false;
bool g_event_loop_failure_reported=false;
long g_breakout_candidate_count=0;
long g_reversal_candidate_count=0;
long g_pullback_candidate_count=0;

bool NearlyEqual(const double left,const double right)
  {
   return MathAbs(left-right) <= PARITY_PRICE_TOLERANCE;
  }

bool RunCoreVectorSmoke()
  {
   XauZone breakout_zone;
   breakout_zone.id="2026-09-06:R1";
   breakout_zone.low=VEC_BREAKOUT_LOW;
   breakout_zone.high=VEC_BREAKOUT_HIGH;
   if(!BreakoutValid(breakout_zone,XAU_BUY,XAU_TREND_UP,VEC_BREAKOUT_CLOSE,true))
      return false;
   if(!ReversalDirectionalTouch(breakout_zone,XAU_SELL,XAU_TREND_UP,
                                VEC_REVERSAL_PREVIOUS,VEC_REVERSAL_CURRENT,false))
      return false;
   if(UpdateTrend(XAU_TREND_NONE,1,VEC_TREND_REFERENCE_HIGH,VEC_TREND_REFERENCE_LOW,
                  VEC_TREND_BID) != XAU_TREND_UP)
      return false;

   XauZone pullback_zone;
   pullback_zone.id="2026-09-06:R1";
   pullback_zone.low=VEC_PULLBACK_LOW;
   pullback_zone.high=VEC_PULLBACK_HIGH;
   double pullback_entry=0.0;
   if(!PullbackPenetrated(pullback_zone,XAU_BUY,VEC_PULLBACK_BID,pullback_entry) ||
      !NearlyEqual(pullback_entry,VEC_PULLBACK_HIGH))
      return false;
   int closed_directions[2]={1,1};
   if(!StrictPullbackTrend(XAU_BUY,closed_directions,VEC_STRICT_CURRENT_OPEN,
                           VEC_STRICT_CURRENT_BID,VEC_STRICT_CURRENT_ASK))
      return false;

   XauZone trigger_zone;
   trigger_zone.id="2026-09-06:R2";
   trigger_zone.low=VEC_TRIGGER_TARGET_LOW;
   trigger_zone.high=VEC_TRIGGER_TARGET_HIGH;
   if(!NearlyEqual(PreZoneTriggerPrice(XAU_BUY,trigger_zone),VEC_TRIGGER_TARGET_LOW-1.0) ||
      !PreZoneCrossed(XAU_BUY,trigger_zone,VEC_TRIGGER_PREVIOUS,VEC_TRIGGER_CURRENT))
      return false;

   XauZone risk_zones[4];
   risk_zones[0].id="R1"; risk_zones[0].low=VEC_RISK_ZONE_1_LOW; risk_zones[0].high=VEC_RISK_ZONE_1_HIGH;
   risk_zones[1].id="R2"; risk_zones[1].low=VEC_RISK_ZONE_2_LOW; risk_zones[1].high=VEC_RISK_ZONE_2_HIGH;
   risk_zones[2].id="R3"; risk_zones[2].low=VEC_RISK_ZONE_3_LOW; risk_zones[2].high=VEC_RISK_ZONE_3_HIGH;
   risk_zones[3].id="R4"; risk_zones[3].low=VEC_RISK_ZONE_4_LOW; risk_zones[3].high=VEC_RISK_ZONE_4_HIGH;
   double sl=0.0,tp=0.0;
   string stop_zone="",target_zone="";
   if(!InitialStop(XAU_BUY,VEC_RISK_ENTRY,risk_zones,sl,stop_zone) ||
      !InitialTarget(XAU_BUY,VEC_RISK_ENTRY,risk_zones,tp,target_zone))
      return false;
   if(!NearlyEqual(sl,VEC_RISK_EXPECTED_SL) || !NearlyEqual(tp,VEC_RISK_EXPECTED_TP) ||
      stop_zone!="R2" || target_zone!="R4")
      return false;
   if(!PortfolioRiskAllows(VEC_PORTFOLIO_CAPITAL,VEC_PORTFOLIO_REALIZED,
                           VEC_PORTFOLIO_OPEN,VEC_PORTFOLIO_PENDING,
                           VEC_PORTFOLIO_PROPOSED))
      return false;
   double protected_stop=0.0;
   if(!ProfitProtectionStop(XAU_BUY,VEC_PROTECTION_ENTRY,VEC_PROTECTION_RF,
                            VEC_PROTECTION_BID,VEC_PROTECTION_ASK,
                            VEC_PROTECTION_CURRENT_SL,protected_stop) ||
      !NearlyEqual(protected_stop,118.25))
      return false;
   if(!DailyLossLocked(VEC_DAILY_CAPITAL,VEC_DAILY_NET_PNL,false))
      return false;
   if(!SessionEndActive(StringToTime(VEC_SESSION_NOW),StringToTime(VEC_SESSION_END)))
      return false;

   XauZone merge_raw[4];
   merge_raw[0].low=VEC_MERGE_ZONE_1_LOW; merge_raw[0].high=VEC_MERGE_ZONE_1_HIGH; merge_raw[0].priority=VEC_MERGE_ZONE_1_PRIORITY;
   merge_raw[1].low=VEC_MERGE_ZONE_2_LOW; merge_raw[1].high=VEC_MERGE_ZONE_2_HIGH; merge_raw[1].priority=VEC_MERGE_ZONE_2_PRIORITY;
   merge_raw[2].low=VEC_MERGE_ZONE_3_LOW; merge_raw[2].high=VEC_MERGE_ZONE_3_HIGH; merge_raw[2].priority=VEC_MERGE_ZONE_3_PRIORITY;
   merge_raw[3].low=VEC_MERGE_ZONE_4_LOW; merge_raw[3].high=VEC_MERGE_ZONE_4_HIGH; merge_raw[3].priority=VEC_MERGE_ZONE_4_PRIORITY;
   XauZone merged[];
   if(BuildMergedZones(merge_raw,"2026-09-06",merged) != VEC_MERGE_EXPECTED_COUNT ||
      !NearlyEqual(merged[0].low,100.0) || !NearlyEqual(merged[0].high,105.0) ||
      merged[0].priority != 1 || merged[0].id != "2026-09-06:R1" ||
      merged[1].id != "2026-09-06:R2")
      return false;

   XauZone gap_zones[2];
   gap_zones[0].low=VEC_GAP_ZONE_1_LOW; gap_zones[0].high=VEC_GAP_ZONE_1_HIGH;
   gap_zones[1].low=VEC_GAP_ZONE_2_LOW; gap_zones[1].high=VEC_GAP_ZONE_2_HIGH;
   if(CountDirectionalCrosses(gap_zones,VEC_GAP_PREVIOUS,VEC_GAP_CURRENT) != 2)
      return false;
   if(!PullbackWindowActive(VEC_PULLBACK_BAR_OFFSET) ||
      !PullbackUsageAllowed(1,VEC_PULLBACK_DAILY_FILLS))
      return false;
   if(PullbackTpFailureAction(XAU_BUY,true,false,VEC_TP_INITIAL,
                              VEC_TP_CURRENT_BID,VEC_TP_CURRENT_ASK) != XAU_TP_RESTORE)
      return false;
   if(!RestartSameDayLocked(VEC_RESTART_DAY,VEC_RESTART_LAST_DAY))
      return false;

   XauExecutionStatus next_status=XAU_EXECUTION_CANCELLED;
   bool transition_allowed=ExecutionTransition(
      (XauExecutionStatus)VEC_EXECUTION_STATUS,
      (XauExecutionEvent)VEC_EXECUTION_EVENT,
      (XauOrderType)VEC_EXECUTION_ORDER_TYPE,
      next_status);
   if(transition_allowed != (VEC_EXECUTION_EXPECTED_ALLOWED != 0) ||
      next_status != (XauExecutionStatus)VEC_EXECUTION_EXPECTED_STATUS)
      return false;
   XauZone causal_zone;
   causal_zone.low=VEC_CAUSAL_ZONE_LOW;
   causal_zone.high=VEC_CAUSAL_ZONE_HIGH;
   XauTrend causal_trend=XAU_TREND_NONE;
   if(!CausalTrendThenReversal(causal_zone,XAU_SELL,XAU_TREND_NONE,1,
                               VEC_CAUSAL_REFERENCE_HIGH,VEC_CAUSAL_REFERENCE_LOW,
                               VEC_CAUSAL_PREVIOUS,VEC_CAUSAL_BID,causal_trend) ||
      causal_trend != XAU_TREND_UP)
      return false;
   return ProtectionModificationValid(
      (XauDirection)VEC_MODIFICATION_DIRECTION,
      VEC_MODIFICATION_ENTRY,VEC_MODIFICATION_CURRENT_SL,VEC_MODIFICATION_PROPOSED_SL,
      VEC_MODIFICATION_PROPOSED_TP) ==
      (VEC_MODIFICATION_EXPECTED_VALID != 0);
  }

bool RunExecutionProjectorSmoke()
  {
   const datetime submitted_at=StringToTime("2026.09.06 10:00:00");
   XauExecutionProjection position;
   if(!InitializeExecutionProjection(position,"REQ-M",XAU_ORDER_MARKET,XAU_BUY,
                                     100.0,96.0,108.0,submitted_at))
      return false;
   if(!ProjectExecutionOutcome(position,XAU_EXECUTION_FILL,submitted_at+1,100.1) ||
      position.status != XAU_EXECUTION_FILLED || !NearlyEqual(position.fill_price,100.1))
      return false;
   if(!ProjectExecutionOutcome(position,XAU_EXECUTION_MODIFY_REJECT,submitted_at+2,
                               0.0,97.0,110.0) || !NearlyEqual(position.stop_loss,96.0))
      return false;
   if(!ProjectExecutionOutcome(position,XAU_EXECUTION_MODIFY,submitted_at+3,
                               0.0,97.0,110.0) || !NearlyEqual(position.stop_loss,97.0) ||
      !NearlyEqual(position.take_profit,110.0))
      return false;
   if(!ProjectExecutionOutcome(position,XAU_EXECUTION_CLOSE,submitted_at+4,109.0) ||
      position.status != XAU_EXECUTION_CLOSED || !NearlyEqual(position.close_price,109.0))
      return false;
   if(ProjectExecutionOutcome(position,XAU_EXECUTION_CLOSE,submitted_at+5,109.0))
      return false;

   XauExecutionProjection pending;
   if(!InitializeExecutionProjection(pending,"REQ-P",XAU_ORDER_PENDING_STOP,XAU_BUY,
                                     100.0,96.0,108.0,submitted_at))
      return false;
   if(!ProjectExecutionOutcome(pending,XAU_EXECUTION_CANCEL_REJECT,submitted_at+1) ||
      pending.status != XAU_EXECUTION_SUBMITTED)
      return false;
   if(!ProjectExecutionOutcome(pending,XAU_EXECUTION_CANCEL,submitted_at+2) ||
      pending.status != XAU_EXECUTION_CANCELLED)
      return false;

   XauExecutionBinding bindings[];
   string resolved_request="";
   if(!BindExecutionOrder(bindings,"REQ-M",101) ||
      !ResolveExecutionRequest(bindings,XAU_EXECUTION_FILL,101,0,resolved_request) ||
      resolved_request != "REQ-M" || !BindExecutionPosition(bindings,101,201) ||
      !ResolveExecutionRequest(bindings,XAU_EXECUTION_CLOSE,0,201,resolved_request) ||
      resolved_request != "REQ-M" || BindExecutionOrder(bindings,"REQ-X",101) ||
      BindExecutionPosition(bindings,101,202))
      return false;
   const string bindings_file="XAUUSD_Current\\binding_smoke.tsv";
   XauExecutionBinding recovered_bindings[];
   if(!SaveExecutionBindingsAtomically(bindings_file,bindings) ||
      !LoadExecutionBindings(bindings_file,recovered_bindings) ||
      !SameExecutionBindings(bindings,recovered_bindings))
      return false;
   FileDelete(bindings_file);

   const string corrupt_file="XAUUSD_Current\\binding_corrupt_smoke.tsv";
   int corrupt_handle=FileOpen(corrupt_file,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(corrupt_handle == INVALID_HANDLE)
      return false;
   FileWriteString(corrupt_handle,
                   "XAU_EXECUTION_BINDINGS\t1\r\nREQ-A\t301\t0\r\nREQ-B\t301\t0\r\n");
   FileClose(corrupt_handle);
   if(LoadExecutionBindings(corrupt_file,recovered_bindings) ||
      !SameExecutionBindings(bindings,recovered_bindings) ||
      SaveExecutionBindingsAtomically("..\\binding_escape.tsv",bindings))
      return false;
   FileDelete(corrupt_file);

   XauExecutionProjection native_projections[1];
   XauExecutionBinding native_bindings[];
   if(!InitializeExecutionProjection(native_projections[0],"REQ-N",XAU_ORDER_MARKET,
                                     XAU_BUY,100.0,96.0,108.0,submitted_at) ||
      !BindExecutionOrder(native_bindings,"REQ-N",401) ||
      !ProjectCorrelatedNativeOutcome(native_projections,native_bindings,
                                      XAU_EXECUTION_FILL,401,501,submitted_at+1,100.2) ||
      native_projections[0].status != XAU_EXECUTION_FILLED ||
      !ProjectCorrelatedNativeOutcome(native_projections,native_bindings,
                                      XAU_EXECUTION_CLOSE,0,501,submitted_at+2,107.5) ||
      native_projections[0].status != XAU_EXECUTION_CLOSED ||
      ProjectCorrelatedNativeOutcome(native_projections,native_bindings,
                                     XAU_EXECUTION_CLOSE,0,999,submitted_at+3,107.5))
      return false;
   Print("EXECUTION_PROJECTOR_SMOKE_PASS lifecycle/protection/correlation/persistence/orchestration mode=inert");
   return true;
  }

bool RunGuardedNativeCallbackSmoke()
  {
   const datetime submitted_at=StringToTime("2026.09.06 11:00:00");
   XauExecutionProjection projections[1];
   XauExecutionBinding bindings[];
   const string bindings_file="XAUUSD_Current\\callback_binding_smoke.tsv";
   if(!InitializeExecutionProjection(projections[0],"REQ-CB",XAU_ORDER_MARKET,
                                     XAU_BUY,100.0,96.0,108.0,submitted_at) ||
      !BindExecutionOrder(bindings,"REQ-CB",601) ||
      !PersistThenPublishCorrelatedNativeOutcome(projections,bindings,
                                                 XAU_EXECUTION_FILL,601,701,
                                                 submitted_at+1,100.2,bindings_file) ||
      projections[0].status != XAU_EXECUTION_FILLED || bindings[0].position_id != 701 ||
      !FileIsExist(bindings_file))
      return false;
   FileDelete(bindings_file);
   Print("NATIVE_CALLBACK_SMOKE_PASS opt-in/correlation/persist-before-state mode=inert");
   return true;
  }

bool RunStateOrderingSmoke()
  {
   XauTrendReferenceState state;
   BeginTrendDay(state);
   if(!RecordTrendCandle(state,VEC_CAUSAL_REFERENCE_HIGH,VEC_CAUSAL_REFERENCE_LOW) ||
      ProcessTrendTick(state,VEC_CAUSAL_BID) != XAU_TREND_UP)
      return false;
   XauZone zone;
   zone.low=VEC_BREAKOUT_LOW;
   zone.high=VEC_BREAKOUT_HIGH;
   bool breakout=false;
   if(!CloseBarBreakoutBeforeRoll(state,zone,XAU_BUY,VEC_BREAKOUT_CLOSE,true,
                                  103.0,99.0,breakout) || !breakout || state.count != 2)
      return false;
   XauZone daily_zones[2];
   daily_zones[0].id="R1"; daily_zones[0].low=100.0; daily_zones[0].high=101.0;
   daily_zones[0].priority=0;
   daily_zones[1].id="R2"; daily_zones[1].low=103.0; daily_zones[1].high=104.0;
   daily_zones[1].priority=1;
   XauDailyZoneSignalState daily_states[];
   bool multi_zone_gap=false;
   int breakout_sequence=0;
   string attempted_bars[];
   if(!InitializeDailyZoneStates(daily_zones,daily_states))
      return false;
   BeginSignalBar(daily_states,99.0);
   if(!UpdateZoneEngagement(daily_states,99.0,100.0,multi_zone_gap) || multi_zone_gap ||
      !daily_states[0].buy_engaged || NextBreakoutId(breakout_sequence) != "BO1" ||
      !ConsumeReversalUsage(daily_states[0]) || ConsumeReversalUsage(daily_states[0]) ||
      !ConsumeReversalUsage(daily_states[1]) || !ConsumeReversalUsage(daily_states[1]) ||
      ConsumeReversalUsage(daily_states[1]) || !RecordEntryAttempt(attempted_bars,"t1") ||
      RecordEntryAttempt(attempted_bars,"t1"))
      return false;
   XauPullbackWindowState pullback;
   bool pending_must_cancel=false;
   string candidate_id="";
   double pullback_entry=0.0;
   if(!CreatePullbackWindow(pullback,"BO1",daily_states[1].zone,XAU_BUY) ||
      !BeginPullbackBar(pullback,pending_must_cancel) || pending_must_cancel ||
      !EvaluatePullbackPrice(pullback,daily_states[1].pullback_fills,103.80,
                             candidate_id,pullback_entry) || candidate_id != "BO1:PB1" ||
      !NearlyEqual(pullback_entry,104.0) ||
      !RecordPullbackAttempt(pullback,attempted_bars,"t2",true) ||
      !RecordPullbackFill(pullback,daily_states[1]) || daily_states[1].pullback_fills != 1 ||
      !BeginPullbackBar(pullback,pending_must_cancel) ||
      !EvaluatePullbackPrice(pullback,daily_states[1].pullback_fills,103.80,
                             candidate_id,pullback_entry) || candidate_id != "BO1:PB2" ||
      !RecordPullbackAttempt(pullback,attempted_bars,"t3",true))
      return false;
   for(int offset=3;offset<=6;offset++)
      if(!BeginPullbackBar(pullback,pending_must_cancel))
         return false;
   if(!pending_must_cancel || pullback.active)
      return false;
   XauZone initial_target,next_target;
   initial_target.id="R3"; initial_target.low=110.0; initial_target.high=111.0;
   next_target.id="R4"; next_target.low=116.0; next_target.high=117.0;
   XauPreZoneTriggerState trigger_state;
   XauPullbackTpState tp_state;
   double requested_tp=0.0;
   string target_zone_id="";
   if(!PreZoneCrossOnce(trigger_state,"POS1",XAU_BUY,initial_target,108.0,109.0) ||
      PreZoneCrossOnce(trigger_state,"POS1",XAU_BUY,initial_target,108.0,110.0) ||
      !BlocksOppositeReversal(true,true) || BlocksOppositeReversal(false,true) ||
      !InitializePullbackTp(tp_state,"POS1",XAU_BUY,initial_target) ||
      !ProposePullbackTpExtension(tp_state,initial_target,next_target,true,true,
                                  requested_tp,target_zone_id) ||
      !NearlyEqual(requested_tp,116.0) || target_zone_id != "R4" ||
      !RecordPullbackTpExtension(tp_state,requested_tp,target_zone_id,true) ||
      !tp_state.extended || ProposePullbackTpExtension(tp_state,initial_target,next_target,
                                                       true,true,requested_tp,target_zone_id))
      return false;
   if(EvaluatePullbackTpFailure(tp_state,false,109.0,109.1,requested_tp) != XAU_TP_RESTORE ||
      !NearlyEqual(requested_tp,110.0))
      return false;
   RecordPullbackTpRestore(tp_state,true);
   if(tp_state.extended || !NearlyEqual(tp_state.current_tp,110.0))
      return false;
   Print("STATE_ORDER_SMOKE_PASS tick/trend/bar-close mode=inert");
   return true;
  }

bool RunCoordinatorSmoke()
  {
   XauZone zones[1];
   zones[0].id="2026-09-06:R1";
   zones[0].low=100.0;
   zones[0].high=101.0;
   zones[0].priority=0;
   XauMarketCoordinator state;
   int cancellations=0;
   XauSignalCandidate candidates[];
   XauSignalCandidate breakouts[];
   if(!BeginCoordinatorDay(state,"2026-09-06",zones) ||
      !RecordTrendCandle(state.trend,99.5,98.0) ||
      !BeginCoordinatorBar(state,"2026-09-06T10:00",99.0,99.1,cancellations) ||
      cancellations != 0 ||
      !ProcessCoordinatorTick(state,StringToTime("2026.09.06 10:01:00"),100.0,100.1,
                              candidates) || ArraySize(candidates) != 1 ||
      candidates[0].family != XAU_SIGNAL_REVERSAL ||
      !ProcessCoordinatorTick(state,StringToTime("2026.09.06 10:02:00"),102.1,102.2,
                              candidates) || ArraySize(candidates) != 0 ||
      !CloseCoordinatorBar(state,StringToTime("2026.09.06 10:15:00"),102.2,99.0,102.1,
                           breakouts) || ArraySize(breakouts) != 1 ||
      breakouts[0].family != XAU_SIGNAL_BREAKOUT ||
      ArraySize(state.pullbacks) != 1 || state.trend.count != 2 ||
      !BeginCoordinatorBar(state,"2026-09-06T10:15",102.1,102.2,cancellations) ||
      state.pullbacks[0].bar_offset != 1)
      return false;
   Print("COORDINATOR_SMOKE_PASS day/bar/tick/trend/engagement/signal/close mode=inert");
   return true;
  }

bool RunSafetyRequestSmoke()
  {
   const bool portfolio_allowed=PortfolioRiskAllows(200.0,5.0,10.0,7.0,8.0);
   if(!portfolio_allowed || !ConcurrencyAllowsEntry(200.0,2) ||
      ConcurrencyAllowsEntry(200.0,3) || !NativeMarginAllowsEntry(10.0,10.0) ||
      NativeMarginAllowsEntry(10.01,10.0))
      return false;
   if(EvaluateProtectedEntry(true,false,false,false,XAU_BUY,100.0,96.0,108.0,0.01) !=
      XAU_ENTRY_DAILY_LOSS)
      return false;
   if(EvaluateProtectedEntry(false,false,true,true,XAU_BUY,100.0,96.0,108.0,0.01) !=
      XAU_ENTRY_GROSS_RISK)
      return false;
   if(EvaluateProtectedEntry(false,true,true,true,XAU_BUY,100.0,96.0,108.0,0.01) !=
      XAU_ENTRY_ALLOWED)
      return false;
   XauOperationalSafety operations=EvaluateOperationalSafety(false,true);
   if(!operations.locked || !operations.block_entries || !operations.cancel_pending ||
      !operations.cancel_pullback_cycles || !operations.close_positions)
      return false;
   Print("SAFETY_REQUEST_SMOKE_PASS daily/gross/concurrency/margin/operations mode=inert");
   return true;
  }

bool RunPreparedRequestSmoke()
  {
   XauZone zones[3];
   zones[0].id="2026-09-06:R1"; zones[0].low=90.0; zones[0].high=91.0; zones[0].priority=0;
   zones[1].id="2026-09-06:R2"; zones[1].low=100.0; zones[1].high=101.0; zones[1].priority=0;
   zones[2].id="2026-09-06:R3"; zones[2].low=108.0; zones[2].high=109.0; zones[2].priority=1;
   XauSignalCandidate candidate;
   candidate.candidate_id="BAR:R:R2:0";
   candidate.parent_breakout_id="";
   candidate.bar_id="2026-09-06T10:00";
   candidate.zone_id=zones[1].id;
   candidate.family=XAU_SIGNAL_REVERSAL;
   candidate.direction=XAU_BUY;
   candidate.order_type=XAU_ORDER_MARKET;
   candidate.signal_time=StringToTime("2026.09.06 10:01:00");
   candidate.entry_price=101.0;
   XauPreparedEntry prepared;
   if(!PrepareCandidateEntry(candidate,zones,false,200.0,0.0,0.0,0.0,0,6.0,10.0,
                             200.0,prepared) ||
      prepared.decision != XAU_ENTRY_ALLOWED || !NearlyEqual(prepared.stop_loss,95.0) ||
      !NearlyEqual(prepared.take_profit,108.0))
      return false;
   XauOrderAuditEvent event;
   XauExecutionProjection projections[];
   const string audit_file="XAUUSD_Current\\prepared_request_smoke.jsonl";
   if(!BuildPreparedOrderAudit(prepared,"2026-09-06:E000002","REQ-PREP",event) ||
      !AppendOrderThenProject(audit_file,prepared.decision,event,projections) ||
      ArraySize(projections) != 1)
      return false;
   FileDelete(audit_file);
   XauMarketCoordinator state;
   if(!BeginCoordinatorDay(state,"2026-09-06",zones) ||
      !CommitPreparedEntryAttempt(state,prepared,false) ||
      state.zones[1].reversal_usage != 1 || ArraySize(state.attempted_bars) != 1 ||
      CommitPreparedEntryAttempt(state,prepared,true))
      return false;
   Print("PREPARED_REQUEST_SMOKE_PASS space/risk/safety/audit/attempt mode=inert");
   return true;
  }

bool RunAuditRequestSmoke()
  {
   const string audit_file="XAUUSD_Current\\audit_smoke.jsonl";
   XauOrderAuditEvent event;
   event.event_id="2026-09-06:E000001";
   event.request_id="REQ-AUDIT";
   event.zone_id="2026-09-06:R2";
   event.rule_ids="REVERSAL_DIRECTIONAL_TOUCH";
   event.direction=XAU_BUY;
   event.order_type=XAU_ORDER_MARKET;
   event.broker_time=StringToTime("2026.09.06 10:00:00");
   event.entry=100.0;
   event.stop_loss=96.0;
   event.take_profit=108.0;
   XauExecutionProjection projections[];
   if(AppendOrderThenProject(audit_file,XAU_ENTRY_DAILY_LOSS,event,projections) ||
      ArraySize(projections) != 0 ||
      !AppendOrderThenProject(audit_file,XAU_ENTRY_ALLOWED,event,projections) ||
      ArraySize(projections) != 1 || projections[0].request_id != "REQ-AUDIT" ||
      !FileIsExist(audit_file))
      return false;
   FileDelete(audit_file);
   Print("AUDIT_REQUEST_SMOKE_PASS durable-before-state mode=inert");
   return true;
  }

bool RunNativeAdapterSmoke()
  {
   XauExecutionEvent native_event=XAU_EXECUTION_REJECT;
   if(!ClassifyNativeDealEntry(DEAL_ENTRY_IN,native_event) ||
      native_event != XAU_EXECUTION_FILL ||
      !ClassifyNativeDealEntry(DEAL_ENTRY_OUT,native_event) ||
      native_event != XAU_EXECUTION_CLOSE ||
      ClassifyNativeDealEntry(DEAL_ENTRY_INOUT,native_event))
      return false;

   XauNativeSymbol specification;
   if(!LoadNativeSymbol(_Symbol,specification))
     {
      Print("Native adapter smoke failed: symbol metadata.");
      return false;
     }

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.ask<=specification.point)
     {
      Print("Native adapter smoke failed: current tick.");
      return false;
     }
   double cash_risk=0.0,margin=0.0;
   if(!NativeCashRisk(ORDER_TYPE_BUY,_Symbol,specification.volume_min,
                      tick.ask,tick.ask-specification.point,cash_risk))
     {
      Print("Native adapter smoke failed: cash risk.");
      return false;
     }
   if(!NativeRequiredMargin(ORDER_TYPE_BUY,_Symbol,specification.volume_min,
                            tick.ask,margin))
     {
      Print("Native adapter smoke failed: margin.");
      return false;
     }

   datetime session_from=0,session_to=0;
   if(!NativeContainingTradeSession(_Symbol,TimeCurrent(),session_from,session_to) ||
      session_to<=session_from)
     {
      Print("Native adapter smoke failed: trade session.");
      return false;
     }
   Print("NATIVE_ADAPTER_SMOKE_PASS symbol/session/risk/margin/deal-map mode=read-only");
   return true;
  }

bool RunVisualPayloadSmoke()
  {
   XauVisualMarker marker;
   marker.event_id="2026-09-06:E000001";
   marker.zone_id="2026-09-06:R1";
   marker.label="R-B";
   marker.broker_time=StringToTime("2026.09.06 10:15:00");
   marker.entry=3400.10;
   marker.stop_loss=3396.00;
   marker.take_profit=3408.00;
   marker.zone_priority=1;
   string tooltip=XauMarkerTooltip(marker,2);
   if(StringFind(tooltip,"Time=")<0 || StringFind(tooltip,"Zone=2026-09-06:R1")<0 ||
      StringFind(tooltip,"Entry=3400.10")<0 || StringFind(tooltip,"SL=3396.00")<0 ||
      StringFind(tooltip,"TP=3408.00")<0 ||
      StringFind(tooltip,"Event=2026-09-06:E000001")<0)
      return false;
   Print("VISUAL_PAYLOAD_SMOKE_PASS labels/tooltip mode=render-only");
   return true;
  }

bool InitializeCurrentEventLoop(const MqlTick &tick,const datetime bar_time)
  {
   const string broker_day=TimeToString(tick.time,TIME_DATE);
   XauZone raw_zones[];
   XauZone merged_zones[];
   if(!LoadGeneratedRawZones(broker_day,raw_zones))
      return false;
   string zone_day=broker_day;
   StringReplace(zone_day,".","-");
   if(BuildMergedZones(raw_zones,zone_day,merged_zones) <= 0 ||
      !BeginCoordinatorDay(g_market_state,zone_day,merged_zones))
      return false;

   MqlDateTime day_parts;
   if(!TimeToStruct(tick.time,day_parts))
      return false;
   day_parts.hour=0;
   day_parts.min=0;
   day_parts.sec=0;
   const datetime day_start=StructToTime(day_parts);
   if(bar_time > day_start)
     {
      MqlRates history[];
      const int copied=CopyRates(_Symbol,PERIOD_M15,day_start,bar_time-1,history);
      const datetime previous_bar=iTime(_Symbol,PERIOD_M15,1);
      if(copied < 0 && previous_bar >= day_start)
         return false;
      const int history_count=(copied > 0 ? copied : 0);
      for(int i=0;i<history_count;i++)
         if(!RecordTrendCandle(g_market_state.trend,history[i].high,history[i].low))
            return false;
     }

   const double open_bid=iOpen(_Symbol,PERIOD_M15,0);
   int pending_cancellations=0;
   if(open_bid <= 0.0 ||
      !BeginCoordinatorBar(g_market_state,TimeToString(bar_time,TIME_DATE|TIME_MINUTES),
                           open_bid,open_bid+MathMax(0.0,tick.ask-tick.bid),
                           pending_cancellations))
      return false;
   g_current_bar_time=bar_time;
   g_event_loop_ready=true;
   PrintFormat("CURRENT_EVENT_LOOP_READY zones=%d history_bars=%d mode=inert",
               ArraySize(merged_zones),g_market_state.trend.count);
   return true;
  }

bool ProcessCurrentEventLoopTick(const MqlTick &tick)
  {
   const datetime bar_time=iTime(_Symbol,PERIOD_M15,0);
   if(bar_time <= 0)
      return false;
   if(!g_event_loop_ready)
     {
      if(!InitializeCurrentEventLoop(tick,bar_time))
         return false;
     }
   else if(TimeToString(tick.time,TIME_DATE) !=
           StringSubstr(g_market_state.broker_day,0,4)+"."+
           StringSubstr(g_market_state.broker_day,5,2)+"."+
           StringSubstr(g_market_state.broker_day,8,2))
     {
      g_event_loop_ready=false;
      if(!InitializeCurrentEventLoop(tick,bar_time))
         return false;
     }
   else if(bar_time != g_current_bar_time)
     {
      XauSignalCandidate breakouts[];
      const double high=iHigh(_Symbol,PERIOD_M15,1);
      const double low=iLow(_Symbol,PERIOD_M15,1);
      const double close_bid=iClose(_Symbol,PERIOD_M15,1);
      if(!CloseCoordinatorBar(g_market_state,bar_time,high,low,close_bid,breakouts))
         return false;
      int pending_cancellations=0;
      const double open_bid=iOpen(_Symbol,PERIOD_M15,0);
      if(!BeginCoordinatorBar(g_market_state,
                              TimeToString(bar_time,TIME_DATE|TIME_MINUTES),open_bid,
                              open_bid+MathMax(0.0,tick.ask-tick.bid),pending_cancellations))
         return false;
      g_current_bar_time=bar_time;
      if(ArraySize(breakouts)>0 || pending_cancellations>0)
        {
         g_breakout_candidate_count+=ArraySize(breakouts);
         PrintFormat("CURRENT_EVENT_LOOP_CLOSE breakouts=%d cancellations=%d mode=inert",
                     ArraySize(breakouts),pending_cancellations);
        }
     }

   XauSignalCandidate candidates[];
   if(!ProcessCoordinatorTick(g_market_state,tick.time,tick.bid,tick.ask,candidates))
      return false;
   for(int i=0;i<ArraySize(candidates);i++)
      if(candidates[i].family == XAU_SIGNAL_REVERSAL)
         g_reversal_candidate_count++;
      else if(candidates[i].family == XAU_SIGNAL_PULLBACK)
         g_pullback_candidate_count++;
   return true;
  }

int OnInit()
  {
   if(InpEnableTrading)
     {
      Print("Live/trading execution is not implemented or approved; initialization blocked.");
      return INIT_FAILED;
     }
   if(InpObserveNativeOutcomes && InpStrategyMagic<=0)
     {
      Print("Native outcome observation requires an explicit positive strategy Magic.");
      return INIT_FAILED;
     }
   if(InpEnableTesterExecution &&
      (!(bool)MQLInfoInteger(MQL_TESTER) || InpStrategyMagic<=0))
     {
      Print("Tester execution requires Strategy Tester and an explicit positive Magic.");
      return INIT_FAILED;
     }
   if(!RunCoreVectorSmoke())
     {
      Print("Core contract vector smoke failed.");
      return INIT_FAILED;
     }
   Print("CORE_VECTOR_SMOKE_PASS vectors=19 mode=inert");
   if(!RunExecutionProjectorSmoke())
      return INIT_FAILED;
   if(!RunGuardedNativeCallbackSmoke())
      return INIT_FAILED;
   if(!RunStateOrderingSmoke())
      return INIT_FAILED;
   if(!RunCoordinatorSmoke())
      return INIT_FAILED;
   if(!RunSafetyRequestSmoke())
      return INIT_FAILED;
   if(!RunPreparedRequestSmoke())
      return INIT_FAILED;
   if(!RunAuditRequestSmoke())
      return INIT_FAILED;
   if(!RunNativeAdapterSmoke())
      return INIT_FAILED;
   if(!RunVisualPayloadSmoke())
      return INIT_FAILED;
   Print("XAUUSD MVP research-only contract baseline initialized.");
   return INIT_SUCCEEDED;
  }

void OnTradeTransaction(const MqlTradeTransaction &transaction,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(!InpObserveNativeOutcomes)
      return;
   XauNativeDealOutcome outcome;
   if(!LoadNativeDealOutcome(transaction,_Symbol,InpStrategyMagic,outcome))
      return;
   if(!PersistThenPublishCorrelatedNativeOutcome(
      g_execution_projections,g_execution_bindings,outcome.event_kind,
      outcome.order_ticket,outcome.position_id,outcome.broker_time,outcome.price,
      EXECUTION_BINDINGS_FILE))
      return;
   Print("Project-owned Native outcome persisted and projected.");
  }

void OnTick()
  {
   if(InpEmitTimeBasisProbe && g_time_basis_probe_count<5)
     {
      MqlTick tick;
      if(SymbolInfoTick(_Symbol,tick))
        {
         PrintFormat("TIME_BASIS_PROBE index=%d server=%s bid=%s",
                     g_time_basis_probe_count+1,
                     TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),
                     DoubleToString(tick.bid,_Digits));
         g_time_basis_probe_count++;
        }
     }
   if(InpRunCurrentEventLoop)
     {
      MqlTick tick;
      if((!SymbolInfoTick(_Symbol,tick) || !ProcessCurrentEventLoopTick(tick)) &&
         !g_event_loop_failure_reported)
        {
         Print("Current event loop failed closed; no trading action is available.");
         g_event_loop_failure_reported=true;
        }
     }
   // The event loop emits state/candidates only; trading remains unavailable.
  }

void OnDeinit(const int reason)
  {
   if(InpRunCurrentEventLoop)
      PrintFormat("CURRENT_EVENT_LOOP_DONE breakout=%I64d reversal=%I64d pullback=%I64d "
                  "failed=%d mode=inert",g_breakout_candidate_count,
                  g_reversal_candidate_count,g_pullback_candidate_count,
                  (int)g_event_loop_failure_reported);
  }
