#ifndef XAUUSD_MVP_TESTER_BROKER_MQH
#define XAUUSD_MVP_TESTER_BROKER_MQH

struct XauTesterSubmission
  {
   bool attempted;
   bool accepted;
   ulong order_ticket;
   ulong deal_ticket;
   uint retcode;
  };

bool TesterExecutionAllowed(const bool enabled)
  {
   return enabled && (bool)MQLInfoInteger(MQL_TESTER);
  }

ENUM_ORDER_TYPE_FILLING NativeFillingPolicy(const string symbol)
  {
   const long flags=SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE);
   if((flags & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return ORDER_FILLING_FOK;
   if((flags & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
  }

bool TesterRetcodeAccepted(const uint retcode)
  {
   return retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_PLACED ||
          retcode == TRADE_RETCODE_DONE_PARTIAL;
  }

bool SubmitTesterPreparedEntry(const bool enabled,const long magic,const string symbol,
                               const XauPreparedEntry &prepared,
                               XauTesterSubmission &submission)
  {
   submission.attempted=false;
   submission.accepted=false;
   submission.order_ticket=0;
   submission.deal_ticket=0;
   submission.retcode=0;
   if(!TesterExecutionAllowed(enabled) || magic <= 0 || symbol == "" ||
      prepared.decision != XAU_ENTRY_ALLOWED)
      return false;

   MqlTick tick;
   if(!SymbolInfoTick(symbol,tick))
      return false;
   MqlTradeRequest request={};
   MqlTradeResult result={};
   request.action=(prepared.candidate.order_type == XAU_ORDER_MARKET ?
                   TRADE_ACTION_DEAL : TRADE_ACTION_PENDING);
   request.symbol=symbol;
   request.magic=(ulong)magic;
   request.volume=prepared.volume_lots;
   request.type_time=ORDER_TIME_GTC;
   request.type_filling=NativeFillingPolicy(symbol);
   request.sl=prepared.stop_loss;
   request.tp=prepared.take_profit;
   request.comment="XAUUSD_MVP";
   if(prepared.candidate.order_type == XAU_ORDER_MARKET)
     {
      request.type=(prepared.candidate.direction == XAU_BUY ? ORDER_TYPE_BUY :
                    ORDER_TYPE_SELL);
      request.price=(prepared.candidate.direction == XAU_BUY ? tick.ask : tick.bid);
      request.deviation=20;
     }
   else
     {
      request.type=(prepared.candidate.direction == XAU_BUY ? ORDER_TYPE_BUY_STOP :
                    ORDER_TYPE_SELL_STOP);
      request.price=prepared.candidate.entry_price;
     }

   submission.attempted=true;
   const bool sent=OrderSend(request,result);
   submission.retcode=result.retcode;
   submission.order_ticket=result.order;
   submission.deal_ticket=result.deal;
   submission.accepted=sent && TesterRetcodeAccepted(result.retcode);
   return true;
  }

bool CancelTesterPendingOrders(const bool enabled,const long magic,const string symbol,
                               ulong &cancelled_tickets[])
  {
   ArrayResize(cancelled_tickets,0);
   if(!TesterExecutionAllowed(enabled) || magic <= 0 || symbol == "")
      return false;
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      const ulong ticket=OrderGetTicket(i);
      if(ticket == 0 || OrderGetString(ORDER_SYMBOL) != symbol ||
         OrderGetInteger(ORDER_MAGIC) != magic)
         continue;
      MqlTradeRequest request={};
      MqlTradeResult result={};
      request.action=TRADE_ACTION_REMOVE;
      request.order=ticket;
      request.symbol=symbol;
      request.magic=(ulong)magic;
      if(!OrderSend(request,result) || !TesterRetcodeAccepted(result.retcode))
         return false;
      const int index=ArraySize(cancelled_tickets);
      if(ArrayResize(cancelled_tickets,index+1) != index+1)
         return false;
      cancelled_tickets[index]=ticket;
     }
   return true;
  }

bool CloseTesterPositions(const bool enabled,const long magic,const string symbol,
                          int &closed_positions)
  {
   closed_positions=0;
   if(!TesterExecutionAllowed(enabled) || magic <= 0 || symbol == "")
      return false;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong ticket=PositionGetTicket(i);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != symbol ||
         PositionGetInteger(POSITION_MAGIC) != magic)
         continue;
      MqlTick tick;
      if(!SymbolInfoTick(symbol,tick))
         return false;
      const ENUM_POSITION_TYPE position_type=
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      MqlTradeRequest request={};
      MqlTradeResult result={};
      request.action=TRADE_ACTION_DEAL;
      request.position=ticket;
      request.symbol=symbol;
      request.magic=(ulong)magic;
      request.volume=PositionGetDouble(POSITION_VOLUME);
      request.type=(position_type == POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY);
      request.price=(position_type == POSITION_TYPE_BUY ? tick.bid : tick.ask);
      request.deviation=20;
      request.type_filling=NativeFillingPolicy(symbol);
      request.comment="XAUUSD_FLAT";
      if(!OrderSend(request,result) || !TesterRetcodeAccepted(result.retcode))
         return false;
      closed_positions++;
     }
   return true;
  }

bool ModifyTesterProtection(const bool enabled,const long magic,const string symbol,
                            const ulong position_ticket,const double stop_loss,
                            const double take_profit,bool &accepted)
  {
   accepted=false;
   if(!TesterExecutionAllowed(enabled) || magic <= 0 || symbol == "" ||
      position_ticket == 0 || stop_loss <= 0.0 || take_profit <= 0.0)
      return false;
   MqlTradeRequest request={};
   MqlTradeResult result={};
   request.action=TRADE_ACTION_SLTP;
   request.position=position_ticket;
   request.symbol=symbol;
   request.magic=(ulong)magic;
   request.sl=stop_loss;
   request.tp=take_profit;
   const bool sent=OrderSend(request,result);
   accepted=sent && TesterRetcodeAccepted(result.retcode);
   return true;
  }

#endif
