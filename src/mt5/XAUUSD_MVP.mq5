#property strict
#property version "1.000"
#property description "Research-only XAUUSD MVP contract baseline"

#include "generated/CoreVectors.mqh"
#include "include/XauContracts.mqh"
#include "include/XauExecution.mqh"
#include "include/XauNative.mqh"
#include "include/XauVisual.mqh"

input bool InpEnableTrading=false;
input bool InpEmitTimeBasisProbe=false;

int g_time_basis_probe_count=0;

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
   Print("EXECUTION_PROJECTOR_SMOKE_PASS lifecycle/protection/correlation mode=inert");
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

int OnInit()
  {
   if(InpEnableTrading)
     {
      Print("Live/trading execution is not implemented or approved; initialization blocked.");
      return INIT_FAILED;
     }
   if(!RunCoreVectorSmoke())
     {
      Print("Core contract vector smoke failed.");
      return INIT_FAILED;
     }
   Print("CORE_VECTOR_SMOKE_PASS vectors=18 mode=inert");
   if(!RunExecutionProjectorSmoke())
      return INIT_FAILED;
   if(!RunNativeAdapterSmoke())
      return INIT_FAILED;
   if(!RunVisualPayloadSmoke())
      return INIT_FAILED;
   Print("XAUUSD MVP research-only contract baseline initialized.");
   return INIT_SUCCEEDED;
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
   // Intentionally inert until current adapters pass parity and live gates.
  }
