#ifndef XAUUSD_MVP_COORDINATOR_MQH
#define XAUUSD_MVP_COORDINATOR_MQH

struct XauSignalCandidate
  {
   string candidate_id;
   string parent_breakout_id;
   string bar_id;
   string zone_id;
   XauSignalFamily family;
   XauDirection direction;
   XauOrderType order_type;
   datetime signal_time;
   double entry_price;
  };

struct XauMarketCoordinator
  {
   string broker_day;
   string bar_id;
   bool day_active;
   bool bar_active;
   double bar_open;
   double last_bid;
   double last_ask;
   int breakout_sequence;
   XauTrendReferenceState trend;
   XauDailyZoneSignalState zones[];
   XauPullbackWindowState pullbacks[];
   string reversal_keys[];
   string attempted_bars[];
  };

bool AppendSignalCandidate(XauSignalCandidate &candidates[],const string candidate_id,
                           const string parent_breakout_id,const string bar_id,
                           const string zone_id,const XauSignalFamily family,
                           const XauDirection direction,const XauOrderType order_type,
                           const datetime signal_time,const double entry_price)
  {
   if(candidate_id == "" || bar_id == "" || zone_id == "" || signal_time <= 0 ||
      entry_price <= 0.0)
      return false;
   const int index=ArraySize(candidates);
   if(ArrayResize(candidates,index+1) != index+1)
      return false;
   candidates[index].candidate_id=candidate_id;
   candidates[index].parent_breakout_id=parent_breakout_id;
   candidates[index].bar_id=bar_id;
   candidates[index].zone_id=zone_id;
   candidates[index].family=family;
   candidates[index].direction=direction;
   candidates[index].order_type=order_type;
   candidates[index].signal_time=signal_time;
   candidates[index].entry_price=entry_price;
   return true;
  }

bool RecordUniqueText(string &values[],const string value)
  {
   if(value == "")
      return false;
   for(int i=0;i<ArraySize(values);i++)
      if(values[i] == value)
         return false;
   const int index=ArraySize(values);
   if(ArrayResize(values,index+1) != index+1)
      return false;
   values[index]=value;
   return true;
  }

int FindCoordinatorPullback(const XauMarketCoordinator &state,const string zone_id,
                            const XauDirection direction)
  {
   for(int i=0;i<ArraySize(state.pullbacks);i++)
      if(state.pullbacks[i].zone.id == zone_id && state.pullbacks[i].direction == direction)
         return i;
   return -1;
  }

bool BeginCoordinatorDay(XauMarketCoordinator &state,const string broker_day,
                         const XauZone &zones[])
  {
   if(broker_day == "" || ArraySize(zones) == 0 ||
      !InitializeDailyZoneStates(zones,state.zones))
      return false;
   state.broker_day=broker_day;
   state.bar_id="";
   state.day_active=true;
   state.bar_active=false;
   state.bar_open=0.0;
   state.last_bid=0.0;
   state.last_ask=0.0;
   state.breakout_sequence=0;
   ArrayResize(state.pullbacks,0);
   ArrayResize(state.reversal_keys,0);
   ArrayResize(state.attempted_bars,0);
   BeginTrendDay(state.trend);
   return true;
  }

bool BeginCoordinatorBar(XauMarketCoordinator &state,const string bar_id,
                         const double open_bid,const double open_ask,int &pending_cancellations)
  {
   pending_cancellations=0;
   if(!state.day_active || state.bar_active || bar_id == "" || open_bid <= 0.0 ||
      open_ask < open_bid)
      return false;
   for(int i=0;i<ArraySize(state.pullbacks);i++)
     {
      if(!state.pullbacks[i].active)
         continue;
      bool pending_must_cancel=false;
      if(!BeginPullbackBar(state.pullbacks[i],pending_must_cancel))
         return false;
      if(pending_must_cancel)
         pending_cancellations++;
     }
   BeginSignalBar(state.zones,open_bid);
   state.bar_id=bar_id;
   state.bar_active=true;
   state.bar_open=open_bid;
   state.last_bid=open_bid;
   state.last_ask=open_ask;
   return true;
  }

bool ProcessCoordinatorTick(XauMarketCoordinator &state,const datetime tick_time,
                            const double bid,const double ask,XauSignalCandidate &candidates[])
  {
   ArrayResize(candidates,0);
   if(!state.bar_active || tick_time <= 0 || bid <= 0.0 || ask < bid)
      return false;
   const double previous_bid=state.last_bid;
   ProcessTrendTick(state.trend,bid);
   bool multi_zone_gap=false;
   if(!UpdateZoneEngagement(state.zones,previous_bid,bid,multi_zone_gap))
      return false;

   for(int i=0;i<ArraySize(state.zones);i++)
     {
      for(int side=0;side<2;side++)
        {
         const XauDirection direction=(XauDirection)side;
         if(!ReversalDirectionalTouch(state.zones[i].zone,direction,state.trend.trend,
                                      previous_bid,bid,multi_zone_gap))
            continue;
         const string key=state.bar_id+":R:"+state.zones[i].zone.id+":"+
                          IntegerToString(side);
         if(!RecordUniqueText(state.reversal_keys,key))
            continue;
         if(!AppendSignalCandidate(candidates,key,"",state.bar_id,state.zones[i].zone.id,
                                   XAU_SIGNAL_REVERSAL,direction,XAU_ORDER_MARKET,
                                   tick_time,bid))
            return false;
        }
     }

   for(int i=0;i<ArraySize(state.pullbacks);i++)
     {
      const int zone_index=FindDailyZoneState(state.zones,state.pullbacks[i].zone.id);
      if(zone_index < 0)
         return false;
      string candidate_id="";
      double entry_price=0.0;
      if(EvaluatePullbackPrice(state.pullbacks[i],state.zones[zone_index].pullback_fills,
                               bid,candidate_id,entry_price) &&
         !AppendSignalCandidate(candidates,candidate_id,
                                state.pullbacks[i].parent_breakout_id,state.bar_id,
                                state.pullbacks[i].zone.id,XAU_SIGNAL_PULLBACK,
                                state.pullbacks[i].direction,XAU_ORDER_PENDING_STOP,
                                tick_time,entry_price))
         return false;
     }
   state.last_bid=bid;
   state.last_ask=ask;
   return true;
  }

bool CloseCoordinatorBar(XauMarketCoordinator &state,const datetime close_time,
                         const double high,const double low,const double close_bid,
                         XauSignalCandidate &breakouts[])
  {
   ArrayResize(breakouts,0);
   if(!state.bar_active || close_time <= 0 || high < MathMax(close_bid,low) ||
      low > close_bid || MathAbs(close_bid-state.last_bid) > PARITY_PRICE_TOLERANCE)
      return false;
   for(int i=0;i<ArraySize(state.zones);i++)
     {
      for(int side=0;side<2;side++)
        {
         const XauDirection direction=(XauDirection)side;
         const bool engaged=(direction == XAU_BUY ? state.zones[i].buy_engaged :
                             state.zones[i].sell_engaged);
         if(!BreakoutValid(state.zones[i].zone,direction,state.trend.trend,close_bid,engaged))
            continue;
         const string breakout_id=NextBreakoutId(state.breakout_sequence);
         if(!AppendSignalCandidate(breakouts,breakout_id,"",state.bar_id,
                                   state.zones[i].zone.id,XAU_SIGNAL_BREAKOUT,direction,
                                   XAU_ORDER_MARKET,close_time,close_bid))
            return false;
         int window_index=FindCoordinatorPullback(state,state.zones[i].zone.id,direction);
         if(window_index >= 0 && state.pullbacks[window_index].active)
            continue;
         if(window_index < 0)
           {
            window_index=ArraySize(state.pullbacks);
            if(ArrayResize(state.pullbacks,window_index+1) != window_index+1)
               return false;
           }
         if(!CreatePullbackWindow(state.pullbacks[window_index],breakout_id,
                                  state.zones[i].zone,direction))
            return false;
        }
     }
   if(!RecordTrendCandle(state.trend,high,low))
      return false;
   state.bar_active=false;
   state.bar_id="";
   return true;
  }

#endif
