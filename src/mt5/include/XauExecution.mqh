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
