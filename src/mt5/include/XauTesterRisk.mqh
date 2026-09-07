#ifndef XAUUSD_MVP_TESTER_RISK_MQH
#define XAUUSD_MVP_TESTER_RISK_MQH

struct XauTesterRiskSnapshot
  {
   double net_realized_pnl;
   double realized_gross_loss;
   double open_position_risk;
   double pending_order_risk;
   double free_margin;
   int open_positions;
   int pending_orders;
  };

int FindRiskPosition(const ulong &position_ids[],const ulong position_id)
  {
   for(int i=0;i<ArraySize(position_ids);i++)
      if(position_ids[i] == position_id)
         return i;
   return -1;
  }

bool LoadTesterRealizedRisk(const long magic,const string symbol,const datetime day_start,
                            const datetime broker_now,double &net_realized,
                            double &gross_loss)
  {
   net_realized=0.0;
   gross_loss=0.0;
   if(!HistorySelect(day_start,broker_now))
      return false;
   ulong position_ids[];
   double position_pnl[];
   bool position_closed[];
   for(int i=0;i<HistoryDealsTotal();i++)
     {
      const ulong deal=HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetString(deal,DEAL_SYMBOL) != symbol ||
         HistoryDealGetInteger(deal,DEAL_MAGIC) != magic)
         continue;
      const ulong position_id=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
      if(position_id == 0)
         continue;
      int index=FindRiskPosition(position_ids,position_id);
      if(index < 0)
        {
         index=ArraySize(position_ids);
         if(ArrayResize(position_ids,index+1) != index+1 ||
            ArrayResize(position_pnl,index+1) != index+1 ||
            ArrayResize(position_closed,index+1) != index+1)
            return false;
         position_ids[index]=position_id;
         position_pnl[index]=0.0;
         position_closed[index]=false;
        }
      position_pnl[index]+=HistoryDealGetDouble(deal,DEAL_PROFIT)+
                           HistoryDealGetDouble(deal,DEAL_SWAP)+
                           HistoryDealGetDouble(deal,DEAL_COMMISSION)+
                           HistoryDealGetDouble(deal,DEAL_FEE);
      const ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
         position_closed[index]=true;
     }
   for(int i=0;i<ArraySize(position_ids);i++)
      if(position_closed[i])
        {
         net_realized+=position_pnl[i];
         if(position_pnl[i] < 0.0)
            gross_loss-=position_pnl[i];
        }
   return true;
  }

bool LoadTesterExposureRisk(const long magic,const string symbol,
                            XauTesterRiskSnapshot &snapshot)
  {
   snapshot.open_position_risk=0.0;
   snapshot.pending_order_risk=0.0;
   snapshot.open_positions=0;
   snapshot.pending_orders=0;
   for(int i=0;i<PositionsTotal();i++)
     {
      const ulong ticket=PositionGetTicket(i);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != symbol ||
         PositionGetInteger(POSITION_MAGIC) != magic)
         continue;
      const double entry=PositionGetDouble(POSITION_PRICE_OPEN);
      const double stop=PositionGetDouble(POSITION_SL);
      const double volume=PositionGetDouble(POSITION_VOLUME);
      const ENUM_POSITION_TYPE position_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
       const ENUM_ORDER_TYPE order_type=(position_type == POSITION_TYPE_BUY ? ORDER_TYPE_BUY :
                                         ORDER_TYPE_SELL);
       double risk=0.0;
       if(stop <= 0.0)
          return false;
       const bool protected_stop=(position_type == POSITION_TYPE_BUY ? stop >= entry :
                                                                    stop <= entry);
       if(!protected_stop && !NativeCashRisk(order_type,symbol,volume,entry,stop,risk))
          return false;
       snapshot.open_position_risk+=risk;
      snapshot.open_positions++;
     }
   for(int i=0;i<OrdersTotal();i++)
     {
      const ulong ticket=OrderGetTicket(i);
      if(ticket == 0 || OrderGetString(ORDER_SYMBOL) != symbol ||
         OrderGetInteger(ORDER_MAGIC) != magic)
         continue;
      const ENUM_ORDER_TYPE order_type=(ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(order_type != ORDER_TYPE_BUY_STOP && order_type != ORDER_TYPE_SELL_STOP)
         continue;
      double risk=0.0;
      if(!NativeCashRisk(order_type,symbol,OrderGetDouble(ORDER_VOLUME_CURRENT),
                         OrderGetDouble(ORDER_PRICE_OPEN),OrderGetDouble(ORDER_SL),risk))
         return false;
      snapshot.pending_order_risk+=risk;
      snapshot.pending_orders++;
     }
   return true;
  }

bool LoadTesterRiskSnapshot(const bool enabled,const long magic,const string symbol,
                            const datetime day_start,const datetime broker_now,
                            XauTesterRiskSnapshot &snapshot)
  {
   if(!TesterExecutionAllowed(enabled) || magic <= 0 || symbol == "" ||
      day_start <= 0 || broker_now < day_start)
      return false;
   if(!LoadTesterRealizedRisk(magic,symbol,day_start,broker_now,
                              snapshot.net_realized_pnl,snapshot.realized_gross_loss) ||
      !LoadTesterExposureRisk(magic,symbol,snapshot))
      return false;
   snapshot.free_margin=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   return snapshot.free_margin >= 0.0;
  }

bool TesterPositionRiskFree(const bool enabled,const long magic,const string symbol,
                            const ulong position_id,const XauDirection direction,
                            const double entry,const double volume,const datetime broker_now,
                            double &risk_free)
  {
   risk_free=0.0;
   if(!TesterExecutionAllowed(enabled) || position_id == 0 || entry <= 0.0 || volume <= 0.0 ||
      !HistorySelect(0,broker_now))
      return false;
   double native_cost=0.0;
   for(int i=0;i<HistoryDealsTotal();i++)
     {
      const ulong deal=HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetString(deal,DEAL_SYMBOL) != symbol ||
         HistoryDealGetInteger(deal,DEAL_MAGIC) != magic ||
         (ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID) != position_id)
         continue;
      native_cost-=HistoryDealGetDouble(deal,DEAL_COMMISSION)+
                   HistoryDealGetDouble(deal,DEAL_FEE)+HistoryDealGetDouble(deal,DEAL_SWAP);
     }
   native_cost=MathMax(native_cost,0.0);
   double cash_per_unit=0.0;
   const ENUM_ORDER_TYPE order_type=(direction == XAU_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   const double unit_exit=(direction == XAU_BUY ? entry+1.0 : entry-1.0);
   if(!OrderCalcProfit(order_type,symbol,volume,entry,unit_exit,cash_per_unit) ||
      MathAbs(cash_per_unit) <= 0.0)
      return false;
   const double offset=native_cost/MathAbs(cash_per_unit);
   risk_free=(direction == XAU_BUY ? entry+offset : entry-offset);
   return true;
  }

#endif
