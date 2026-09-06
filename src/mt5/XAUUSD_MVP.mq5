#property strict
#property version "1.000"
#property description "Research-only XAUUSD MVP contract baseline"

#include "generated/CoreVectors.mqh"
#include "include/XauContracts.mqh"
#include "include/XauNative.mqh"

input bool InpEnableTrading=false;

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
   return RestartSameDayLocked(VEC_RESTART_DAY,VEC_RESTART_LAST_DAY);
  }

bool RunNativeAdapterSmoke()
  {
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
   Print("NATIVE_ADAPTER_SMOKE_PASS symbol/session/risk/margin mode=read-only");
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
   Print("CORE_VECTOR_SMOKE_PASS vectors=16 mode=inert");
   if(!RunNativeAdapterSmoke())
      return INIT_FAILED;
   Print("XAUUSD MVP research-only contract baseline initialized.");
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   // Intentionally inert until current adapters pass parity and live gates.
  }
