#ifndef XAU_VISUAL_MQH
#define XAU_VISUAL_MQH

// Rendering-only adapter. These functions consume domain/audit payloads and never
// feed values back into signal, risk, safety, or execution decisions.

struct XauVisualMarker
  {
   string event_id;
   string zone_id;
   string label;
   datetime broker_time;
   double entry;
   double stop_loss;
   double take_profit;
   int zone_priority;
  };

color XauZoneColor(const int priority)
  {
   return priority==1 ? clrGold : clrDodgerBlue;
  }

string XauMarkerTooltip(const XauVisualMarker &marker,const int digits)
  {
   return StringFormat("Time=%s | Zone=%s | Entry=%s | SL=%s | TP=%s | Event=%s",
                       TimeToString(marker.broker_time,TIME_DATE|TIME_SECONDS),
                       marker.zone_id,
                       DoubleToString(marker.entry,digits),
                       DoubleToString(marker.stop_loss,digits),
                       DoubleToString(marker.take_profit,digits),
                       marker.event_id);
  }

bool DrawXauZone(const long chart_id,const XauZone &zone,
                 const datetime from_time,const datetime to_time)
  {
   if(from_time<=0 || to_time<=from_time || zone.high<zone.low)
      return false;
   string name="XAU_ZONE_"+zone.id;
   if(ObjectFind(chart_id,name)<0 &&
      !ObjectCreate(chart_id,name,OBJ_RECTANGLE,0,from_time,zone.low,to_time,zone.high))
      return false;
   if(!ObjectSetInteger(chart_id,name,OBJPROP_COLOR,XauZoneColor(zone.priority)) ||
      !ObjectSetInteger(chart_id,name,OBJPROP_FILL,true) ||
      !ObjectSetInteger(chart_id,name,OBJPROP_BACK,true) ||
      !ObjectSetInteger(chart_id,name,OBJPROP_SELECTABLE,false) ||
      !ObjectSetInteger(chart_id,name,OBJPROP_HIDDEN,true))
      return false;
   return ObjectMove(chart_id,name,0,from_time,zone.low) &&
          ObjectMove(chart_id,name,1,to_time,zone.high);
  }

bool DrawXauAuditMarker(const long chart_id,const XauVisualMarker &marker,
                        const int digits)
  {
   if(marker.broker_time<=0 || marker.entry<=0.0 || marker.event_id=="" ||
      marker.zone_id=="" || marker.label=="")
      return false;
   string name="XAU_EVENT_"+marker.event_id;
   if(ObjectFind(chart_id,name)<0 &&
      !ObjectCreate(chart_id,name,OBJ_TEXT,0,marker.broker_time,marker.entry))
      return false;
   if(!ObjectSetString(chart_id,name,OBJPROP_TEXT,marker.label) ||
      !ObjectSetString(chart_id,name,OBJPROP_TOOLTIP,XauMarkerTooltip(marker,digits)) ||
      !ObjectSetInteger(chart_id,name,OBJPROP_COLOR,XauZoneColor(marker.zone_priority)) ||
      !ObjectSetInteger(chart_id,name,OBJPROP_ANCHOR,ANCHOR_CENTER) ||
      !ObjectSetInteger(chart_id,name,OBJPROP_SELECTABLE,false) ||
      !ObjectSetInteger(chart_id,name,OBJPROP_HIDDEN,true))
      return false;
   return ObjectMove(chart_id,name,0,marker.broker_time,marker.entry);
  }

#endif
