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

enum XauExecutionStatus
  {
   XAU_EXECUTION_SUBMITTED = 0,
   XAU_EXECUTION_FILLED = 1,
   XAU_EXECUTION_REJECTED = 2,
   XAU_EXECUTION_CLOSED = 3,
   XAU_EXECUTION_CANCELLED = 4
  };

enum XauExecutionEvent
  {
   XAU_EXECUTION_FILL = 0,
   XAU_EXECUTION_REJECT = 1,
   XAU_EXECUTION_CLOSE = 2,
   XAU_EXECUTION_MODIFY = 3,
   XAU_EXECUTION_MODIFY_REJECT = 4,
   XAU_EXECUTION_CANCEL = 5,
   XAU_EXECUTION_CANCEL_REJECT = 6
  };

enum XauOrderType
  {
   XAU_ORDER_MARKET = 0,
   XAU_ORDER_PENDING_STOP = 1
  };

enum XauSignalFamily
  {
   XAU_SIGNAL_BREAKOUT = 0,
   XAU_SIGNAL_REVERSAL = 1,
   XAU_SIGNAL_PULLBACK = 2
  };

enum XauEntryRejection
  {
   XAU_ENTRY_ALLOWED = 0,
   XAU_ENTRY_DAILY_LOSS = 1,
   XAU_ENTRY_GROSS_RISK = 2,
   XAU_ENTRY_CONCURRENCY = 3,
   XAU_ENTRY_MARGIN = 4,
   XAU_ENTRY_INVALID_PROTECTION = 5
  };

struct XauOperationalSafety
  {
   bool locked;
   bool block_entries;
   bool cancel_pending;
   bool cancel_pullback_cycles;
   bool close_positions;
  };

struct XauZone
  {
   string id;
   double low;
   double high;
   int priority; // 0=Normal, 1=High
  };

enum XauTpFailureAction
  {
   XAU_TP_NONE = 0,
   XAU_TP_RESTORE = 1,
   XAU_TP_MARKET_CLOSE = 2
  };

int BuildMergedZones(const XauZone &raw_zones[],const string broker_day,XauZone &merged[])
  {
   const int count=ArraySize(raw_zones);
   XauZone sorted[];
   ArrayResize(sorted,count);
   for(int i=0;i<count;i++)
     {
      sorted[i]=raw_zones[i];
      if(sorted[i].low > sorted[i].high)
        {
         const double swap=sorted[i].low;
         sorted[i].low=sorted[i].high;
         sorted[i].high=swap;
        }
     }
   for(int i=1;i<count;i++)
     {
      XauZone value=sorted[i];
      int position=i-1;
      while(position >= 0 &&
            (sorted[position].low > value.low ||
             (sorted[position].low == value.low && sorted[position].high > value.high)))
        {
         sorted[position+1]=sorted[position];
         position--;
        }
      sorted[position+1]=value;
     }

   ArrayResize(merged,0);
   int merged_count=0;
   for(int i=0;i<count;i++)
     {
      if(merged_count == 0 || sorted[i].low-merged[merged_count-1].high >= 1.5)
        {
         ArrayResize(merged,merged_count+1);
         merged[merged_count]=sorted[i];
         merged[merged_count].id=broker_day+":R"+IntegerToString(merged_count+1);
         merged_count++;
        }
      else
        {
         merged[merged_count-1].low=MathMin(merged[merged_count-1].low,sorted[i].low);
         merged[merged_count-1].high=MathMax(merged[merged_count-1].high,sorted[i].high);
         merged[merged_count-1].priority=MathMax(merged[merged_count-1].priority,
                                                  sorted[i].priority);
        }
     }
   return merged_count;
  }

int CountDirectionalCrosses(const XauZone &zones[],const double previous_bid,
                            const double current_bid)
  {
   int crosses=0;
   for(int i=0;i<ArraySize(zones);i++)
      if((previous_bid < zones[i].low && current_bid >= zones[i].low) ||
         (previous_bid > zones[i].high && current_bid <= zones[i].high))
         crosses++;
   return crosses;
  }

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

bool CausalTrendThenReversal(const XauZone &zone,const XauDirection direction,
                             const XauTrend current_trend,const int reference_count,
                             const double reference_high,const double reference_low,
                             const double previous_bid,const double current_bid,
                             XauTrend &updated_trend)
  {
   updated_trend=UpdateTrend(current_trend,reference_count,reference_high,reference_low,
                             current_bid);
   return ReversalDirectionalTouch(zone,direction,updated_trend,previous_bid,current_bid,false);
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

bool PullbackWindowActive(const int bar_offset)
  {
   return bar_offset >= 1 && bar_offset <= 5;
  }

bool PullbackUsageAllowed(const int zone_priority,const int daily_fills)
  {
   if(daily_fills < 0)
      return false;
   return zone_priority == 1 || daily_fills < 1;
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

bool BlocksOppositeReversal(const bool actual_zone_touch,const bool strict_trend_valid)
  {
   return actual_zone_touch && strict_trend_valid;
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

int MaximumPositions(const double strategy_capital)
  {
   if(MathAbs(strategy_capital-200.0) <= PARITY_PRICE_TOLERANCE)
      return 3;
   if(MathAbs(strategy_capital-300.0) <= PARITY_PRICE_TOLERANCE)
      return 5;
   return -1;
  }

bool ConcurrencyAllowsEntry(const double strategy_capital,const int open_positions)
  {
   const int maximum=MaximumPositions(strategy_capital);
   return maximum >= 0 && open_positions >= 0 && open_positions < maximum;
  }

bool NativeMarginAllowsEntry(const double required_margin,const double free_margin)
  {
   return required_margin >= 0.0 && free_margin >= 0.0 && required_margin <= free_margin;
  }

XauEntryRejection EvaluateProtectedEntry(const bool daily_locked,
                                         const bool portfolio_allowed,
                                         const bool concurrency_allowed,
                                         const bool margin_allowed,
                                         const XauDirection direction,const double entry,
                                         const double stop_loss,const double take_profit,
                                         const double volume_lots)
  {
   if(daily_locked)
      return XAU_ENTRY_DAILY_LOSS;
   if(!portfolio_allowed)
      return XAU_ENTRY_GROSS_RISK;
   if(!concurrency_allowed)
      return XAU_ENTRY_CONCURRENCY;
   if(!margin_allowed)
      return XAU_ENTRY_MARGIN;
   const bool protected_order=(direction == XAU_BUY ? stop_loss < entry && entry < take_profit
                                                    : take_profit < entry && entry < stop_loss);
   if(!protected_order || MathAbs(volume_lots-0.01) > PARITY_PRICE_TOLERANCE)
      return XAU_ENTRY_INVALID_PROTECTION;
   return XAU_ENTRY_ALLOWED;
  }

XauOperationalSafety EvaluateOperationalSafety(const bool session_active,
                                                const bool same_day_restart)
  {
   XauOperationalSafety actions;
   actions.locked=session_active || same_day_restart;
   actions.block_entries=actions.locked;
   actions.cancel_pending=actions.locked;
   actions.cancel_pullback_cycles=actions.locked;
   actions.close_positions=actions.locked;
   return actions;
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

XauTpFailureAction PullbackTpFailureAction(const XauDirection direction,
                                           const bool extended,const bool strict_valid,
                                           const double initial_tp,const double current_bid,
                                           const double current_ask)
  {
   if(!extended || strict_valid)
      return XAU_TP_NONE;
   const bool crossed=(direction == XAU_BUY ? current_bid >= initial_tp
                                            : current_ask <= initial_tp);
   return (crossed ? XAU_TP_MARKET_CLOSE : XAU_TP_RESTORE);
  }

bool RestartSameDayLocked(const string broker_day,const string persisted_last_activation_day)
  {
   return broker_day != "" && broker_day == persisted_last_activation_day;
  }

bool ExecutionTransition(const XauExecutionStatus status,const XauExecutionEvent event_kind,
                         const XauOrderType order_type,XauExecutionStatus &next_status)
  {
   if(status == XAU_EXECUTION_SUBMITTED && event_kind == XAU_EXECUTION_FILL)
      next_status=XAU_EXECUTION_FILLED;
   else if(status == XAU_EXECUTION_SUBMITTED && event_kind == XAU_EXECUTION_REJECT)
      next_status=XAU_EXECUTION_REJECTED;
   else if(status == XAU_EXECUTION_FILLED && event_kind == XAU_EXECUTION_CLOSE)
      next_status=XAU_EXECUTION_CLOSED;
   else if(status == XAU_EXECUTION_FILLED &&
           (event_kind == XAU_EXECUTION_MODIFY || event_kind == XAU_EXECUTION_MODIFY_REJECT))
      next_status=XAU_EXECUTION_FILLED;
   else if(status == XAU_EXECUTION_SUBMITTED && event_kind == XAU_EXECUTION_CANCEL_REJECT)
      next_status=XAU_EXECUTION_SUBMITTED;
   else if(status == XAU_EXECUTION_SUBMITTED && event_kind == XAU_EXECUTION_CANCEL &&
           order_type == XAU_ORDER_PENDING_STOP)
      next_status=XAU_EXECUTION_CANCELLED;
   else
      return false;
   return true;
  }

bool ProtectionModificationValid(const XauDirection direction,const double entry,
                                 const double current_stop,const double proposed_stop,
                                 const double proposed_tp)
  {
   if(direction == XAU_BUY)
      return proposed_stop >= current_stop && proposed_stop < proposed_tp && proposed_tp > entry;
   return proposed_stop <= current_stop && proposed_tp < proposed_stop && proposed_tp < entry;
  }

#endif
