#ifndef XAUUSD_MVP_EXECUTION_MQH
#define XAUUSD_MVP_EXECUTION_MQH

struct XauExecutionProjection
  {
   string request_id;
   XauExecutionStatus status;
   XauOrderType order_type;
   XauDirection direction;
   double order_entry;
   double fill_price;
   double stop_loss;
   double take_profit;
   double close_price;
   datetime transition_time;
  };

struct XauExecutionBinding
  {
   string request_id;
   ulong order_ticket;
   ulong position_id;
  };

bool ExecutionRequestIdValid(const string request_id)
  {
   return request_id != "" && StringFind(request_id,"\t") < 0 &&
          StringFind(request_id,"\r") < 0 && StringFind(request_id,"\n") < 0;
  }

bool BindExecutionOrder(XauExecutionBinding &bindings[],const string request_id,
                        const ulong order_ticket)
  {
   if(!ExecutionRequestIdValid(request_id) || order_ticket == 0)
      return false;
   for(int i=0;i<ArraySize(bindings);i++)
     {
      if(bindings[i].request_id == request_id)
         return bindings[i].order_ticket == order_ticket;
      if(bindings[i].order_ticket == order_ticket)
         return false;
     }
   const int index=ArraySize(bindings);
   if(ArrayResize(bindings,index+1) != index+1)
      return false;
   bindings[index].request_id=request_id;
   bindings[index].order_ticket=order_ticket;
   bindings[index].position_id=0;
   return true;
  }

bool BindExecutionPosition(XauExecutionBinding &bindings[],const ulong order_ticket,
                           const ulong position_id)
  {
   if(order_ticket == 0 || position_id == 0)
      return false;
   int matching_index=-1;
   for(int i=0;i<ArraySize(bindings);i++)
     {
      if(bindings[i].position_id == position_id && bindings[i].order_ticket != order_ticket)
         return false;
      if(bindings[i].order_ticket == order_ticket)
         matching_index=i;
     }
   if(matching_index < 0)
      return false;
   if(bindings[matching_index].position_id != 0 &&
      bindings[matching_index].position_id != position_id)
      return false;
   bindings[matching_index].position_id=position_id;
   return true;
  }

bool ResolveExecutionRequest(const XauExecutionBinding &bindings[],
                             const XauExecutionEvent event_kind,const ulong order_ticket,
                             const ulong position_id,string &request_id)
  {
   request_id="";
   for(int i=0;i<ArraySize(bindings);i++)
     {
      const bool order_match=(event_kind == XAU_EXECUTION_FILL && order_ticket != 0 &&
                              bindings[i].order_ticket == order_ticket);
      const bool position_match=(event_kind == XAU_EXECUTION_CLOSE && position_id != 0 &&
                                 bindings[i].position_id == position_id);
      if(order_match || position_match)
        {
         request_id=bindings[i].request_id;
         return true;
        }
     }
   return false;
  }

bool SameExecutionBindings(const XauExecutionBinding &left[],
                           const XauExecutionBinding &right[])
  {
   if(ArraySize(left) != ArraySize(right))
      return false;
   for(int i=0;i<ArraySize(left);i++)
      if(left[i].request_id != right[i].request_id ||
         left[i].order_ticket != right[i].order_ticket ||
         left[i].position_id != right[i].position_id)
         return false;
   return true;
  }

bool LoadExecutionBindings(const string file_name,XauExecutionBinding &bindings[])
  {
   XauExecutionBinding recovered[];
   int handle=FileOpen(file_name,FILE_READ|FILE_TXT|FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return false;
   bool valid=true;
   if(FileIsEnding(handle) || FileReadString(handle) != "XAU_EXECUTION_BINDINGS\t1")
      valid=false;
   while(valid && !FileIsEnding(handle))
     {
      const string line=FileReadString(handle);
      if(line == "")
         continue;
      string fields[];
      if(StringSplit(line,'\t',fields) != 3 || !ExecutionRequestIdValid(fields[0]))
        {
         valid=false;
         break;
        }
      const long signed_order=StringToInteger(fields[1]);
      const long signed_position=StringToInteger(fields[2]);
      if(signed_order <= 0 || signed_position < 0 ||
         !BindExecutionOrder(recovered,fields[0],(ulong)signed_order) ||
         (signed_position > 0 &&
          !BindExecutionPosition(recovered,(ulong)signed_order,(ulong)signed_position)))
        {
         valid=false;
         break;
        }
     }
   FileClose(handle);
   if(!valid)
      return false;
   ArrayResize(bindings,ArraySize(recovered));
   for(int i=0;i<ArraySize(recovered);i++)
      bindings[i]=recovered[i];
   return true;
  }

bool SaveExecutionBindingsAtomically(const string file_name,
                                     const XauExecutionBinding &bindings[])
  {
   if(file_name == "" || StringFind(file_name,"..") >= 0)
      return false;
   const string temporary=file_name+".tmp";
   int handle=FileOpen(temporary,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return false;
   bool valid=FileWriteString(handle,"XAU_EXECUTION_BINDINGS\t1\r\n") > 0;
   for(int i=0;valid && i<ArraySize(bindings);i++)
     {
      if(!ExecutionRequestIdValid(bindings[i].request_id) || bindings[i].order_ticket == 0)
        {
         valid=false;
         break;
        }
      const string line=StringFormat("%s\t%I64u\t%I64u\r\n",bindings[i].request_id,
                                     bindings[i].order_ticket,bindings[i].position_id);
      valid=FileWriteString(handle,line) == StringLen(line);
     }
   FileFlush(handle);
   FileClose(handle);
   XauExecutionBinding verified[];
   valid=valid && LoadExecutionBindings(temporary,verified) &&
         SameExecutionBindings(bindings,verified);
   if(!valid || !FileMove(temporary,0,file_name,FILE_REWRITE))
     {
      FileDelete(temporary);
      return false;
     }
   return true;
  }

bool InitializeExecutionProjection(XauExecutionProjection &record,const string request_id,
                                   const XauOrderType order_type,const XauDirection direction,
                                   const double order_entry,const double stop_loss,
                                   const double take_profit,const datetime submitted_at)
  {
   if(request_id == "" || order_entry <= 0.0 || submitted_at <= 0)
      return false;
   if(!ProtectionModificationValid(direction,order_entry,stop_loss,stop_loss,take_profit))
      return false;
   record.request_id=request_id;
   record.status=XAU_EXECUTION_SUBMITTED;
   record.order_type=order_type;
   record.direction=direction;
   record.order_entry=order_entry;
   record.fill_price=0.0;
   record.stop_loss=stop_loss;
   record.take_profit=take_profit;
   record.close_price=0.0;
   record.transition_time=submitted_at;
   return true;
  }

bool ProjectExecutionOutcome(XauExecutionProjection &record,const XauExecutionEvent event_kind,
                             const datetime outcome_time,const double outcome_price=0.0,
                             const double proposed_stop=0.0,const double proposed_tp=0.0)
  {
   if(record.request_id == "" || outcome_time < record.transition_time)
      return false;

   XauExecutionStatus next_status=record.status;
   if(!ExecutionTransition(record.status,event_kind,record.order_type,next_status))
      return false;
   if(event_kind == XAU_EXECUTION_FILL && outcome_price <= 0.0)
      return false;
   if(event_kind == XAU_EXECUTION_CLOSE && outcome_price <= 0.0)
      return false;
   if((event_kind == XAU_EXECUTION_MODIFY ||
       event_kind == XAU_EXECUTION_MODIFY_REJECT) &&
      !ProtectionModificationValid(record.direction,record.order_entry,record.stop_loss,
                                   proposed_stop,proposed_tp))
      return false;

   if(event_kind == XAU_EXECUTION_FILL)
      record.fill_price=outcome_price;
   else if(event_kind == XAU_EXECUTION_CLOSE)
      record.close_price=outcome_price;
   else if(event_kind == XAU_EXECUTION_MODIFY)
     {
      record.stop_loss=proposed_stop;
      record.take_profit=proposed_tp;
     }
   record.status=next_status;
   record.transition_time=outcome_time;
   return true;
  }

#endif
