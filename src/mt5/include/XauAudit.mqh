#ifndef XAUUSD_MVP_AUDIT_MQH
#define XAUUSD_MVP_AUDIT_MQH

struct XauOrderAuditEvent
  {
   string event_id;
   string request_id;
   string zone_id;
   string rule_ids;
   XauDirection direction;
   XauOrderType order_type;
   datetime broker_time;
   double entry;
   double stop_loss;
   double take_profit;
  };

bool AuditTextValid(const string value)
  {
   return value != "" && StringFind(value,"\"") < 0 && StringFind(value,"\\") < 0 &&
          StringFind(value,"\r") < 0 && StringFind(value,"\n") < 0;
  }

bool SerializeOrderAudit(const XauOrderAuditEvent &event,string &line)
  {
   line="";
   if(!AuditTextValid(event.event_id) || !ExecutionRequestIdValid(event.request_id) ||
      !AuditTextValid(event.zone_id) || !AuditTextValid(event.rule_ids) ||
      event.broker_time <= 0 || event.entry <= 0.0)
      return false;
   line=StringFormat(
      "{\"schema_version\":1,\"kind\":\"order\",\"event_id\":\"%s\","
      "\"execution_request_id\":\"%s\",\"zone_id\":\"%s\",\"rule_ids\":\"%s\","
      "\"direction\":%d,\"order_type\":%d,\"broker_time\":%I64d,"
      "\"entry\":\"%.10f\",\"stop_loss\":\"%.10f\",\"take_profit\":\"%.10f\"}",
      event.event_id,event.request_id,event.zone_id,event.rule_ids,(int)event.direction,
      (int)event.order_type,(long)event.broker_time,event.entry,event.stop_loss,event.take_profit);
   return true;
  }

bool AppendAuditLine(const string file_name,const string line)
  {
   if(file_name == "" || StringFind(file_name,"..") >= 0 || line == "")
      return false;
   int handle=FileOpen(file_name,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   if(handle == INVALID_HANDLE || !FileSeek(handle,0,SEEK_END))
     {
      if(handle != INVALID_HANDLE)
         FileClose(handle);
      return false;
     }
   const string record=line+"\r\n";
   const bool written=FileWriteString(handle,record) == StringLen(record);
   FileFlush(handle);
   FileClose(handle);
   return written;
  }

bool AppendOrderThenProject(const string audit_file,const XauEntryRejection decision,
                            const XauOrderAuditEvent &event,
                            XauExecutionProjection &projections[])
  {
   if(decision != XAU_ENTRY_ALLOWED)
      return false;
   XauExecutionProjection projection;
   if(!InitializeExecutionProjection(projection,event.request_id,event.order_type,event.direction,
                                     event.entry,event.stop_loss,event.take_profit,
                                     event.broker_time))
      return false;
   string line="";
   if(!SerializeOrderAudit(event,line) || !AppendAuditLine(audit_file,line))
      return false;
   const int index=ArraySize(projections);
   if(ArrayResize(projections,index+1) != index+1)
      return false;
   projections[index]=projection;
   return true;
  }

#endif
