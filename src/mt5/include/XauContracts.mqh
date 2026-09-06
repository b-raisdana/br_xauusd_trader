#ifndef XAUUSD_MVP_CONTRACTS_MQH
#define XAUUSD_MVP_CONTRACTS_MQH

const double BASE_R_USD = 6.0;
const double BREAKOUT_BUFFER_USD = 1.0;
const double GROSS_DAILY_RISK_FRACTION = 0.15;
const double PULLBACK_PENETRATION_USD = 0.20;
const double PRE_ZONE_TRIGGER_DISTANCE_USD = 1.0;
const double DAILY_REALIZED_LOSS_FRACTION = 0.20;
const double PARITY_PRICE_TOLERANCE = 1e-9;

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

XauTrend UpdateTrend(const XauTrend current_state,const int reference_count,
                     const double reference_high,const double reference_low,const double bid)
  {
   if(reference_count <= 0)
      return current_state;
   if(bid > reference_high)
      return XAU_TREND_UP;
   if(bid < reference_low)
      return XAU_TREND_DOWN;
   return current_state;
  }

bool PullbackPenetrated(const XauZone &zone,const XauDirection direction,const double bid,
                        double &entry_price)
  {
   entry_price=(direction == XAU_BUY ? zone.high : zone.low);
   if(direction == XAU_BUY)
      return bid <= zone.high-PULLBACK_PENETRATION_USD;
   return bid >= zone.low+PULLBACK_PENETRATION_USD;
  }

bool StrictPullbackTrend(const XauDirection direction,const int &closed_directions[],
                         const double current_open,const double current_bid,
                         const double current_ask)
  {
   const int required=(direction == XAU_BUY ? 1 : -1);
   for(int i=0;i<ArraySize(closed_directions);i++)
      if(closed_directions[i] != required)
         return false;
   return (direction == XAU_BUY ? current_bid > current_open : current_ask < current_open);
  }

double PreZoneTriggerPrice(const XauDirection direction,const XauZone &target_zone)
  {
   return (direction == XAU_BUY ? target_zone.low-PRE_ZONE_TRIGGER_DISTANCE_USD
                                : target_zone.high+PRE_ZONE_TRIGGER_DISTANCE_USD);
  }

bool PreZoneCrossed(const XauDirection direction,const XauZone &target_zone,
                    const double previous_price,const double current_price)
  {
   const double trigger=PreZoneTriggerPrice(direction,target_zone);
   if(direction == XAU_BUY)
      return previous_price < trigger && current_price >= trigger;
   return previous_price > trigger && current_price <= trigger;
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

bool ProfitProtectionStop(const XauDirection direction,const double entry,
                          const double risk_free,const double current_bid,
                          const double current_ask,const double current_stop,
                          double &proposed_stop)
  {
   const double favorable=(direction == XAU_BUY ? current_bid-entry : entry-current_ask);
   const int step=(int)MathFloor(favorable/BASE_R_USD);
   if(step < 1)
      return false;
   proposed_stop=(direction == XAU_BUY ? risk_free+(step-1)*BASE_R_USD
                                       : risk_free-(step-1)*BASE_R_USD);
   return (direction == XAU_BUY ? proposed_stop > current_stop : proposed_stop < current_stop);
  }

bool DailyLossLocked(const double strategy_capital,const double net_realized_pnl,
                     const bool previously_locked)
  {
   if(previously_locked)
      return true;
   if(strategy_capital <= 0.0 || strategy_capital >= 300.0)
      return false;
   return net_realized_pnl <= -strategy_capital*DAILY_REALIZED_LOSS_FRACTION;
  }

bool SessionEndActive(const datetime broker_now,const datetime broker_session_end)
  {
   return broker_now >= broker_session_end-5*60;
  }

#endif
