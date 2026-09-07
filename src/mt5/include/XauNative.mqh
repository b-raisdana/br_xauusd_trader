#ifndef XAU_NATIVE_MQH
#define XAU_NATIVE_MQH

// Read-only boundary around broker-native symbol, risk, margin, and session APIs.
// It deliberately contains no order-send, position mutation, or account identity calls.

struct XauNativeSymbol
  {
   int digits;
   double point;
   double volume_min;
   double volume_max;
   double volume_step;
  };

struct XauNativeDealOutcome
  {
   ulong deal_ticket;
   ulong order_ticket;
   ulong position_id;
   XauExecutionEvent event_kind;
   double price;
   datetime broker_time;
  };

bool ClassifyNativeDealEntry(const ENUM_DEAL_ENTRY entry,XauExecutionEvent &event_kind)
  {
   if(entry == DEAL_ENTRY_IN)
     {
      event_kind=XAU_EXECUTION_FILL;
      return true;
     }
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      event_kind=XAU_EXECUTION_CLOSE;
      return true;
     }
   // INOUT is compound and cannot safely project to one lifecycle event.
   return false;
  }

bool LoadNativeDealOutcome(const MqlTradeTransaction &transaction,const string expected_symbol,
                           const long expected_magic,XauNativeDealOutcome &outcome)
  {
   if(expected_symbol == "" || expected_magic <= 0 ||
      transaction.type != TRADE_TRANSACTION_DEAL_ADD || transaction.deal == 0 ||
      transaction.symbol != expected_symbol)
      return false;
   if(!HistoryDealSelect(transaction.deal) ||
      HistoryDealGetInteger(transaction.deal,DEAL_MAGIC) != expected_magic)
      return false;

   XauExecutionEvent event_kind=XAU_EXECUTION_REJECT;
   ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(transaction.deal,DEAL_ENTRY);
   if(!ClassifyNativeDealEntry(entry,event_kind))
      return false;
   const double deal_price=HistoryDealGetDouble(transaction.deal,DEAL_PRICE);
   const long deal_time=HistoryDealGetInteger(transaction.deal,DEAL_TIME);
   if(deal_price <= 0.0 || deal_time <= 0)
      return false;

   outcome.deal_ticket=transaction.deal;
   outcome.order_ticket=transaction.order;
   outcome.position_id=(ulong)HistoryDealGetInteger(transaction.deal,DEAL_POSITION_ID);
   outcome.event_kind=event_kind;
   outcome.price=deal_price;
   outcome.broker_time=(datetime)deal_time;
   return outcome.position_id != 0;
  }

bool LoadNativeSymbol(const string symbol,XauNativeSymbol &result)
  {
   long digits=0;
   double point=0.0,volume_min=0.0,volume_max=0.0,volume_step=0.0;
   if(!SymbolInfoInteger(symbol,SYMBOL_DIGITS,digits) ||
      !SymbolInfoDouble(symbol,SYMBOL_POINT,point) ||
      !SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN,volume_min) ||
      !SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX,volume_max) ||
      !SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP,volume_step))
      return false;
   if(digits<0 || point<=0.0 || volume_min<=0.0 ||
      volume_max<volume_min || volume_step<=0.0)
      return false;
   result.digits=(int)digits;
   result.point=point;
   result.volume_min=volume_min;
   result.volume_max=volume_max;
   result.volume_step=volume_step;
   return true;
  }

bool NativeCashRisk(const ENUM_ORDER_TYPE order_type,const string symbol,
                    const double volume,const double entry,const double stop,
                    double &cash_risk)
  {
   cash_risk=0.0;
   if(volume<=0.0 || entry<=0.0 || stop<=0.0 || entry==stop)
      return false;
   double profit=0.0;
   if(!OrderCalcProfit(order_type,symbol,volume,entry,stop,profit))
      return false;
   cash_risk=MathAbs(profit);
   return cash_risk>0.0;
  }

bool NativeRequiredMargin(const ENUM_ORDER_TYPE order_type,const string symbol,
                          const double volume,const double entry,double &margin)
  {
   margin=0.0;
   if(volume<=0.0 || entry<=0.0)
      return false;
   if(!OrderCalcMargin(order_type,symbol,volume,entry,margin))
      return false;
   return margin>=0.0;
  }

int NativeSecondsOfDay(const datetime value)
  {
   MqlDateTime parts;
   if(!TimeToStruct(value,parts))
      return -1;
   return parts.hour*3600+parts.min*60+parts.sec;
  }

bool NativeContainingTradeSession(const string symbol,const datetime broker_now,
                                  datetime &session_from,datetime &session_to)
  {
   session_from=0;
   session_to=0;
   MqlDateTime now_parts;
   if(!TimeToStruct(broker_now,now_parts))
      return false;
   now_parts.hour=0;
   now_parts.min=0;
   now_parts.sec=0;
   datetime today=StructToTime(now_parts);

   // The prior day's final session may cross midnight into broker_now.
   for(int day_offset=-1;day_offset<=0;day_offset++)
     {
      datetime day_start=today+day_offset*86400;
      MqlDateTime day_parts;
      if(!TimeToStruct(day_start,day_parts))
         continue;
      ENUM_DAY_OF_WEEK weekday=(ENUM_DAY_OF_WEEK)day_parts.day_of_week;
      for(uint index=0;index<32;index++)
        {
         datetime raw_from=0,raw_to=0;
         if(!SymbolInfoSessionTrade(symbol,weekday,index,raw_from,raw_to))
            break;
         int from_seconds=NativeSecondsOfDay(raw_from);
         int to_seconds=NativeSecondsOfDay(raw_to);
         if(from_seconds<0 || to_seconds<0)
            return false;
         datetime absolute_from=day_start+from_seconds;
         datetime absolute_to=day_start+to_seconds;
         if(to_seconds<=from_seconds)
            absolute_to+=86400;
         if(broker_now>=absolute_from && broker_now<absolute_to)
           {
            session_from=absolute_from;
            session_to=absolute_to;
            return true;
           }
        }
     }
   return false;
  }

#endif
