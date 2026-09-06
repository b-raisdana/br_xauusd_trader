#property strict
#property version "1.000"
#property description "Research-only XAUUSD MVP contract baseline"

#include "generated/CoreVectors.mqh"
#include "include/XauContracts.mqh"

input bool InpEnableTrading=false;

bool NearlyEqual(const double left,const double right)
  {
   return MathAbs(left-right) <= 1e-9;
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
   return PortfolioRiskAllows(VEC_PORTFOLIO_CAPITAL,VEC_PORTFOLIO_REALIZED,
                              VEC_PORTFOLIO_OPEN,VEC_PORTFOLIO_PENDING,
                              VEC_PORTFOLIO_PROPOSED);
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
   Print("XAUUSD MVP research-only contract baseline initialized.");
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   // Intentionally inert until current adapters pass parity and live gates.
  }
