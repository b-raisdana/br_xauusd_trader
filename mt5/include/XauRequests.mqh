#ifndef XAUUSD_MVP_REQUESTS_MQH
#define XAUUSD_MVP_REQUESTS_MQH

struct XauPreparedEntry
  {
   XauSignalCandidate candidate;
   XauEntryRejection decision;
   double volume_lots;
   double stop_loss;
   double take_profit;
   string stop_zone_id;
   string target_zone_id;
  };

bool EntryBarAvailable(const string &attempted_bars[],const string bar_id)
  {
   for(int i=0;i<ArraySize(attempted_bars);i++)
      if(attempted_bars[i] == bar_id)
         return false;
   return bar_id != "";
  }

bool CandidateAttemptAvailable(const XauMarketCoordinator &state,
                               const XauSignalCandidate &candidate)
  {
   if(!EntryBarAvailable(state.attempted_bars,candidate.bar_id))
      return false;
   const int zone_index=FindDailyZoneState(state.zones,candidate.zone_id);
   if(zone_index < 0)
      return false;
   if(candidate.family == XAU_SIGNAL_BREAKOUT)
      return true;
   if(candidate.family == XAU_SIGNAL_REVERSAL)
     {
      const int limit=(state.zones[zone_index].zone.priority == 1 ? 2 : 1);
      return state.zones[zone_index].reversal_usage < limit;
     }
   if(candidate.family == XAU_SIGNAL_PULLBACK)
     {
      const int window_index=FindCoordinatorPullback(state,candidate.zone_id,
                                                     candidate.direction);
      return window_index >= 0 && state.pullbacks[window_index].active &&
             !state.pullbacks[window_index].pending_active &&
             PullbackUsageAllowed(state.zones[zone_index].zone.priority,
                                  state.zones[zone_index].pullback_fills);
     }
   return false;
  }

bool PrepareCandidateEntry(const XauSignalCandidate &candidate,const XauZone &zones[],
                           const bool daily_locked,const double strategy_capital,
                           const double realized_gross_loss,const double open_risk,
                           const double pending_risk,const int open_positions,
                           const double native_cash_risk,const double required_margin,
                           const double free_margin,XauPreparedEntry &prepared)
  {
   prepared.candidate=candidate;
   prepared.volume_lots=0.01;
   prepared.stop_loss=0.0;
   prepared.take_profit=0.0;
   prepared.stop_zone_id="";
   prepared.target_zone_id="";
   if(candidate.family != XAU_SIGNAL_BREAKOUT &&
      candidate.family != XAU_SIGNAL_REVERSAL && candidate.family != XAU_SIGNAL_PULLBACK)
     {
      prepared.decision=XAU_ENTRY_INITIAL_RISK;
      return false;
     }
   if(!HasMinimumFreeSpace(candidate.zone_id,candidate.direction,zones))
     {
      prepared.decision=XAU_ENTRY_FREE_SPACE;
      return true;
     }
   if(!InitialStop(candidate.direction,candidate.entry_price,zones,prepared.stop_loss,
                   prepared.stop_zone_id) ||
      !InitialTarget(candidate.direction,candidate.entry_price,zones,prepared.take_profit,
                     prepared.target_zone_id))
     {
      prepared.decision=XAU_ENTRY_INITIAL_RISK;
      return true;
     }
   const bool portfolio_allowed=PortfolioRiskAllows(
      strategy_capital,realized_gross_loss,open_risk,pending_risk,native_cash_risk);
   prepared.decision=EvaluateProtectedEntry(
      daily_locked,portfolio_allowed,ConcurrencyAllowsEntry(strategy_capital,open_positions),
      NativeMarginAllowsEntry(required_margin,free_margin),candidate.direction,
      candidate.entry_price,prepared.stop_loss,prepared.take_profit,prepared.volume_lots);
   return true;
  }

bool BuildPreparedOrderAudit(const XauPreparedEntry &prepared,const string event_id,
                             const string request_id,XauOrderAuditEvent &event)
  {
   if(prepared.decision != XAU_ENTRY_ALLOWED || event_id == "" || request_id == "")
      return false;
   event.event_id=event_id;
   event.request_id=request_id;
   event.zone_id=prepared.candidate.zone_id;
   event.rule_ids=(prepared.candidate.family == XAU_SIGNAL_BREAKOUT ?
                   "BREAKOUT_VALIDATION,ZONE_ENGAGEMENT" :
                   (prepared.candidate.family == XAU_SIGNAL_REVERSAL ?
                    "REVERSAL_DIRECTIONAL_TOUCH" : "PULLBACK_CONSERVATIVE"));
   event.direction=prepared.candidate.direction;
   event.order_type=prepared.candidate.order_type;
   event.broker_time=prepared.candidate.signal_time;
   event.entry=prepared.candidate.entry_price;
   event.stop_loss=prepared.stop_loss;
   event.take_profit=prepared.take_profit;
   return true;
  }

bool CommitPreparedEntryAttempt(XauMarketCoordinator &state,
                                const XauPreparedEntry &prepared,
                                const bool broker_accepted)
  {
   if(prepared.decision != XAU_ENTRY_ALLOWED)
      return false;
   const int zone_index=FindDailyZoneState(state.zones,prepared.candidate.zone_id);
   if(zone_index < 0)
      return false;
   if(prepared.candidate.family == XAU_SIGNAL_BREAKOUT)
      return RecordEntryAttempt(state.attempted_bars,prepared.candidate.bar_id);
   if(prepared.candidate.family == XAU_SIGNAL_REVERSAL)
     {
      const int limit=(state.zones[zone_index].zone.priority == 1 ? 2 : 1);
      if(state.zones[zone_index].reversal_usage >= limit ||
         !RecordEntryAttempt(state.attempted_bars,prepared.candidate.bar_id))
         return false;
      state.zones[zone_index].reversal_usage++;
      return true;
     }
   if(prepared.candidate.family == XAU_SIGNAL_PULLBACK)
     {
      const int window_index=FindCoordinatorPullback(
         state,prepared.candidate.zone_id,prepared.candidate.direction);
      if(window_index < 0)
         return false;
      return RecordPullbackAttempt(state.pullbacks[window_index],state.attempted_bars,
                                   prepared.candidate.bar_id,broker_accepted);
     }
   return false;
  }

#endif
