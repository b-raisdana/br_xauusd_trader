#ifndef XAUUSD_MVP_STATE_MQH
#define XAUUSD_MVP_STATE_MQH

struct XauTrendReferenceState
  {
   XauTrend trend;
   int count;
   double highs[3];
   double lows[3];
  };

struct XauDailyZoneSignalState
  {
   XauZone zone;
   bool buy_engaged;
   bool sell_engaged;
   int reversal_usage;
   int pullback_fills;
  };

struct XauPullbackWindowState
  {
   string parent_breakout_id;
   XauZone zone;
   XauDirection direction;
   int bar_offset;
   bool active;
   bool penetration_latched;
   bool pending_active;
   int sequence;
  };

struct XauPreZoneTriggerState
  {
   string position_id;
   string target_zone_id;
   bool triggered;
  };

struct XauPullbackTpState
  {
   string position_id;
   XauDirection direction;
   string initial_target_zone_id;
   double initial_tp;
   string current_target_zone_id;
   double current_tp;
   bool extended;
  };

bool PreZoneCrossOnce(XauPreZoneTriggerState &state,const string position_id,
                      const XauDirection direction,const XauZone &target_zone,
                      const double previous_price,const double current_price)
  {
   if(position_id == "" || target_zone.id == "")
      return false;
   if(state.position_id != position_id || state.target_zone_id != target_zone.id)
     {
      state.position_id=position_id;
      state.target_zone_id=target_zone.id;
      state.triggered=false;
     }
   if(state.triggered ||
      !PreZoneCrossed(direction,target_zone,previous_price,current_price))
      return false;
   state.triggered=true;
   return true;
  }

bool InitializePullbackTp(XauPullbackTpState &state,const string position_id,
                          const XauDirection direction,const XauZone &initial_target)
  {
   if(position_id == "" || initial_target.id == "")
      return false;
   const double target=(direction == XAU_BUY ? initial_target.low : initial_target.high);
   state.position_id=position_id;
   state.direction=direction;
   state.initial_target_zone_id=initial_target.id;
   state.initial_tp=target;
   state.current_target_zone_id=initial_target.id;
   state.current_tp=target;
   state.extended=false;
   return true;
  }

bool ProposePullbackTpExtension(const XauPullbackTpState &state,
                                const XauZone &approached_zone,const XauZone &next_zone,
                                const bool has_next_zone,const bool strict_valid,
                                double &requested_tp,string &target_zone_id)
  {
   requested_tp=0.0;
   target_zone_id="";
   if(state.extended || !strict_valid || !has_next_zone ||
      approached_zone.id != state.initial_target_zone_id)
      return false;
   requested_tp=(state.direction == XAU_BUY ? next_zone.low : next_zone.high);
   target_zone_id=next_zone.id;
   return target_zone_id != "";
  }

bool RecordPullbackTpExtension(XauPullbackTpState &state,const double requested_tp,
                               const string target_zone_id,const bool broker_accepted)
  {
   if(requested_tp <= 0.0 || target_zone_id == "")
      return false;
   if(broker_accepted)
     {
      state.current_tp=requested_tp;
      state.current_target_zone_id=target_zone_id;
      state.extended=true;
     }
   return true;
  }

XauTpFailureAction EvaluatePullbackTpFailure(const XauPullbackTpState &state,
                                             const bool strict_valid,
                                             const double current_bid,
                                             const double current_ask,double &requested_tp)
  {
   requested_tp=0.0;
   const XauTpFailureAction action=PullbackTpFailureAction(
      state.direction,state.extended,strict_valid,state.initial_tp,current_bid,current_ask);
   if(action == XAU_TP_RESTORE)
      requested_tp=state.initial_tp;
   return action;
  }

void RecordPullbackTpRestore(XauPullbackTpState &state,const bool broker_accepted)
  {
   if(broker_accepted)
     {
      state.current_tp=state.initial_tp;
      state.current_target_zone_id=state.initial_target_zone_id;
      state.extended=false;
     }
  }

bool CreatePullbackWindow(XauPullbackWindowState &window,const string parent_breakout_id,
                          const XauZone &zone,const XauDirection direction)
  {
   if(parent_breakout_id == "" || zone.id == "" || zone.low > zone.high)
      return false;
   window.parent_breakout_id=parent_breakout_id;
   window.zone=zone;
   window.direction=direction;
   window.bar_offset=0;
   window.active=true;
   window.penetration_latched=false;
   window.pending_active=false;
   window.sequence=0;
   return true;
  }

bool BeginPullbackBar(XauPullbackWindowState &window,bool &pending_must_cancel)
  {
   pending_must_cancel=false;
   if(!window.active)
      return false;
   window.bar_offset++;
   if(!PullbackWindowActive(window.bar_offset))
     {
      pending_must_cancel=window.pending_active;
      window.pending_active=false;
      window.active=false;
     }
   return true;
  }

bool EvaluatePullbackPrice(XauPullbackWindowState &window,const int daily_fills,
                           const double bid,string &candidate_id,double &entry_price)
  {
   candidate_id="";
   entry_price=0.0;
   if(!window.active || !PullbackWindowActive(window.bar_offset) || window.pending_active ||
      !PullbackUsageAllowed(window.zone.priority,daily_fills))
      return false;
   if(!window.penetration_latched)
     {
      if(window.direction == XAU_BUY)
         window.penetration_latched=bid <= window.zone.high-PULLBACK_PENETRATION_USD;
      else
         window.penetration_latched=bid >= window.zone.low+PULLBACK_PENETRATION_USD;
     }
   if(!window.penetration_latched)
      return false;
   window.sequence++;
   candidate_id=window.parent_breakout_id+":PB"+IntegerToString(window.sequence);
   entry_price=(window.direction == XAU_BUY ? window.zone.high : window.zone.low);
   return true;
  }

bool RecordPullbackAttempt(XauPullbackWindowState &window,string &attempted_bars[],
                           const string bar_id,const bool broker_accepted)
  {
   if(!window.active || window.pending_active || !RecordEntryAttempt(attempted_bars,bar_id))
      return false;
   if(broker_accepted)
      window.pending_active=true;
   return true;
  }

bool RecordPullbackFill(XauPullbackWindowState &window,XauDailyZoneSignalState &zone_state)
  {
   if(!window.active || !window.pending_active || window.zone.id != zone_state.zone.id)
      return false;
   zone_state.pullback_fills++;
   window.pending_active=false;
   window.penetration_latched=false;
   return true;
  }

bool RecordPullbackPendingRemoved(XauPullbackWindowState &window)
  {
   if(!window.active || !window.pending_active)
      return false;
   window.pending_active=false;
   return true;
  }

bool InitializeDailyZoneStates(const XauZone &zones[],XauDailyZoneSignalState &states[])
  {
   ArrayResize(states,ArraySize(zones));
   for(int i=0;i<ArraySize(zones);i++)
     {
      if(zones[i].id == "" || zones[i].low > zones[i].high)
         return false;
      states[i].zone=zones[i];
      states[i].buy_engaged=false;
      states[i].sell_engaged=false;
      states[i].reversal_usage=0;
      states[i].pullback_fills=0;
     }
   return true;
  }

int FindDailyZoneState(const XauDailyZoneSignalState &states[],const string zone_id)
  {
   for(int i=0;i<ArraySize(states);i++)
      if(states[i].zone.id == zone_id)
         return i;
   return -1;
  }

void BeginSignalBar(XauDailyZoneSignalState &states[],const double open_bid)
  {
   for(int i=0;i<ArraySize(states);i++)
     {
      const bool inside=open_bid >= states[i].zone.low && open_bid <= states[i].zone.high;
      states[i].buy_engaged=inside;
      states[i].sell_engaged=inside;
     }
  }

bool UpdateZoneEngagement(XauDailyZoneSignalState &states[],const double previous_bid,
                          const double current_bid,bool &multi_zone_tick_gap)
  {
   XauZone zones[];
   ArrayResize(zones,ArraySize(states));
   for(int i=0;i<ArraySize(states);i++)
      zones[i]=states[i].zone;
   multi_zone_tick_gap=CountDirectionalCrosses(zones,previous_bid,current_bid) > 1;
   for(int i=0;i<ArraySize(states);i++)
     {
      if(multi_zone_tick_gap)
        {
         const bool inside=current_bid >= states[i].zone.low && current_bid <= states[i].zone.high;
         if(inside)
           {
            states[i].buy_engaged=true;
            states[i].sell_engaged=true;
           }
         continue;
        }
      if(!states[i].buy_engaged && previous_bid < states[i].zone.low &&
         current_bid >= states[i].zone.low)
         states[i].buy_engaged=true;
      if(!states[i].sell_engaged && previous_bid > states[i].zone.high &&
         current_bid <= states[i].zone.high)
         states[i].sell_engaged=true;
     }
   return true;
  }

string NextBreakoutId(int &daily_sequence)
  {
   daily_sequence++;
   return "BO"+IntegerToString(daily_sequence);
  }

bool ConsumeReversalUsage(XauDailyZoneSignalState &state)
  {
   const int limit=(state.zone.priority == 1 ? 2 : 1);
   if(state.reversal_usage >= limit)
      return false;
   state.reversal_usage++;
   return true;
  }

bool RecordEntryAttempt(string &attempted_bars[],const string bar_id)
  {
   if(bar_id == "")
      return false;
   for(int i=0;i<ArraySize(attempted_bars);i++)
      if(attempted_bars[i] == bar_id)
         return false;
   const int index=ArraySize(attempted_bars);
   if(ArrayResize(attempted_bars,index+1) != index+1)
      return false;
   attempted_bars[index]=bar_id;
   return true;
  }

void BeginTrendDay(XauTrendReferenceState &state)
  {
   state.trend=XAU_TREND_NONE;
   state.count=0;
   ArrayInitialize(state.highs,0.0);
   ArrayInitialize(state.lows,0.0);
  }

bool RecordTrendCandle(XauTrendReferenceState &state,const double high,const double low)
  {
   if(high < low)
      return false;
   if(state.count < 3)
     {
      state.highs[state.count]=high;
      state.lows[state.count]=low;
      state.count++;
      return true;
     }
   state.highs[0]=state.highs[1]; state.highs[1]=state.highs[2]; state.highs[2]=high;
   state.lows[0]=state.lows[1]; state.lows[1]=state.lows[2]; state.lows[2]=low;
   return true;
  }

bool TrendReferences(const XauTrendReferenceState &state,double &reference_high,
                     double &reference_low)
  {
   if(state.count <= 0)
      return false;
   reference_high=state.highs[0];
   reference_low=state.lows[0];
   for(int i=1;i<state.count;i++)
     {
      reference_high=MathMax(reference_high,state.highs[i]);
      reference_low=MathMin(reference_low,state.lows[i]);
     }
   return true;
  }

XauTrend ProcessTrendTick(XauTrendReferenceState &state,const double bid)
  {
   double reference_high=0.0,reference_low=0.0;
   if(TrendReferences(state,reference_high,reference_low))
      state.trend=UpdateTrend(state.trend,state.count,reference_high,reference_low,bid);
   return state.trend;
  }

bool CloseBarBreakoutBeforeRoll(XauTrendReferenceState &state,const XauZone &zone,
                                const XauDirection direction,const double close_price,
                                const bool engaged,const double candle_high,
                                const double candle_low,bool &breakout)
  {
   if(candle_high < MathMax(close_price,candle_low) || candle_low > close_price)
      return false;
   breakout=BreakoutValid(zone,direction,state.trend,close_price,engaged);
   return RecordTrendCandle(state,candle_high,candle_low);
  }

#endif
