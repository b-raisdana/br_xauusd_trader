#ifndef XAUUSD_MVP_CONTRACTS_MQH
#define XAUUSD_MVP_CONTRACTS_MQH

const double BASE_R_USD = 6.0;
const double BREAKOUT_BUFFER_USD = 1.0;
const double GROSS_DAILY_RISK_FRACTION = 0.15;

enum XauDirection
  {
   XAU_BUY = 0,
   XAU_SELL = 1
  };

enum XauTrend
  {
   XAU_TREND_NONE = 0,
   XAU_TREND_UP = 1,
   XAU_TREND_DOWN = 2
  };

struct XauZone
  {
   string id;
   double low;
   double high;
  };

bool BreakoutValid(const XauZone &zone,const XauDirection direction,const XauTrend trend,
                   const double close_price,const bool engaged)
  {
   if(!engaged)
      return false;
   if(direction == XAU_BUY)
      return trend == XAU_TREND_UP && close_price > zone.high + BREAKOUT_BUFFER_USD;
   return trend == XAU_TREND_DOWN && close_price < zone.low - BREAKOUT_BUFFER_USD;
  }

bool ReversalDirectionalTouch(const XauZone &zone,const XauDirection direction,
                              const XauTrend trend,const double previous_bid,
                              const double current_bid,const bool multi_zone_tick_gap)
  {
   if(multi_zone_tick_gap)
      return false;
   if(direction == XAU_SELL)
      return trend == XAU_TREND_UP && previous_bid < zone.low && current_bid >= zone.low;
   return trend == XAU_TREND_DOWN && previous_bid > zone.high && current_bid <= zone.high;
  }

bool InitialStop(const XauDirection direction,const double entry,const XauZone &zones[],
                 double &stop_loss,string &stop_zone_id)
  {
   bool found=false;
   double nearest=0.0;
   for(int i=0;i<ArraySize(zones);i++)
     {
      if(direction == XAU_BUY && zones[i].high < entry && (!found || zones[i].high > nearest))
        {
         found=true;
         nearest=zones[i].high;
         stop_zone_id=zones[i].id;
        }
      if(direction == XAU_SELL && zones[i].low > entry && (!found || zones[i].low < nearest))
        {
         found=true;
         nearest=zones[i].low;
         stop_zone_id=zones[i].id;
        }
     }
   if(!found)
      return false;
   stop_loss=(direction == XAU_BUY ? MathMax(nearest,entry-BASE_R_USD)
                                   : MathMin(nearest,entry+BASE_R_USD));
   return true;
  }

bool InitialTarget(const XauDirection direction,const double entry,const XauZone &zones[],
                   double &take_profit,string &target_zone_id)
  {
   bool found=false;
   double nearest=0.0;
   for(int i=0;i<ArraySize(zones);i++)
     {
      if(direction == XAU_BUY && zones[i].low > entry && zones[i].low-entry >= BASE_R_USD &&
         (!found || zones[i].low < nearest))
        {
         found=true;
         nearest=zones[i].low;
         target_zone_id=zones[i].id;
        }
      if(direction == XAU_SELL && zones[i].high < entry && entry-zones[i].high >= BASE_R_USD &&
         (!found || zones[i].high > nearest))
        {
         found=true;
         nearest=zones[i].high;
         target_zone_id=zones[i].id;
        }
     }
   if(!found)
      return false;
   take_profit=nearest;
   return true;
  }

bool PortfolioRiskAllows(const double strategy_capital,const double realized_gross_loss,
                         const double open_risk,const double pending_risk,
                         const double proposed_risk)
  {
   if(strategy_capital <= 0.0 || realized_gross_loss < 0.0 || open_risk < 0.0 ||
      pending_risk < 0.0 || proposed_risk < 0.0)
      return false;
   const double budget=strategy_capital*GROSS_DAILY_RISK_FRACTION;
   return realized_gross_loss+open_risk+pending_risk+proposed_risk <= budget+1e-9;
  }

#endif
