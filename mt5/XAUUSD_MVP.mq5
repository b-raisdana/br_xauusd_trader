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
#include "include/XauTesterRisk.mqh"
#include "include/XauVisual.mqh"

input bool InpEnableTrading=false;
input bool InpEmitTimeBasisProbe=false;
input bool InpObserveNativeOutcomes=false;
input long InpStrategyMagic=0;
input bool InpRunCurrentEventLoop=false;
input bool InpEnableTesterExecution=false;
input double InpStrategyCapital=200.0;
input bool InpSimulateSameDayRestart=false;

int g_time_basis_probe_count=0;
XauExecutionProjection g_execution_projections[];
XauExecutionBinding g_execution_bindings[];
const string EXECUTION_BINDINGS_FILE="XAUUSD_Current\\bindings.tsv";
const string ORDER_AUDIT_FILE="XAUUSD_Current\\orders.jsonl";
XauMarketCoordinator g_market_state;
datetime g_current_bar_time=0;
bool g_event_loop_ready=false;
bool g_event_loop_failure_reported=false;
long g_breakout_candidate_count=0;
long g_reversal_candidate_count=0;
long g_pullback_candidate_count=0;
long g_tester_attempt_count=0;
long g_tester_accept_count=0;
long g_tester_reject_count=0;
long g_request_sequence=0;
long g_event_sequence=0;
bool g_daily_loss_locked=false;
bool g_operational_lock=false;
long g_session_cancel_count=0;
long g_session_close_count=0;
bool g_session_zero_exposure=false;
bool g_restart_lock=false;
int g_max_open_positions=0;
long g_gate_rejections[8];
double g_final_net_realized=0.0;
double g_final_gross_loss=0.0;
long g_invalid_price_rejections=0;
long g_other_broker_rejections=0;
long g_protection_modifies=0;
long g_protection_modify_rejects=0;
long g_sl_loosen_violations=0;
long g_tp_extensions=0;
long g_tp_restores=0;
long g_tp_market_closes=0;
long g_tp_modify_rejects=0;
long g_tp_close_rejects=0;
long g_breakout_conflict_closes=0;
bool g_symbol_spec_emitted=false;
long g_attribution_attempts[6];
long g_attribution_accepts[6];
long g_attribution_rejects[6];

struct XauRuntimeRequest
  {
   string request_id;
   XauSignalCandidate candidate;
   string target_zone_id;
   XauPreZoneTriggerState trigger_state;
   XauPullbackTpState tp_state;
   bool tp_initialized;
  };

XauRuntimeRequest g_runtime_requests[];

bool NearlyEqual(const double left,const double right)
  {
   return MathAbs(left-right) <= PARITY_PRICE_TOLERANCE;
  }

bool EmitTesterSymbolSpecification(const MqlTick &tick)
  {
   if(!InpEnableTesterExecution || g_symbol_spec_emitted)
      return true;
   long digits=0,stops_level=0,freeze_level=0;
   double point=0.0,contract_size=0.0,tick_size=0.0,tick_value=0.0;
   double volume_min=0.0,volume_step=0.0;
   datetime session_from=0,session_to=0;
   if(!SymbolInfoInteger(_Symbol,SYMBOL_DIGITS,digits) ||
      !SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL,stops_level) ||
      !SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL,freeze_level) ||
      !SymbolInfoDouble(_Symbol,SYMBOL_POINT,point) ||
      !SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE,contract_size) ||
      !SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE,tick_size) ||
      !SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE,tick_value) ||
      !SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN,volume_min) ||
      !SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP,volume_step) ||
      !NativeContainingTradeSession(_Symbol,tick.time,session_from,session_to) ||
      digits < 0 || stops_level < 0 || freeze_level < 0 || point <= 0.0 ||
      contract_size <= 0.0 || tick_size <= 0.0 || tick_value <= 0.0 ||
      volume_min <= 0.0 || volume_step <= 0.0)
      return false;
   PrintFormat("TESTER_SYMBOL_SPEC digits=%d point=%s contract=%s tick_size=%s "
               "tick_value=%s stops=%d freeze=%d volume_min=%s volume_step=%s "
               "session_from=%s session_to=%s mode=tester",
               (int)digits,DoubleToString(point,(int)digits),DoubleToString(contract_size,2),
               DoubleToString(tick_size,(int)digits),DoubleToString(tick_value,2),
               (int)stops_level,(int)freeze_level,DoubleToString(volume_min,2),
               DoubleToString(volume_step,2),TimeToString(session_from,TIME_DATE|TIME_SECONDS),
               TimeToString(session_to,TIME_DATE|TIME_SECONDS));
   g_symbol_spec_emitted=true;
   return true;
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
   g_daily_loss_locked=false;
   g_operational_lock=false;
   g_session_zero_exposure=false;
   g_restart_lock=InpSimulateSameDayRestart;
   PrintFormat("CURRENT_EVENT_LOOP_READY zones=%d history_bars=%d mode=inert",
               ArraySize(merged_zones),g_market_state.trend.count);
   return true;
  }

bool AppendRuntimeRequest(const string request_id,const XauPreparedEntry &prepared)
  {
   const int index=ArraySize(g_runtime_requests);
   if(ArrayResize(g_runtime_requests,index+1) != index+1)
      return false;
   g_runtime_requests[index].request_id=request_id;
   g_runtime_requests[index].candidate=prepared.candidate;
   g_runtime_requests[index].target_zone_id=prepared.target_zone_id;
   g_runtime_requests[index].trigger_state.position_id="";
   g_runtime_requests[index].trigger_state.target_zone_id="";
   g_runtime_requests[index].trigger_state.triggered=false;
   g_runtime_requests[index].tp_initialized=false;
   return true;
  }

int FindRuntimeRequest(const string request_id)
  {
   for(int i=0;i<ArraySize(g_runtime_requests);i++)
      if(g_runtime_requests[i].request_id == request_id)
         return i;
   return -1;
  }

int AttributionIndex(const XauSignalFamily family,const int priority)
  {
   const int family_offset=(family == XAU_SIGNAL_BREAKOUT ? 0 :
                            (family == XAU_SIGNAL_REVERSAL ? 2 : 4));
   return family_offset+(priority == 1 ? 1 : 0);
  }

bool ApplyProjectOwnedNativeOutcome(const XauNativeDealOutcome &outcome)
  {
   string request_id="";
   if(!ResolveExecutionRequest(g_execution_bindings,outcome.event_kind,
                               outcome.order_ticket,outcome.position_id,request_id))
     {
      PrintFormat("NATIVE_OUTCOME_FAIL step=resolve kind=%d order=%I64u position=%I64u",
                  (int)outcome.event_kind,outcome.order_ticket,outcome.position_id);
      return false;
     }
   const int existing_index=FindExecutionProjection(g_execution_projections,request_id);
   if(existing_index >= 0 &&
      ((outcome.event_kind == XAU_EXECUTION_FILL &&
        g_execution_projections[existing_index].status == XAU_EXECUTION_FILLED) ||
       (outcome.event_kind == XAU_EXECUTION_CLOSE &&
        g_execution_projections[existing_index].status == XAU_EXECUTION_CLOSED)))
      return true;
   if(!PersistThenPublishCorrelatedNativeOutcome(
         g_execution_projections,g_execution_bindings,outcome.event_kind,
         outcome.order_ticket,outcome.position_id,outcome.broker_time,outcome.price,
         EXECUTION_BINDINGS_FILE))
     {
      PrintFormat("NATIVE_OUTCOME_FAIL step=persist_publish request=%s kind=%d order=%I64u position=%I64u",
                  request_id,(int)outcome.event_kind,outcome.order_ticket,outcome.position_id);
      return false;
     }
   if(outcome.event_kind == XAU_EXECUTION_FILL)
     {
      const int runtime_index=FindRuntimeRequest(request_id);
      if(runtime_index >= 0 &&
         g_runtime_requests[runtime_index].candidate.family == XAU_SIGNAL_PULLBACK)
        {
         const int window_index=FindCoordinatorPullback(
            g_market_state,g_runtime_requests[runtime_index].candidate.zone_id,
            g_runtime_requests[runtime_index].candidate.direction);
         const int zone_index=FindDailyZoneState(
            g_market_state.zones,g_runtime_requests[runtime_index].candidate.zone_id);
         if(zone_index < 0)
           {
            PrintFormat("NATIVE_OUTCOME_FAIL step=pullback_fill request=%s window=%d zone=%d",
                        request_id,window_index,zone_index);
            return false;
           }
         if(window_index < 0 ||
            !RecordPullbackFill(g_market_state.pullbacks[window_index],
                                g_market_state.zones[zone_index]))
           {
            g_market_state.zones[zone_index].pullback_fills++;
            PrintFormat("TESTER_PULLBACK_FILL_RECOVERED request=%s mode=tester",request_id);
           }
         const int target_index=FindDailyZoneState(
            g_market_state.zones,g_runtime_requests[runtime_index].target_zone_id);
         if(target_index < 0 ||
            !InitializePullbackTp(g_runtime_requests[runtime_index].tp_state,
                                  IntegerToString((long)outcome.position_id),
                                  g_runtime_requests[runtime_index].candidate.direction,
                                  g_market_state.zones[target_index].zone))
           {
            PrintFormat("NATIVE_OUTCOME_FAIL step=tp_initialize request=%s",request_id);
            return false;
           }
         g_runtime_requests[runtime_index].tp_initialized=true;
        }
     }
   return true;
  }

bool RecoverTesterPositionBinding(const ulong position_id,const datetime broker_now)
  {
   if(position_id == 0 || !HistorySelect(0,broker_now))
      return false;
   for(int i=0;i<HistoryDealsTotal();i++)
     {
      const ulong deal=HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetString(deal,DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(deal,DEAL_MAGIC) != InpStrategyMagic ||
         (ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID) != position_id ||
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY) != DEAL_ENTRY_IN)
         continue;
      const ulong order_ticket=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
      string request_id="";
      if(!ResolveExecutionOrderTicket(g_execution_bindings,order_ticket,request_id) ||
         !BindExecutionPosition(g_execution_bindings,order_ticket,position_id) ||
         !SaveExecutionBindingsAtomically(EXECUTION_BINDINGS_FILE,g_execution_bindings))
         return false;
      return true;
     }
   return false;
  }

bool ApplyTesterPendingCancellation(const ulong order_ticket,const datetime broker_time)
  {
   string request_id="";
   if(!ResolveExecutionOrderTicket(g_execution_bindings,order_ticket,request_id))
      return false;
   const int projection_index=FindExecutionProjection(g_execution_projections,request_id);
   if(projection_index < 0)
      return false;
   if(g_execution_projections[projection_index].status != XAU_EXECUTION_CANCELLED &&
      !ProjectExecutionOutcome(g_execution_projections[projection_index],
                               XAU_EXECUTION_CANCEL,broker_time))
      return false;
   const int runtime_index=FindRuntimeRequest(request_id);
   if(runtime_index >= 0 &&
      g_runtime_requests[runtime_index].candidate.family == XAU_SIGNAL_PULLBACK)
     {
      const int window_index=FindCoordinatorPullback(
         g_market_state,g_runtime_requests[runtime_index].candidate.zone_id,
         g_runtime_requests[runtime_index].candidate.direction);
      if(window_index < 0)
         return false;
      if(g_market_state.pullbacks[window_index].pending_active &&
         !RecordPullbackPendingRemoved(g_market_state.pullbacks[window_index]))
         return false;
     }
   return true;
  }

bool ExecuteTesterOperationalSafety(const MqlTick &tick)
  {
   if(!InpEnableTesterExecution || g_operational_lock)
      return true;
   datetime session_from=0,session_to=0;
   if(!NativeContainingTradeSession(_Symbol,tick.time,session_from,session_to))
      return false;
   const bool session_active=SessionEndActive(tick.time,session_to);
   if(!session_active && !g_restart_lock)
      return true;
   const XauOperationalSafety actions=EvaluateOperationalSafety(session_active,g_restart_lock);
   if(!actions.locked || !actions.cancel_pending || !actions.close_positions)
      return false;
   ulong cancelled[];
   if(!CancelTesterPendingOrders(true,InpStrategyMagic,_Symbol,cancelled))
      return false;
   for(int i=0;i<ArraySize(cancelled);i++)
      if(!ApplyTesterPendingCancellation(cancelled[i],tick.time))
         return false;
   int closed=0;
   if(!CloseTesterPositions(true,InpStrategyMagic,_Symbol,closed))
      return false;
   XauTesterRiskSnapshot after_flatten;
   MqlDateTime day_parts;
   if(!TimeToStruct(tick.time,day_parts))
      return false;
   day_parts.hour=0;
   day_parts.min=0;
   day_parts.sec=0;
   if(!LoadTesterRiskSnapshot(true,InpStrategyMagic,_Symbol,StructToTime(day_parts),
                              tick.time,after_flatten) ||
      after_flatten.open_positions != 0 || after_flatten.pending_orders != 0)
      return false;
   g_final_net_realized=after_flatten.net_realized_pnl;
   g_final_gross_loss=after_flatten.realized_gross_loss;
   for(int i=0;i<ArraySize(g_market_state.pullbacks);i++)
     {
      g_market_state.pullbacks[i].active=false;
      g_market_state.pullbacks[i].pending_active=false;
     }
   g_session_cancel_count+=ArraySize(cancelled);
   g_session_close_count+=closed;
   g_operational_lock=true;
   g_session_zero_exposure=true;
   if(g_restart_lock)
      PrintFormat("TESTER_RESTART_FLAT cancellations=%d closes=%d broker_day=%s mode=tester",
                  ArraySize(cancelled),closed,g_market_state.broker_day);
   else
      PrintFormat("TESTER_SESSION_FLAT cancellations=%d closes=%d mode=tester",
                  ArraySize(cancelled),closed);
   return true;
  }

bool LoadPullbackStrictDirections(const XauRuntimeRequest &runtime,int &directions[])
  {
   ArrayResize(directions,0);
   const datetime pullback_bar=StringToTime(runtime.candidate.bar_id);
   if(pullback_bar <= 0 || g_current_bar_time < pullback_bar)
      return false;
   const datetime first_closed=pullback_bar+PeriodSeconds(PERIOD_M15);
   if(first_closed >= g_current_bar_time)
      return true;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   const int copied=CopyRates(_Symbol,PERIOD_M15,first_closed,g_current_bar_time-1,rates);
   if(copied < 0 || ArrayResize(directions,copied) != copied)
      return false;
   for(int i=0;i<copied;i++)
      directions[i]=(rates[i].close > rates[i].open ? 1 :
                     (rates[i].close < rates[i].open ? -1 : 0));
   return true;
  }

int AdjacentTargetZoneIndex(const int current_index,const XauDirection direction)
  {
   const int next=(direction == XAU_BUY ? current_index+1 : current_index-1);
   return (next >= 0 && next < ArraySize(g_market_state.zones) ? next : -1);
  }

bool ManageTesterPullbackTp(const MqlTick &tick)
  {
   if(!InpEnableTesterExecution || g_operational_lock)
      return true;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong position_ticket=PositionGetTicket(i);
      if(position_ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol ||
         PositionGetInteger(POSITION_MAGIC) != InpStrategyMagic)
         continue;
      const ulong position_id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      string request_id="";
      if(!ResolveExecutionRequest(g_execution_bindings,XAU_EXECUTION_CLOSE,0,position_id,
                                  request_id) &&
         (!RecoverTesterPositionBinding(position_id,tick.time) ||
          !ResolveExecutionRequest(g_execution_bindings,XAU_EXECUTION_CLOSE,0,position_id,
                                   request_id)))
        { Print("TP_RUNTIME_FAIL step=resolve"); return false; }
      const int runtime_index=FindRuntimeRequest(request_id);
      if(runtime_index < 0 ||
         g_runtime_requests[runtime_index].candidate.family != XAU_SIGNAL_PULLBACK)
         continue;
      const int projection_index=FindExecutionProjection(g_execution_projections,request_id);
      if(projection_index < 0)
        { Print("TP_RUNTIME_FAIL step=projection"); return false; }
      if(!g_runtime_requests[runtime_index].tp_initialized)
        {
         if(g_execution_projections[projection_index].status == XAU_EXECUTION_SUBMITTED)
            continue;
         const int recovery_target_index=FindDailyZoneState(
            g_market_state.zones,g_runtime_requests[runtime_index].target_zone_id);
         if(g_execution_projections[projection_index].status != XAU_EXECUTION_FILLED ||
            recovery_target_index < 0 ||
            !InitializePullbackTp(g_runtime_requests[runtime_index].tp_state,
                                  IntegerToString((long)position_id),
                                  g_runtime_requests[runtime_index].candidate.direction,
                                  g_market_state.zones[recovery_target_index].zone))
           {
            Print("TP_RUNTIME_FAIL step=state_recovery");
            return false;
           }
         g_runtime_requests[runtime_index].tp_initialized=true;
         PrintFormat("TESTER_TP_STATE_RECOVERED position=%I64u mode=tester",position_id);
        }
      const int target_index=FindDailyZoneState(
         g_market_state.zones,
         g_runtime_requests[runtime_index].tp_state.current_target_zone_id);
      if(target_index < 0)
        { Print("TP_RUNTIME_FAIL step=lookup"); return false; }
      int closed_directions[];
      if(!LoadPullbackStrictDirections(g_runtime_requests[runtime_index],closed_directions))
        { Print("TP_RUNTIME_FAIL step=strict_history"); return false; }
      const XauDirection direction=g_runtime_requests[runtime_index].candidate.direction;
      const bool strict_valid=StrictPullbackTrend(direction,closed_directions,
                                                  g_market_state.bar_open,tick.bid,tick.ask);
      const double current_stop=PositionGetDouble(POSITION_SL);
      const double current_tp=PositionGetDouble(POSITION_TP);
      if(!g_runtime_requests[runtime_index].tp_state.extended)
        {
         const double previous_price=(direction == XAU_BUY ? g_market_state.last_bid :
                                                               g_market_state.last_ask);
         const double current_price=(direction == XAU_BUY ? tick.bid : tick.ask);
         if(!PreZoneCrossOnce(g_runtime_requests[runtime_index].trigger_state,
                              IntegerToString((long)position_id),direction,
                              g_market_state.zones[target_index].zone,
                              previous_price,current_price))
            continue;
         const int next_index=AdjacentTargetZoneIndex(target_index,direction);
         double requested_tp=0.0;
         string target_zone_id="";
         if(!ProposePullbackTpExtension(
               g_runtime_requests[runtime_index].tp_state,
               g_market_state.zones[target_index].zone,
               (next_index >= 0 ? g_market_state.zones[next_index].zone :
                                  g_market_state.zones[target_index].zone),
               next_index >= 0,strict_valid,requested_tp,target_zone_id))
            continue;
         bool accepted=false;
         if(!ModifyTesterProtection(true,InpStrategyMagic,_Symbol,position_ticket,
                                    current_stop,requested_tp,accepted) ||
            !ProjectExecutionOutcome(g_execution_projections[projection_index],
                                     (accepted ? XAU_EXECUTION_MODIFY :
                                                 XAU_EXECUTION_MODIFY_REJECT),
                                     tick.time,0.0,current_stop,requested_tp) ||
            !RecordPullbackTpExtension(g_runtime_requests[runtime_index].tp_state,
                                       requested_tp,target_zone_id,accepted))
           { Print("TP_RUNTIME_FAIL step=extend"); return false; }
         if(accepted)
            g_tp_extensions++;
         else
            g_tp_modify_rejects++;
         continue;
        }
      double requested_tp=0.0;
      const XauTpFailureAction action=EvaluatePullbackTpFailure(
         g_runtime_requests[runtime_index].tp_state,strict_valid,tick.bid,tick.ask,
         requested_tp);
      if(action == XAU_TP_NONE)
         continue;
      if(action == XAU_TP_RESTORE)
        {
         bool accepted=false;
         if(!ModifyTesterProtection(true,InpStrategyMagic,_Symbol,position_ticket,
                                    current_stop,requested_tp,accepted) ||
            !ProjectExecutionOutcome(g_execution_projections[projection_index],
                                     (accepted ? XAU_EXECUTION_MODIFY :
                                                 XAU_EXECUTION_MODIFY_REJECT),
                                     tick.time,0.0,current_stop,requested_tp))
           { Print("TP_RUNTIME_FAIL step=restore"); return false; }
         RecordPullbackTpRestore(g_runtime_requests[runtime_index].tp_state,accepted);
         if(accepted)
            g_tp_restores++;
         else
            g_tp_modify_rejects++;
         continue;
        }
      XauTesterSubmission submission;
      if(!CloseTesterPosition(true,InpStrategyMagic,_Symbol,position_ticket,submission) ||
         !submission.attempted)
        { Print("TP_RUNTIME_FAIL step=close_submit"); return false; }
      if(!submission.accepted)
        {
         g_tp_close_rejects++;
         continue;
        }
      g_tp_market_closes++;
      if(submission.deal_ticket != 0)
        {
         XauNativeDealOutcome immediate;
         if(!LoadNativeDealTicketOutcome(submission.deal_ticket,submission.order_ticket,
                                         _Symbol,InpStrategyMagic,immediate) ||
            !ApplyProjectOwnedNativeOutcome(immediate))
           { Print("TP_RUNTIME_FAIL step=close_outcome"); return false; }
        }
     }
   return true;
  }

bool CloseTesterOppositeReversals(const MqlTick &tick,
                                  const XauSignalCandidate &breakouts[])
  {
   if(!InpEnableTesterExecution || g_operational_lock)
      return true;
   for(int b=0;b<ArraySize(breakouts);b++)
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         const ulong ticket=PositionGetTicket(i);
         if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol ||
            PositionGetInteger(POSITION_MAGIC) != InpStrategyMagic)
            continue;
         const ulong position_id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
         string request_id="";
         if(!ResolveExecutionRequest(g_execution_bindings,XAU_EXECUTION_CLOSE,0,
                                     position_id,request_id))
            continue;
         const int runtime_index=FindRuntimeRequest(request_id);
         if(runtime_index < 0 ||
            g_runtime_requests[runtime_index].candidate.family != XAU_SIGNAL_REVERSAL ||
            g_runtime_requests[runtime_index].candidate.zone_id != breakouts[b].zone_id ||
            g_runtime_requests[runtime_index].candidate.direction == breakouts[b].direction)
            continue;
         XauTesterSubmission submission;
         if(!CloseTesterPosition(true,InpStrategyMagic,_Symbol,ticket,submission) ||
            !submission.attempted || !submission.accepted)
            return false;
         g_breakout_conflict_closes++;
         if(submission.deal_ticket != 0)
           {
            XauNativeDealOutcome outcome;
            if(!LoadNativeDealTicketOutcome(submission.deal_ticket,submission.order_ticket,
                                            _Symbol,InpStrategyMagic,outcome) ||
               !ApplyProjectOwnedNativeOutcome(outcome))
               return false;
           }
        }
   return true;
  }

bool ManageTesterProfitProtection(const MqlTick &tick)
  {
   if(!InpEnableTesterExecution || g_operational_lock)
      return true;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong position_ticket=PositionGetTicket(i);
      if(position_ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol ||
         PositionGetInteger(POSITION_MAGIC) != InpStrategyMagic)
         continue;
      const ulong position_id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      string request_id="";
      if(!ResolveExecutionRequest(g_execution_bindings,XAU_EXECUTION_CLOSE,0,position_id,
                                  request_id) &&
         (!RecoverTesterPositionBinding(position_id,tick.time) ||
          !ResolveExecutionRequest(g_execution_bindings,XAU_EXECUTION_CLOSE,0,position_id,
                                   request_id)))
        { Print("PROTECTION_FAIL step=resolve"); return false; }
      const int projection_index=FindExecutionProjection(g_execution_projections,request_id);
      if(projection_index < 0)
        { Print("PROTECTION_FAIL step=projection"); return false; }
      const XauDirection direction=g_execution_projections[projection_index].direction;
      const double entry=PositionGetDouble(POSITION_PRICE_OPEN);
      const double current_stop=PositionGetDouble(POSITION_SL);
      const double current_tp=PositionGetDouble(POSITION_TP);
      double risk_free=0.0,proposed_stop=0.0;
      if(!TesterPositionRiskFree(true,InpStrategyMagic,_Symbol,position_id,direction,entry,
                                 PositionGetDouble(POSITION_VOLUME),tick.time,risk_free))
        { Print("PROTECTION_FAIL step=risk_free"); return false; }
      if(!ProfitProtectionStop(direction,entry,risk_free,tick.bid,tick.ask,current_stop,
                               proposed_stop))
         continue;
      if(!ProtectionModificationValid(direction,entry,current_stop,proposed_stop,current_tp))
        {
         g_sl_loosen_violations++;
         Print("PROTECTION_FAIL step=validation");
         return false;
        }
      bool accepted=false;
      if(!ModifyTesterProtection(true,InpStrategyMagic,_Symbol,position_ticket,
                                 proposed_stop,current_tp,accepted))
        { Print("PROTECTION_FAIL step=submit"); return false; }
      const XauExecutionEvent event_kind=(accepted ? XAU_EXECUTION_MODIFY :
                                          XAU_EXECUTION_MODIFY_REJECT);
      if(!ProjectExecutionOutcome(g_execution_projections[projection_index],event_kind,
                                  tick.time,0.0,proposed_stop,current_tp))
        { Print("PROTECTION_FAIL step=project"); return false; }
      if(accepted)
         g_protection_modifies++;
      else
         g_protection_modify_rejects++;
     }
   return true;
  }

bool ProcessTesterCandidates(const MqlTick &tick,const XauSignalCandidate &candidates[])
  {
   if(!InpEnableTesterExecution || g_operational_lock)
      return true;
   MqlDateTime day_parts;
   if(!TimeToStruct(tick.time,day_parts))
      return false;
   day_parts.hour=0;
   day_parts.min=0;
   day_parts.sec=0;
   const datetime day_start=StructToTime(day_parts);
   for(int i=0;i<ArraySize(candidates);i++)
     {
      if(!CandidateAttemptAvailable(g_market_state,candidates[i]))
         continue;
      XauTesterRiskSnapshot risk;
      if(!LoadTesterRiskSnapshot(true,InpStrategyMagic,_Symbol,day_start,tick.time,risk))
        { Print("TESTER_CANDIDATE_FAIL step=risk_snapshot"); return false; }
      if(risk.open_positions > g_max_open_positions)
         g_max_open_positions=risk.open_positions;
      g_daily_loss_locked=DailyLossLocked(InpStrategyCapital,risk.net_realized_pnl,
                                         g_daily_loss_locked);
      double stop_loss=0.0,take_profit=0.0;
      string stop_zone="",target_zone="";
      XauZone zones[];
      ArrayResize(zones,ArraySize(g_market_state.zones));
      for(int z=0;z<ArraySize(g_market_state.zones);z++)
         zones[z]=g_market_state.zones[z].zone;
      if(!InitialStop(candidates[i].direction,candidates[i].entry_price,zones,
                      stop_loss,stop_zone) ||
         !InitialTarget(candidates[i].direction,candidates[i].entry_price,zones,
                        take_profit,target_zone))
         continue;
      const ENUM_ORDER_TYPE native_type=(candidates[i].direction == XAU_BUY ?
                                         ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      double proposed_risk=0.0,required_margin=0.0;
      if(!NativeCashRisk(native_type,_Symbol,0.01,candidates[i].entry_price,stop_loss,
                          proposed_risk) ||
         !NativeRequiredMargin(native_type,_Symbol,0.01,candidates[i].entry_price,
                                required_margin))
        { Print("TESTER_CANDIDATE_FAIL step=native_measurement"); return false; }
      XauPreparedEntry prepared;
      if(!PrepareCandidateEntry(candidates[i],zones,g_daily_loss_locked,
                                InpStrategyCapital,risk.realized_gross_loss,
                                risk.open_position_risk,risk.pending_order_risk,
                                 risk.open_positions,proposed_risk,required_margin,
                                 risk.free_margin,prepared))
        { Print("TESTER_CANDIDATE_FAIL step=prepare"); return false; }
      if(prepared.decision != XAU_ENTRY_ALLOWED)
        {
         const int rejection_index=(int)prepared.decision;
         if(rejection_index >= 0 && rejection_index < ArraySize(g_gate_rejections))
            g_gate_rejections[rejection_index]++;
         continue;
        }
      const string request_id="REQ-"+IntegerToString((int)++g_request_sequence);
      const string event_id=g_market_state.broker_day+":E"+
                            IntegerToString((int)++g_event_sequence);
      XauOrderAuditEvent audit;
      if(!BuildPreparedOrderAudit(prepared,event_id,request_id,audit) ||
         !AppendOrderThenProject(ORDER_AUDIT_FILE,prepared.decision,audit,
                                 g_execution_projections) ||
         !AppendRuntimeRequest(request_id,prepared))
        {
         PrintFormat("TESTER_CANDIDATE_FAIL step=durable_prepare request=%s",request_id);
         return false;
        }
      XauTesterSubmission submission;
      if(!SubmitTesterPreparedEntry(true,InpStrategyMagic,_Symbol,prepared,submission) ||
         !submission.attempted ||
         !CommitPreparedEntryAttempt(g_market_state,prepared,submission.accepted))
        {
         PrintFormat("TESTER_CANDIDATE_FAIL step=submit_commit request=%s attempted=%d accepted=%d",
                     request_id,(int)submission.attempted,(int)submission.accepted);
         return false;
        }
      g_tester_attempt_count++;
      const int attribution_index=AttributionIndex(
         prepared.candidate.family,g_market_state.zones[FindDailyZoneState(
            g_market_state.zones,prepared.candidate.zone_id)].zone.priority);
      g_attribution_attempts[attribution_index]++;
      if(!submission.accepted)
        {
         g_tester_reject_count++;
         g_attribution_rejects[attribution_index]++;
         if(submission.retcode == TRADE_RETCODE_INVALID_PRICE ||
            submission.retcode == TRADE_RETCODE_INVALID_STOPS)
            g_invalid_price_rejections++;
         else
            g_other_broker_rejections++;
         PrintFormat("TESTER_BROKER_REJECT retcode=%u mode=tester",submission.retcode);
         const int projection_index=FindExecutionProjection(g_execution_projections,request_id);
          if(projection_index < 0 ||
             !ProjectExecutionOutcome(g_execution_projections[projection_index],
                                      XAU_EXECUTION_REJECT,tick.time))
           {
            PrintFormat("TESTER_CANDIDATE_FAIL step=project_reject request=%s",request_id);
            return false;
           }
         continue;
        }
      if(submission.order_ticket == 0 ||
         !BindExecutionOrder(g_execution_bindings,request_id,submission.order_ticket) ||
         !SaveExecutionBindingsAtomically(EXECUTION_BINDINGS_FILE,g_execution_bindings))
        {
         PrintFormat("TESTER_CANDIDATE_FAIL step=bind_order request=%s order=%I64u",
                     request_id,submission.order_ticket);
         return false;
        }
      g_tester_accept_count++;
      g_attribution_accepts[attribution_index]++;
      if(submission.deal_ticket != 0)
        {
         XauNativeDealOutcome immediate;
         if(!LoadNativeDealTicketOutcome(submission.deal_ticket,submission.order_ticket,
                                         _Symbol,InpStrategyMagic,immediate) ||
            !ApplyProjectOwnedNativeOutcome(immediate))
           {
            PrintFormat("TESTER_CANDIDATE_FAIL step=immediate_fill request=%s order=%I64u deal=%I64u",
                        request_id,submission.order_ticket,submission.deal_ticket);
            return false;
           }
        }
     }
   return true;
  }

bool ProcessCurrentEventLoopTick(const MqlTick &tick)
  {
   XauSignalCandidate close_breakouts[];
   const datetime bar_time=iTime(_Symbol,PERIOD_M15,0);
   if(bar_time <= 0)
      return false;
   if(!g_event_loop_ready)
     {
      if(!InitializeCurrentEventLoop(tick,bar_time))
         return false;
     }
   if(!EmitTesterSymbolSpecification(tick))
     {
      Print("CURRENT_EVENT_LOOP_STAGE_FAIL stage=symbol_spec");
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
      const double high=iHigh(_Symbol,PERIOD_M15,1);
      const double low=iLow(_Symbol,PERIOD_M15,1);
      const double close_bid=iClose(_Symbol,PERIOD_M15,1);
      if(!CloseCoordinatorBar(g_market_state,bar_time,high,low,close_bid,close_breakouts))
         return false;
      int pending_cancellations=0;
      const double open_bid=iOpen(_Symbol,PERIOD_M15,0);
      if(!BeginCoordinatorBar(g_market_state,
                              TimeToString(bar_time,TIME_DATE|TIME_MINUTES),open_bid,
                              open_bid+MathMax(0.0,tick.ask-tick.bid),pending_cancellations))
         return false;
      g_current_bar_time=bar_time;
      if(ArraySize(close_breakouts)>0 || pending_cancellations>0)
        {
         g_breakout_candidate_count+=ArraySize(close_breakouts);
         PrintFormat("CURRENT_EVENT_LOOP_CLOSE breakouts=%d cancellations=%d mode=inert",
                     ArraySize(close_breakouts),pending_cancellations);
        }
     }

   if(!ExecuteTesterOperationalSafety(tick))
     {
      Print("CURRENT_EVENT_LOOP_STAGE_FAIL stage=operational_safety");
      return false;
     }
   if(!ManageTesterPullbackTp(tick))
     {
      Print("CURRENT_EVENT_LOOP_STAGE_FAIL stage=pullback_tp");
      return false;
     }
   if(!ManageTesterProfitProtection(tick))
     {
      Print("CURRENT_EVENT_LOOP_STAGE_FAIL stage=profit_protection");
      return false;
     }
   if(!CloseTesterOppositeReversals(tick,close_breakouts))
     {
      Print("CURRENT_EVENT_LOOP_STAGE_FAIL stage=breakout_conflict_close");
      return false;
     }
   if(!ProcessTesterCandidates(tick,close_breakouts))
     {
      Print("CURRENT_EVENT_LOOP_STAGE_FAIL stage=breakout_candidates");
      return false;
     }

   XauSignalCandidate candidates[];
   if(!ProcessCoordinatorTick(g_market_state,tick.time,tick.bid,tick.ask,candidates))
      return false;
   for(int i=0;i<ArraySize(candidates);i++)
      if(candidates[i].family == XAU_SIGNAL_REVERSAL)
         g_reversal_candidate_count++;
      else if(candidates[i].family == XAU_SIGNAL_PULLBACK)
         g_pullback_candidate_count++;
   if(!ProcessTesterCandidates(tick,candidates))
     {
      Print("CURRENT_EVENT_LOOP_STAGE_FAIL stage=tester_candidates");
      return false;
     }
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
      (!(bool)MQLInfoInteger(MQL_TESTER) || InpStrategyMagic<=0 ||
       !InpObserveNativeOutcomes || MaximumPositions(InpStrategyCapital)<0))
     {
      Print("Tester execution requires Strategy Tester and an explicit positive Magic.");
      return INIT_FAILED;
     }
   if(InpSimulateSameDayRestart && !InpEnableTesterExecution)
     {
      Print("Same-day restart simulation is available only in guarded tester execution.");
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
   if(!ApplyProjectOwnedNativeOutcome(outcome))
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
                  "attempts=%I64d accepted=%I64d rejected=%I64d cancellations=%I64d "
                  "session_closes=%I64d session_flattened=%d failed=%d mode=%s",
                  g_breakout_candidate_count,
                  g_reversal_candidate_count,g_pullback_candidate_count,
                  g_tester_attempt_count,g_tester_accept_count,g_tester_reject_count,
                  g_session_cancel_count,g_session_close_count,
                  (int)g_session_zero_exposure,
                  (int)g_event_loop_failure_reported,
                  (InpEnableTesterExecution ? "tester" : "inert"));
   if(InpEnableTesterExecution)
     {
      PrintFormat("TESTER_RISK_DONE net=%.2f gross_loss=%.2f max_positions=%d "
                  "daily_blocks=%I64d gross_blocks=%I64d concurrency_blocks=%I64d "
                  "margin_blocks=%I64d protection_blocks=%I64d space_blocks=%I64d "
                  "initial_blocks=%I64d invalid_price_rejects=%I64d "
                  "other_broker_rejects=%I64d protection_modifies=%I64d "
                  "modify_rejects=%I64d sl_loosen=%I64d mode=tester",
                  g_final_net_realized,g_final_gross_loss,g_max_open_positions,
                  g_gate_rejections[XAU_ENTRY_DAILY_LOSS],
                  g_gate_rejections[XAU_ENTRY_GROSS_RISK],
                  g_gate_rejections[XAU_ENTRY_CONCURRENCY],
                  g_gate_rejections[XAU_ENTRY_MARGIN],
                  g_gate_rejections[XAU_ENTRY_INVALID_PROTECTION],
                  g_gate_rejections[XAU_ENTRY_FREE_SPACE],
                  g_gate_rejections[XAU_ENTRY_INITIAL_RISK],g_invalid_price_rejections,
                  g_other_broker_rejections,g_protection_modifies,
                  g_protection_modify_rejects,g_sl_loosen_violations);
      PrintFormat("TESTER_TP_DONE extensions=%I64d restores=%I64d market_closes=%I64d "
                  "modify_rejects=%I64d close_rejects=%I64d mode=tester",
                  g_tp_extensions,g_tp_restores,g_tp_market_closes,
                  g_tp_modify_rejects,g_tp_close_rejects);
      PrintFormat("TESTER_BREAKOUT_DONE conflict_closes=%I64d mode=tester",
                  g_breakout_conflict_closes);
      PrintFormat("TESTER_ATTRIBUTION bo_normal=%I64d/%I64d/%I64d bo_high=%I64d/%I64d/%I64d "
                  "rev_normal=%I64d/%I64d/%I64d rev_high=%I64d/%I64d/%I64d "
                  "pb_normal=%I64d/%I64d/%I64d pb_high=%I64d/%I64d/%I64d mode=tester",
                  g_attribution_attempts[0],g_attribution_accepts[0],g_attribution_rejects[0],
                  g_attribution_attempts[1],g_attribution_accepts[1],g_attribution_rejects[1],
                  g_attribution_attempts[2],g_attribution_accepts[2],g_attribution_rejects[2],
                  g_attribution_attempts[3],g_attribution_accepts[3],g_attribution_rejects[3],
                  g_attribution_attempts[4],g_attribution_accepts[4],g_attribution_rejects[4],
                  g_attribution_attempts[5],g_attribution_accepts[5],g_attribution_rejects[5]);
     }
  }
