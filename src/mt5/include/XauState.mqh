#ifndef XAUUSD_MVP_STATE_MQH
#define XAUUSD_MVP_STATE_MQH

struct XauTrendReferenceState
  {
   XauTrend trend;
   int count;
   double highs[3];
   double lows[3];
  };

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
