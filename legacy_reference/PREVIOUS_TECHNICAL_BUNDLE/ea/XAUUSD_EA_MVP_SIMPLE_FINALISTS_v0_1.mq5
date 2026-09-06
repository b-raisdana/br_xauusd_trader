//+------------------------------------------------------------------+
//| XAUUSD_EA_MVP_SIMPLE_FINALISTS_v0_1.mq5                               |
//| Scope: S2 reset experimental AR-SESSION-01; frozen S1 control preserved |
//| Status: EXPERIMENTAL CHALLENGER - AR-SESSION-01 only; frozen baseline preserved separately. Compile/test evidence required. |
//+------------------------------------------------------------------+
#property strict
#property version   "1.80"
#property description "XAUUSD MVP simple finalist matrix candidate"
#property tester_file "ranges.csv"

#include <Trade/Trade.mqh>

// AR-SESSION-01 experimental family. BASELINE_CARRY must preserve frozen trading behavior.
enum ENUM_SESSION_FLAT_MODE { SESSION_BASELINE_CARRY=0, SESSION_PB_FLAT=1, SESSION_ALL_FLAT=2 };

// Simple first-MVP finalists selected by causal Train/Forward screen.
enum ENUM_MVP_SIMPLE_PROFILE
  {
   MVP_SIMPLE_CONTROL=0,
   MVP_SIMPLE_PB_ONLY_SPACE15=1,
   MVP_SIMPLE_SPACE15_HIGH_H1=2,
   MVP_SIMPLE_SPACE15_HIGH_H2=3,
   MVP_SIMPLE_SPACE15_HIGHSPACE_H2=4
  };

// Rule IDs: a-5, b-23, b-29, b-30, QA/Visual
input string InpRangesFile="ranges.csv";                         // a-5
input string InpJournalFile="XAUUSD_EA_S1_v0_7_4_TEST_MATRIX_journal.csv";     // QA Journal
input string InpSummaryFile="XAUUSD_EA_S1_v0_7_4_TEST_MATRIX_summary.csv";     // concise signal/trade report
input double InpRCapUSD=6.0;                                    // b-29/b-30 R_CAP
input bool   InpQADiscoveryMode=true;                            // QA-DL / QA-R2
input double InpQAStrategyCapitalBasis=100.0;                    // QA-DL shadow b-23 basis only
input bool   InpDebugVisual=false;                               // visual-3 extra debug only
input bool   InpShowZonesOnLiveChart=true;                       // visual-1 default ON
input bool   InpShowSignalTextOnLiveChart=false;                 // visual-2 live default OFF
input bool   InpCleanupVisualOnDeinit=false;                     // explicit only
input int    InpHighReversalMaxPerDay=3;                          // TEST-HIGH-R: high zones only, total/day
input double InpHighReversalSLMultiplier=1.5;                     // TEST-HIGH-R: applies to High reversal #1..#N
input double InpTestVolumeLot=0.01;                              // TEST-HARNESS only; 0.01 preserves S1 b-21/b-22 baseline
input bool   InpTestDailyLossOverride=false;                     // TEST-HARNESS only; false preserves b-23 baseline
input double InpTestDailyLossPercent=20.0;                       // TEST-HARNESS only; used only when override=true
input bool   InpFastValidationMode=false;                    // TEST-HARNESS reporting only; never changes trade logic
// AR-SESSION-01 — APPROVED_REQUIREMENT_PENDING_VALIDATION; experimental branch only.
input ENUM_SESSION_FLAT_MODE InpSessionFlatMode=SESSION_BASELINE_CARRY; // 0 carry control, 1 PB-only flat, 2 all EA positions flat
input double InpSessionPreCloseMinutes=5.0;                     // derived from broker session end; offset is experimental control
input bool   InpSessionSafetyTelemetry=true;                    // schedule/carry/flatten QA telemetry
// MVP simple finalist controls. CONTROL leaves R2 strategy logic unchanged.
input ENUM_MVP_SIMPLE_PROFILE InpMVPSimpleProfile=MVP_SIMPLE_CONTROL;
input int    InpMaxLivePositions=99;                              // 99 disables the deployment cap in 100K equivalence runs
input bool   InpMVPProfileTelemetry=true;

const ulong  EA_MAGIC=260829075;                                  // QA execution identity
const double BREAKOUT_BUFFER_USD=1.0;                            // b-4
const double PULLBACK_PENETRATION_USD=0.20;                      // b-8

CTrade trade;

// TEST-HARNESS I/O plumbing only: during Strategy Tester runs, use the shared
// FILE_COMMON sandbox so input/output files survive local-agent cleanup and are
// accessible from the harness after terminal shutdown. Live/chart behavior stays
// on the normal terminal-local MQL5\Files sandbox.
int HarnessFileOpenFlags(const int base_flags)
  {
   if((bool)MQLInfoInteger(MQL_TESTER)) return(base_flags|FILE_COMMON);
   return(base_flags);
  }

int HarnessFileScopeFlag()
  {
   if((bool)MQLInfoInteger(MQL_TESTER)) return(FILE_COMMON);
   return(0);
  }

enum ENUM_TREND_STATE { TREND_NONE=0, TREND_UP=1, TREND_DOWN=-1 };
enum ENUM_USAGE_STATE { USAGE_UNUSED=0, USAGE_ACTIVE=1, USAGE_CONSUMED=2 };

struct RawZone
  {
   datetime day;
   string   day_key;
   double   low;
   double   high;
   string   priority;
   string   note;
  };

struct ZoneRuntime
  {
   string day_key;
   string id;
   double low;
   double high;
   string priority;
   bool   engaged_buy;
   bool   engaged_sell;
   int    reversal_usage;
   int    reversal_fill_count;          // TEST-HIGH-R: executed real Reversal fills this zone/day
   int    pullback_fill_count;          // MVP simple: executed PB fills this zone/day
   datetime last_reversal_buy_signal_bar;   // b-31: one R-B per M15/zone
   datetime last_reversal_sell_signal_bar;  // b-31: one R-S per M15/zone
  };

struct PullbackCycle
  {
   bool     active;
   bool     buy;
   string   day_key;
   string   zone_id;
   double   zone_low;
   double   zone_high;
   datetime breakout_bar_time;
   int      valid_bar_no;              // 1=t+1 ... 5=t+5
   bool     penetration_latched;
   ulong    order_ticket;
   bool     waiting_logged;
   string   parent_breakout_id;       // QA lineage: BO#xx that created this cycle
  };

struct RequestMeta
  {
   bool   active;
   string comment;
   double requested_price;
   double sl;
   double tp;
   double r0;
   string target_zone_id;
   string parent_breakout_id;         // blank for Reversal; BO#xx for Pullback
   int    reversal_ordinal;            // TEST-HIGH-R; 0 for Pullback
  };

struct PositionTrack
  {
   bool   active;
   ulong  position_id;
   ulong  position_ticket;
   string day_key;
   string zone_id;
   string trade_type;                  // R or P
   bool   buy;
   double risk_anchor_entry;
   double actual_fill;
   double initial_sl;
   double tp;
   double r0;
   int    r_stage;                     // 0 initial, 1 >=1R, 2 >=1.5R, 3 >=2R structural
   double desired_sl;
   bool   sl_retry_logged;
   string target_zone_id;
   string parent_breakout_id;         // QA lineage only
   bool   stacked_pullback;           // entered while older same Zone+Direction PB position was open
   int    reversal_ordinal;            // TEST-HIGH-R: real Reversal number on this zone/day
   bool   session_close_requested;       // AR-SESSION-01 close-confirmation telemetry
   string session_close_reason;          // AR-SESSION-01
   string last_carry_audit_key;          // one carry observation per broker session
  };

RawZone       g_raw_zones[];
ZoneRuntime   g_zones[];
PullbackCycle g_cycles[];
RequestMeta   g_requests[];
PositionTrack g_positions[];

string           g_day_key="";
bool             g_day_valid=false;
datetime         g_bar_time=0;
double           g_prev_bid=0.0;
double           g_ref_high=0.0;
double           g_ref_low=0.0;
ENUM_TREND_STATE g_trend=TREND_NONE;
long             g_event_seq=0;
int              g_breakout_seq=0;             // resets each Broker day; display id BO#01...
double           g_initial_deposit=0.0;
double           g_daily_realized_net=0.0;
bool             g_daily_stop=false;
bool             g_daily_would_trigger_logged=false;
string           g_visual_prefix="XAU_S1_";
bool             g_session_preclose_active=false;
string           g_session_cutoff_key="";
string           g_session_active_window_key="";
datetime         g_session_active_from=0;
datetime         g_session_active_to=0;

// Forward declaration used by position/pullback/session lifecycle.
int FindActiveCycle(string day_key,string zone_id,bool buy);
int AllowedReversalCountForZone(int zone_index);
bool CloseInvalidatedReversal(int track_index,string zone_id);
void CancelAllPullbackCycles(string event_name,string reason);

//+------------------------------------------------------------------+
//| Utility / QA                                                     |
//+------------------------------------------------------------------+
string Trim(string s)
  {
   StringTrimLeft(s);
   StringTrimRight(s);
   return s;
  }

string Lower(string s)
  {
   StringToLower(s);
   return s;
  }

string DayKey(datetime t)
  {
   return TimeToString(t,TIME_DATE);
  }

string TrendToString(ENUM_TREND_STATE t)
  {
   if(t==TREND_UP) return "TREND_UP";
   if(t==TREND_DOWN) return "TREND_DOWN";
   return "TREND_NONE";
  }

string MVPSimpleProfileToString()
  {
   if(InpMVPSimpleProfile==MVP_SIMPLE_PB_ONLY_SPACE15) return "PB_ONLY_SPACE15";
   if(InpMVPSimpleProfile==MVP_SIMPLE_SPACE15_HIGH_H1) return "SPACE15_HIGH_H1";
   if(InpMVPSimpleProfile==MVP_SIMPLE_SPACE15_HIGH_H2) return "SPACE15_HIGH_H2";
   if(InpMVPSimpleProfile==MVP_SIMPLE_SPACE15_HIGHSPACE_H2) return "SPACE15_HIGHSPACE_H2";
   return "CONTROL";
  }

bool MVPSimpleActive() { return InpMVPSimpleProfile!=MVP_SIMPLE_CONTROL; }

int MVPSimpleHighMax()
  {
   if(InpMVPSimpleProfile==MVP_SIMPLE_SPACE15_HIGH_H1) return 1;
   if(InpMVPSimpleProfile==MVP_SIMPLE_SPACE15_HIGH_H2 || InpMVPSimpleProfile==MVP_SIMPLE_SPACE15_HIGHSPACE_H2) return 2;
   if(InpMVPSimpleProfile==MVP_SIMPLE_PB_ONLY_SPACE15) return 0;
   return InpHighReversalMaxPerDay;
  }

string ModelToString() { return "MVP_SIMPLE_"+MVPSimpleProfileToString(); }

string Sanitize(string s)
  {
   StringReplace(s,",",";");
   StringReplace(s,"\r"," ");
   StringReplace(s,"\n"," ");
   return s;
  }

string ServerTimeMs()
  {
   MqlTick tick;
   if(SymbolInfoTick(_Symbol,tick))
     {
      long ms=tick.time_msc;
      datetime sec=(datetime)(ms/1000);
      return StringFormat("%s.%03d",TimeToString(sec,TIME_DATE|TIME_SECONDS),(int)(ms%1000));
     }
   return TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS);
  }

string NextEventId()
  {
   g_event_seq++;
   return StringFormat("E%I64d",g_event_seq);
  }

// S2-ZONE-DENSITY measurement now; no S1 filtering.
void GetZoneGapContext(string zone_id,double &gap_below,double &gap_above,double &nearest_gap)
  {
   gap_below=-1.0; gap_above=-1.0; nearest_gap=-1.0;
   if(zone_id=="") return;
   int idx=-1;
   for(int i=0;i<ArraySize(g_zones);i++)
      if(g_zones[i].id==zone_id) { idx=i; break; }
   if(idx<0) return;
   if(idx>0) gap_below=g_zones[idx].low-g_zones[idx-1].high;
   if(idx+1<ArraySize(g_zones)) gap_above=g_zones[idx+1].low-g_zones[idx].high;
   if(gap_below>=0.0 && gap_above>=0.0) nearest_gap=MathMin(gap_below,gap_above);
   else if(gap_below>=0.0) nearest_gap=gap_below;
   else if(gap_above>=0.0) nearest_gap=gap_above;
  }

string GapText(double v)
  {
   if(v<0.0) return "N/A";
   return DoubleToString(v,2);
  }

// QA concise report: signals, real trades, secondary candidates and QA tags; management remains in full Journal.
void WriteSummary(string category,string event,string zone_id,string signal_type,string entry_type,
                  double requested_price,double fill_price,double sl,double tp,double r0,
                  ulong position_ticket,bool counted_in_pnl,double net_pnl,string note,
                  string breakout_id="",string parent_breakout_id="",bool stacked_pullback=false,int reversal_ordinal=0)
  {
   // v0.7.2: keep the human summary concise. Full management detail remains in Journal.
   if(category=="MANAGEMENT") return;
   int h=FileOpen(InpSummaryFile,HarnessFileOpenFlags(FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI),',',CP_UTF8);
   if(h==INVALID_HANDLE)
     {
      PrintFormat("SUMMARY_OPEN_FAILED file=%s err=%d",InpSummaryFile,GetLastError());
      return;
     }
   if(FileSize(h)==0)
     {
      FileWrite(h,"server_time","category","event","zone_id","signal","trend","entry_type",
                "breakout_id","parent_breakout_id","requested_price","fill_price","sl","tp","r0","position_ticket","counted_in_pnl",
                "net_pnl","stacked_pullback","reversal_ordinal","gap_below","gap_above","nearest_gap","note");
     }
   double gb,ga,gn; GetZoneGapContext(zone_id,gb,ga,gn);
   FileSeek(h,0,SEEK_END);
   FileWrite(h,ServerTimeMs(),category,event,zone_id,signal_type,TrendToString(g_trend),entry_type,
             breakout_id,parent_breakout_id,
             DoubleToString(requested_price,_Digits),DoubleToString(fill_price,_Digits),
             DoubleToString(sl,_Digits),DoubleToString(tp,_Digits),DoubleToString(r0,_Digits),
             StringFormat("%I64u",position_ticket),counted_in_pnl?"true":"false",
             DoubleToString(net_pnl,2),stacked_pullback?"true":"false",IntegerToString(reversal_ordinal),GapText(gb),GapText(ga),GapText(gn),Sanitize(note));
   FileClose(h);
  }

// TEST-HARNESS reporting optimization only. In fast validation we keep only
// the journal events required for deterministic execution/risk QA. Summary remains active.
bool ShouldWriteJournalEvent(string event)
  {
   if(StringFind(event,"SESSION_")==0) return true;
   if(!InpFastValidationMode) return true;
   return (event=="ZONES_LOADED" ||
           event=="SL_MOVE_CONFIRMED" ||
           event=="DAILY_LOSS_STOP" ||
           event=="DAILY_LOSS_WOULD_TRIGGER" ||
           event=="EXECUTION_BLOCKED_MARGIN" ||
           event=="ORDER_REJECTED" ||
           event=="PENDING_PLACE_RETRY" ||
           event=="TEST_CONFIGURATION_ERROR" ||
           event=="EA_INITIALIZED" ||
           event=="EA_DEINITIALIZED");
  }

// Rule IDs: QA Journal. File handle is closed after every record per ToDo.
string WriteJournal(string rule_id,string event,string zone_id,string signal_type,string entry_type,
                    double requested_price,double fill_price,double sl,double tp,
                    ulong order_ticket,ulong deal_ticket,ulong position_ticket,string reason,
                    string breakout_id="",string parent_breakout_id="")
  {
   string eid=NextEventId();
   if(!ShouldWriteJournalEvent(event)) return eid;
   int h=FileOpen(InpJournalFile,HarnessFileOpenFlags(FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI),',',CP_UTF8);
   if(h==INVALID_HANDLE)
     {
      PrintFormat("JOURNAL_OPEN_FAILED file=%s err=%d",InpJournalFile,GetLastError());
      return eid;
     }
   if(FileSize(h)==0)
     {
      FileWrite(h,"event_id","server_time","ea_version","symbol","broker_server","sl_tp_model",
                "rule_id","event","zone_id","trend_state","signal_type","entry_type",
                "breakout_id","parent_breakout_id","requested_price","fill_price","sl","tp","order_ticket","deal_ticket","position_ticket",
                "gap_below","gap_above","nearest_gap","reason_error");
     }
   double gb,ga,gn; GetZoneGapContext(zone_id,gb,ga,gn);
   FileSeek(h,0,SEEK_END);
   FileWrite(h,eid,ServerTimeMs(),"1.77-R2-ARSESSION01",_Symbol,AccountInfoString(ACCOUNT_SERVER),ModelToString(),
             rule_id,event,zone_id,TrendToString(g_trend),signal_type,entry_type,
             breakout_id,parent_breakout_id,
             DoubleToString(requested_price,_Digits),DoubleToString(fill_price,_Digits),
             DoubleToString(sl,_Digits),DoubleToString(tp,_Digits),
             StringFormat("%I64u",order_ticket),StringFormat("%I64u",deal_ticket),StringFormat("%I64u",position_ticket),
             GapText(gb),GapText(ga),GapText(gn),Sanitize(reason));
   FileClose(h);
   return eid;
  }

//+------------------------------------------------------------------+
//| AR-SESSION-01 experimental session safety                       |
//+------------------------------------------------------------------+
string SessionModeToString()
  {
   if(InpSessionFlatMode==SESSION_PB_FLAT) return "PB_FLAT";
   if(InpSessionFlatMode==SESSION_ALL_FLAT) return "ALL_FLAT";
   return "BASELINE_CARRY";
  }

string WeekdayName(int d)
  {
   string n[7]={"SUNDAY","MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY"};
   if(d<0 || d>6) return "UNKNOWN";
   return n[d];
  }

int SecondsOfDay(datetime t)
  {
   MqlDateTime x;
   if(!TimeToStruct(t,x)) return 0;
   return x.hour*3600+x.min*60+x.sec;
  }

datetime BrokerDayStart(datetime t)
  {
   return StringToTime(DayKey(t)+" 00:00:00");
  }

string SessionWindowKey(datetime a,datetime b)
  {
   return TimeToString(a,TIME_DATE|TIME_SECONDS)+"->"+TimeToString(b,TIME_DATE|TIME_SECONDS);
  }

bool GetContainingTradeSession(datetime now,datetime &from_abs,datetime &to_abs,int &session_index,int &weekday)
  {
   datetime today=BrokerDayStart(now);
   for(int off=-1;off<=0;off++)
     {
      datetime base=today+(off*86400);
      MqlDateTime bd;
      if(!TimeToStruct(base,bd)) continue;
      ENUM_DAY_OF_WEEK dow=(ENUM_DAY_OF_WEEK)bd.day_of_week;
      for(uint idx=0;idx<16;idx++)
        {
         datetime raw_from=0,raw_to=0;
         if(!SymbolInfoSessionTrade(_Symbol,dow,idx,raw_from,raw_to)) break;
         int fs=SecondsOfDay(raw_from);
         int ts=SecondsOfDay(raw_to);
         datetime a=base+fs;
         datetime b=base+ts;
         if(ts<=fs) b+=86400; // crossing midnight or 24h representation
         if(now>=a && now<b)
           {
            from_abs=a; to_abs=b; session_index=(int)idx; weekday=bd.day_of_week;
            return true;
           }
        }
     }
   return false;
  }

void LogWeeklySessionSchedule()
  {
   if(!InpSessionSafetyTelemetry) return;
   int found=0;
   for(int d=0;d<7;d++)
     {
      for(uint idx=0;idx<16;idx++)
        {
         datetime a=0,b=0;
         if(!SymbolInfoSessionTrade(_Symbol,(ENUM_DAY_OF_WEEK)d,idx,a,b)) break;
         found++;
         string note=StringFormat("mode=%s day=%s day_index=%d session_index=%d raw_from=%s raw_to=%s from_sec=%d to_sec=%d",
                                  SessionModeToString(),WeekdayName(d),d,(int)idx,
                                  TimeToString(a,TIME_SECONDS),TimeToString(b,TIME_SECONDS),SecondsOfDay(a),SecondsOfDay(b));
         WriteJournal("AR-SESSION-01","SESSION_SCHEDULE","","","Telemetry",0,0,0,0,0,0,0,note);
         WriteSummary("QA","SESSION_SCHEDULE","","","Telemetry",0,0,0,0,0,0,false,0.0,note);
        }
     }
   if(found==0)
     {
      string note="SymbolInfoSessionTrade returned no trade sessions; AR-SESSION-01 runtime validation cannot pass";
      WriteJournal("AR-SESSION-01","SESSION_SCHEDULE_MISSING","","","Telemetry",0,0,0,0,0,0,0,note);
      WriteSummary("QA","SESSION_SCHEDULE_MISSING","","","Telemetry",0,0,0,0,0,0,false,0.0,note);
     }
  }

bool SessionBlocksPullbackEntries()
  {
   return (g_session_preclose_active && InpSessionFlatMode!=SESSION_BASELINE_CARRY);
  }

bool SessionBlocksReversalEntries()
  {
   return (g_session_preclose_active && InpSessionFlatMode==SESSION_ALL_FLAT);
  }

bool SessionModeTargetsType(string trade_type)
  {
   if(InpSessionFlatMode==SESSION_ALL_FLAT) return true;
   if(InpSessionFlatMode==SESSION_PB_FLAT && trade_type=="P") return true;
   return false;
  }

void CancelSessionOrphanPendingOrders(string reason)
  {
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=EA_MAGIC) continue;
      string comment=OrderGetString(ORDER_COMMENT);
      bool ok=trade.OrderDelete(ticket);
      uint rc=trade.ResultRetcode();
      string ev=(ok && (rc==TRADE_RETCODE_DONE || rc==TRADE_RETCODE_DONE_PARTIAL)) ? "SESSION_PENDING_CANCEL_CONFIRMED" : "SESSION_PENDING_CANCEL_FAILED";
      WriteJournal("AR-SESSION-01",ev,"","PB","Stop",0,0,0,0,ticket,trade.ResultDeal(),0,
                   StringFormat("mode=%s comment=%s %s ret=%s",SessionModeToString(),comment,reason,trade.ResultRetcodeDescription()));
     }
  }

void AuditCrossSessionPositions(datetime now,datetime session_from,datetime session_to,string window_key)
  {
   if(!InpSessionSafetyTelemetry) return;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=EA_MAGIC) continue;
      datetime opened=(datetime)PositionGetInteger(POSITION_TIME);
      if(opened>=session_from) continue;
      ulong position_id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      int p=FindPositionTrack(position_id);
      string type=""; string day=""; string zone=""; bool buy=false;
      if(p>=0)
        {
         if(g_positions[p].last_carry_audit_key==window_key) continue;
         g_positions[p].last_carry_audit_key=window_key;
         type=g_positions[p].trade_type; day=g_positions[p].day_key; zone=g_positions[p].zone_id; buy=g_positions[p].buy;
        }
      else
        {
         string comment=PositionGetString(POSITION_COMMENT);
         ParseComment(comment,type,day,zone,buy);
        }
      string sig=(type=="P"?(buy?"PB-B":"PB-S"):(type=="R"?(buy?"R-B":"R-S"):"UNKNOWN"));
      string note=StringFormat("mode=%s position_open=%s session_from=%s session_to=%s original_day=%s type=%s",
                               SessionModeToString(),TimeToString(opened,TIME_DATE|TIME_SECONDS),
                               TimeToString(session_from,TIME_DATE|TIME_SECONDS),TimeToString(session_to,TIME_DATE|TIME_SECONDS),day,type);
      WriteJournal("AR-SESSION-01","SESSION_CROSS_CARRY_OBSERVED",zone,sig,"Telemetry",0,0,0,0,0,0,ticket,note);
      WriteSummary("QA_TAG","SESSION_CROSS_CARRY_OBSERVED",zone,sig,"Telemetry",0,0,0,0,0,ticket,false,0.0,note);
      if(SessionModeTargetsType(type))
        {
         WriteJournal("AR-SESSION-01","SESSION_CARRY_VIOLATION",zone,sig,"Telemetry",0,0,0,0,0,0,ticket,note);
         WriteSummary("QA_TAG","SESSION_CARRY_VIOLATION",zone,sig,"Telemetry",0,0,0,0,0,ticket,false,0.0,note);
        }
     }
  }

void FlattenSessionPositions(string reason)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=EA_MAGIC) continue;
      ulong position_id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      int p=FindPositionTrack(position_id);
      string type=""; string day=""; string zone=""; bool buy=false;
      if(p>=0)
        {
         type=g_positions[p].trade_type; day=g_positions[p].day_key; zone=g_positions[p].zone_id; buy=g_positions[p].buy;
        }
      else
        {
         string comment=PositionGetString(POSITION_COMMENT);
         ParseComment(comment,type,day,zone,buy);
        }
      if(!SessionModeTargetsType(type)) continue;
      string sig=(type=="P"?(buy?"PB-B":"PB-S"):(buy?"R-B":"R-S"));
      if(p>=0)
        {
         g_positions[p].session_close_requested=true;
         g_positions[p].session_close_reason=reason;
        }
      WriteJournal("AR-SESSION-01","SESSION_FLAT_CLOSE_REQUESTED",zone,sig,"Market",0,0,0,0,0,0,ticket,
                   StringFormat("mode=%s %s",SessionModeToString(),reason));
      bool ok=trade.PositionClose(ticket);
      uint rc=trade.ResultRetcode();
      if(!ok || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_DONE_PARTIAL))
        {
         if(p>=0) g_positions[p].session_close_requested=false;
         WriteJournal("AR-SESSION-01","SESSION_FLAT_CLOSE_FAILED",zone,sig,"Market",0,0,0,0,0,trade.ResultDeal(),ticket,
                      StringFormat("mode=%s %s ret=%s",SessionModeToString(),reason,trade.ResultRetcodeDescription()));
         WriteSummary("QA_TAG","SESSION_FLAT_CLOSE_FAILED",zone,sig,"Market",0,0,0,0,0,ticket,false,0.0,
                      StringFormat("mode=%s %s ret=%s",SessionModeToString(),reason,trade.ResultRetcodeDescription()));
        }
     }
  }

void ManageSessionSafety(datetime now)
  {
   datetime a=0,b=0; int idx=-1,dow=-1;
   if(!GetContainingTradeSession(now,a,b,idx,dow))
     {
      g_session_preclose_active=false;
      return;
     }
   string wk=SessionWindowKey(a,b);
   if(wk!=g_session_active_window_key)
     {
      g_session_active_window_key=wk;
      g_session_active_from=a;
      g_session_active_to=b;
      if(InpSessionSafetyTelemetry)
        {
         string note=StringFormat("mode=%s day=%s session_index=%d from=%s to=%s",
                                  SessionModeToString(),WeekdayName(dow),idx,
                                  TimeToString(a,TIME_DATE|TIME_SECONDS),TimeToString(b,TIME_DATE|TIME_SECONDS));
         WriteJournal("AR-SESSION-01","SESSION_WINDOW_ACTIVE","","","Telemetry",0,0,0,0,0,0,0,note);
         WriteSummary("QA","SESSION_WINDOW_ACTIVE","","","Telemetry",0,0,0,0,0,0,false,0.0,note);
        }
     }
   AuditCrossSessionPositions(now,a,b,wk);
   if(InpSessionFlatMode==SESSION_BASELINE_CARRY)
     {
      g_session_preclose_active=false;
      return;
     }
   int cutoff_seconds=(int)MathRound(InpSessionPreCloseMinutes*60.0);
   if(cutoff_seconds<1) cutoff_seconds=1;
   datetime cutoff=b-cutoff_seconds;
   bool in_cutoff=(now>=cutoff && now<b);
   g_session_preclose_active=in_cutoff;
   if(!in_cutoff) return;
   string ck=wk+"|"+SessionModeToString();
   string reason=StringFormat("broker_session_end=%s cutoff=%s minutes=%.2f window=%s",
                              TimeToString(b,TIME_DATE|TIME_SECONDS),TimeToString(cutoff,TIME_DATE|TIME_SECONDS),InpSessionPreCloseMinutes,wk);
   if(g_session_cutoff_key!=ck)
     {
      g_session_cutoff_key=ck;
      WriteJournal("AR-SESSION-01","SESSION_PRE_CLOSE_CUTOFF_ENTERED","","","Telemetry",0,0,0,0,0,0,0,
                   StringFormat("mode=%s %s",SessionModeToString(),reason));
      WriteSummary("QA","SESSION_PRE_CLOSE_CUTOFF_ENTERED","","","Telemetry",0,0,0,0,0,0,false,0.0,
                   StringFormat("mode=%s %s",SessionModeToString(),reason));
      CancelAllPullbackCycles("SESSION_PULLBACK_CYCLE_CANCELLED",reason);
      CancelSessionOrphanPendingOrders(reason);
     }
   // Retry every tick during the pre-close window until all targeted positions are gone.
   FlattenSessionPositions(reason);
  }

// Rule IDs: visual-1, visual-2, visual-3
bool ZoneVisualEnabled()
  {
   bool is_tester=(bool)MQLInfoInteger(MQL_TESTER);
   bool is_visual=(bool)MQLInfoInteger(MQL_VISUAL_MODE);
   return ((is_tester && is_visual) || (!is_tester && InpShowZonesOnLiveChart));
  }

bool SignalVisualEnabled()
  {
   bool is_tester=(bool)MQLInfoInteger(MQL_TESTER);
   bool is_visual=(bool)MQLInfoInteger(MQL_VISUAL_MODE);
   return ((is_tester && is_visual) || (!is_tester && InpShowSignalTextOnLiveChart));
  }

string VisualPrice(double p)
  {
   if(p<=0.0) return "N/A";
   return DoubleToString(p,_Digits);
  }

string VisualTimeHM(datetime t)
  {
   return TimeToString(t,TIME_MINUTES);
  }

string BuildSignalLabel(string signal,datetime when,string zone_id,string lineage="")
  {
   if(StringLen(lineage)>0)
     {
      if(StringFind(signal,"BO-")==0) return StringFormat("%s %s %s %s",lineage,signal,VisualTimeHM(when),zone_id);
      if(StringFind(signal,"PB-")==0) return StringFormat("%s<-%s %s %s",signal,lineage,VisualTimeHM(when),zone_id);
     }
   return StringFormat("%s %s %s",signal,VisualTimeHM(when),zone_id);
  }

double VisualLabelOffset(string signal)
  {
   // Separate signal families into visual lanes; display-only, no trading effect.
   if(StringFind(signal,"PB-")==0) return MathMax(1.10,110.0*_Point);
   if(StringFind(signal,"BO-")==0) return MathMax(0.70,70.0*_Point);
   return MathMax(0.35,35.0*_Point); // Reversal
  }

int VisualLabelTimeShift(string signal)
  {
   if(StringFind(signal,"PB-")==0) return 180; // +3 min
   if(StringFind(signal,"BO-")==0) return 90;  // +1.5 min
   return 0;
  }

void SetObjectTooltip(string name,string tooltip)
  {
   ObjectSetString(0,name,OBJPROP_TOOLTIP,tooltip);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,true);
   ObjectSetInteger(0,name,OBJPROP_SELECTED,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,false);
  }

color SignalColor(string signal)
  {
   if(signal=="R-B")  return clrLime;
   if(signal=="R-S")  return clrRed;
   if(signal=="BO-B") return clrAqua;
   if(signal=="BO-S") return clrMagenta;
   if(signal=="PB-B") return clrBlue;
   if(signal=="PB-S") return clrOrange;
   return clrWhite;
  }

bool SignalIsBuy(string signal)
  {
   return (signal=="R-B" || signal=="BO-B" || signal=="PB-B");
  }

// Required signal marker for Manual Validation Day.
// visual-2: object name and tooltip both carry event_id for Chart<->Journal reconciliation.
void DrawSignalEvent(string event_id,datetime when,double price,string signal,string zone_id,
                     string entry_type,double sl,double tp,string detail,string lineage="")
  {
   if(!SignalVisualEnabled()) return;

   color c=SignalColor(signal);
   string tooltip=StringFormat("Event: %s\nSignal: %s\nZone: %s\nTime: %s\nTrend: %s\nEntry type: %s\nPrice: %s\nSL: %s\nTP: %s",
                               event_id,signal,zone_id,TimeToString(when,TIME_DATE|TIME_SECONDS),
                               TrendToString(g_trend),entry_type,VisualPrice(price),VisualPrice(sl),VisualPrice(tp));
   if(StringLen(lineage)>0) tooltip+="\nBreakout lineage: "+lineage;
   if(StringLen(detail)>0) tooltip+="\n"+detail;

   string marker=g_visual_prefix+"SIG_MARK_"+event_id;
   if(ObjectCreate(0,marker,OBJ_ARROW,0,when,price))
     {
      ObjectSetInteger(0,marker,OBJPROP_COLOR,c);
      ObjectSetInteger(0,marker,OBJPROP_WIDTH,2);
      ObjectSetInteger(0,marker,OBJPROP_ARROWCODE,SignalIsBuy(signal)?233:234);
      SetObjectTooltip(marker,tooltip);
     }

   double offset=VisualLabelOffset(signal);
   double label_price=price+(SignalIsBuy(signal)?-offset:offset);
   datetime label_time=when+VisualLabelTimeShift(signal);
   string label=g_visual_prefix+"SIG_TXT_"+event_id;
   if(ObjectCreate(0,label,OBJ_TEXT,0,label_time,label_price))
     {
      ObjectSetString(0,label,OBJPROP_TEXT,BuildSignalLabel(signal,when,zone_id,lineage));
      ObjectSetInteger(0,label,OBJPROP_COLOR,c);
      ObjectSetInteger(0,label,OBJPROP_FONTSIZE,8);
      ObjectSetInteger(0,label,OBJPROP_ANCHOR,SignalIsBuy(signal)?ANCHOR_LEFT_UPPER:ANCHOR_LEFT_LOWER);
      SetObjectTooltip(label,tooltip);
     }
  }

// Extra debug-only label. Required Zone/Signal visuals do NOT depend on this.
void DrawEvent(string event_id,datetime when,double price,string text)
  {
   if(!InpDebugVisual) return;
   string name=g_visual_prefix+"DBG_"+event_id;
   if(ObjectCreate(0,name,OBJ_TEXT,0,when,price))
     {
      ObjectSetString(0,name,OBJPROP_TEXT,event_id+" "+text);
      ObjectSetInteger(0,name,OBJPROP_COLOR,clrWhite);
      ObjectSetInteger(0,name,OBJPROP_FONTSIZE,8);
      ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_LEFT_LOWER);
      SetObjectTooltip(name,event_id+" "+text);
     }
  }

void DeleteVisuals()
  {
   int total=ObjectsTotal(0,0,-1);
   for(int i=total-1;i>=0;i--)
     {
      string n=ObjectName(0,i,0,-1);
      if(StringFind(n,g_visual_prefix)==0) ObjectDelete(0,n);
     }
  }

//+------------------------------------------------------------------+
//| Environment validation                                           |
//+------------------------------------------------------------------+
// Rule ID: a-4
bool ValidateTimeframe()
  {
   if(_Period!=PERIOD_M15)
     {
      WriteJournal("a-4","TF_REJECTED","","","",0,0,0,0,0,0,0,"Required timeframe is M15");
      return false;
     }
   WriteJournal("a-4","TF_VALIDATED","","","",0,0,0,0,0,0,0,"M15");
   return true;
  }

// Rule ID: S1 Hedging-only execution decision
bool ValidateAccountMode()
  {
   long mode=AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(mode!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      WriteJournal("S1-HEDGING","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"S1 requires hedging account mode");
      return false;
     }
   WriteJournal("S1-HEDGING","ACCOUNT_MODE_VALIDATED","","","",0,0,0,0,0,0,0,"Hedging");
   return true;
  }

// Rule IDs: b-21, b-22 + TEST-HARNESS. Baseline is 0.01 lot; test-only volume override is explicit and never auto-adjusted.
bool ValidateVolumeCompatibility()
  {
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0 || InpTestVolumeLot<vmin-1e-12 || InpTestVolumeLot>vmax+1e-12)
     {
      WriteJournal("b-21/b-22","TEST_CONFIGURATION_ERROR","","","",InpTestVolumeLot,0,0,0,0,0,0,StringFormat("test volume %.4f unsupported min=%.4f max=%.4f step=%.4f",InpTestVolumeLot,vmin,vmax,step));
      return false;
     }
   double units=InpTestVolumeLot/step;
   if(MathAbs(units-MathRound(units))>1e-8)
     {
      WriteJournal("b-21/b-22","TEST_CONFIGURATION_ERROR","","","",InpTestVolumeLot,0,0,0,0,0,0,StringFormat("test volume %.4f not aligned to volume step %.4f",InpTestVolumeLot,step));
      return false;
     }
   MqlTick tick;
   double test_profit=0.0;
   if(!SymbolInfoTick(_Symbol,tick) || !OrderCalcProfit(ORDER_TYPE_BUY,_Symbol,InpTestVolumeLot,tick.ask,tick.ask+1.0,test_profit))
     {
      WriteJournal("b-22","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"cannot validate b-22 $1 move PnL with OrderCalcProfit");
      return false;
     }
   double expected_profit=(InpTestVolumeLot/0.01);
   if(MathAbs(test_profit-expected_profit)>0.01)
     {
      WriteJournal("b-22/TEST-HARNESS","TEST_CONFIGURATION_ERROR","","","",test_profit,0,0,0,0,0,0,
                   StringFormat("volume/PnL scaling mismatch: lot=%.4f +$1 move=%.4f %s expected=%.4f",InpTestVolumeLot,test_profit,AccountInfoString(ACCOUNT_CURRENCY),expected_profit));
      return false;
     }
   WriteJournal("b-21/b-22/TEST-HARNESS","VOLUME_SET","","","",InpTestVolumeLot,test_profit,0,0,0,0,0,
                StringFormat("test volume=%.4f; $1 move PnL=%.4f; baseline 0.01 lot preserved when input=0.01",InpTestVolumeLot,test_profit));
   return true;
  }

//+------------------------------------------------------------------+
//| Zone data module                                                 |
//+------------------------------------------------------------------+
// Rule IDs: a-5, a-7
bool NormalizeZone(double raw_low,double raw_high,double &zone_low,double &zone_high,bool &swapped)
  {
   swapped=false;
   if(raw_low<=0.0 || raw_high<=0.0) return false;
   zone_low=MathMin(raw_low,raw_high);
   zone_high=MathMax(raw_low,raw_high);
   swapped=(raw_low>raw_high);
   return true;
  }

bool ParseEnabled(string s)
  {
   s=Lower(Trim(s));
   if(s=="false" || s=="0" || s=="no" || s=="off") return false;
   return true;
  }

bool ValidPriority(string p)
  {
   p=Lower(Trim(p));
   return (p=="high" || p=="normal");
  }

bool ValidDateKey(string d,datetime &out_day)
  {
   d=Trim(d);
   out_day=StringToTime(d+" 00:00");
   if(out_day<=0) return false;
   return (TimeToString(out_day,TIME_DATE)==d);
  }

// Rule IDs: a-5, a-11, ranges.csv
bool LoadAllRawZones()
  {
   ArrayResize(g_raw_zones,0);
   int h=FileOpen(InpRangesFile,HarnessFileOpenFlags(FILE_READ|FILE_CSV|FILE_ANSI),',',CP_UTF8);
   if(h==INVALID_HANDLE)
     {
      WriteJournal("a-5","ZONE_INVALID","","","",0,0,0,0,0,0,0,"DATA_ERROR: cannot open ranges file: "+InpRangesFile);
      return false;
     }

   int row=0;
   while(!FileIsEnding(h))
     {
      string s_date=FileReadString(h);
      if(FileIsEnding(h) && Trim(s_date)=="") break;
      string s_lower=FileReadString(h);
      string s_upper=FileReadString(h);
      string s_priority=FileReadString(h);
      string s_enabled=FileReadString(h);
      string s_note=FileReadString(h);
      row++;

      s_date=Trim(s_date);
      if(row==1 && StringFind(Lower(s_date),"date")>=0) continue;
      if(s_date=="") continue;
      if(!ParseEnabled(s_enabled)) continue;

      datetime d=0;
      double raw_low=StringToDouble(Trim(s_lower));
      double raw_high=StringToDouble(Trim(s_upper));
      double low=0,high=0;
      bool swapped=false;
      string priority=Lower(Trim(s_priority));

      if(!ValidDateKey(s_date,d) || !ValidPriority(priority) || !NormalizeZone(raw_low,raw_high,low,high,swapped))
        {
         WriteJournal("a-5/a-11","ZONE_INVALID","","","",0,0,0,0,0,0,0,StringFormat("DATA_ERROR row=%d date=%s lower=%s upper=%s priority=%s",row,s_date,s_lower,s_upper,s_priority));
         continue;
        }

      if(swapped)
         WriteJournal("a-5","ZONE_NORMALIZED","","","",low,high,0,0,0,0,0,StringFormat("row=%d lower/upper swapped",row));

      int n=ArraySize(g_raw_zones);
      ArrayResize(g_raw_zones,n+1);
      g_raw_zones[n].day=d;
      g_raw_zones[n].day_key=s_date;
      g_raw_zones[n].low=low;
      g_raw_zones[n].high=high;
      g_raw_zones[n].priority=priority;
      g_raw_zones[n].note=s_note;
     }
   FileClose(h);
   WriteJournal("a-5","ZONES_LOADED","","","",0,0,0,0,0,0,0,StringFormat("raw_valid_rows=%d",ArraySize(g_raw_zones)));
   return true;
  }

// Rule ID: a-5
void SortZones(ZoneRuntime &arr[])
  {
   int n=ArraySize(arr);
   for(int i=0;i<n-1;i++)
      for(int j=i+1;j<n;j++)
         if(arr[j].low<arr[i].low)
           {
            ZoneRuntime tmp=arr[i]; arr[i]=arr[j]; arr[j]=tmp;
           }
  }

// Rule IDs: a-8, a-9
void MergeZones(ZoneRuntime &arr[])
  {
   int n=ArraySize(arr);
   if(n<=1) return;
   ZoneRuntime out[];
   ArrayResize(out,0);
   for(int i=0;i<n;i++)
     {
      if(ArraySize(out)==0)
        {
         ArrayResize(out,1);
         out[0]=arr[i];
         continue;
        }
      int k=ArraySize(out)-1;
      double gap=arr[i].low-out[k].high;
      if(gap<1.5)
        {
         double old_low=out[k].low,old_high=out[k].high;
         out[k].low=MathMin(out[k].low,arr[i].low);
         out[k].high=MathMax(out[k].high,arr[i].high);
         out[k].id=out[k].id+"&"+arr[i].id;
         if(arr[i].priority=="high") out[k].priority="high";
         WriteJournal("a-8/a-9","ZONE_MERGED",out[k].id,"","",old_low,old_high,out[k].low,out[k].high,0,0,0,StringFormat("gap=%.2f",gap));
        }
      else
        {
         int m=ArraySize(out); ArrayResize(out,m+1); out[m]=arr[i];
        }
     }
   ArrayResize(arr,ArraySize(out));
   for(int z=0;z<ArraySize(out);z++) arr[z]=out[z];
  }

// Rule ID: visual-1
void DrawCurrentZones(datetime day_start)
  {
   if(!ZoneVisualEnabled()) return;
   datetime day_end=day_start+86399;
   for(int i=0;i<ArraySize(g_zones);i++)
     {
      color c=(g_zones[i].priority=="high" ? clrOrange : clrDodgerBlue);
      string base=g_visual_prefix+"ZONE_"+g_day_key+"_"+g_zones[i].id;
      string tooltip=StringFormat("Zone: %s\nPriority: %s\nLow: %s\nHigh: %s\nBroker day: %s",
                                  g_zones[i].id,g_zones[i].priority,
                                  DoubleToString(g_zones[i].low,_Digits),
                                  DoubleToString(g_zones[i].high,_Digits),g_day_key);

      string rect=base+"_RECT";
      if(ObjectCreate(0,rect,OBJ_RECTANGLE,0,day_start,g_zones[i].low,day_end,g_zones[i].high))
        {
         ObjectSetInteger(0,rect,OBJPROP_COLOR,c);
         ObjectSetInteger(0,rect,OBJPROP_BACK,true);
         ObjectSetInteger(0,rect,OBJPROP_FILL,false);
         ObjectSetInteger(0,rect,OBJPROP_WIDTH,1);
         SetObjectTooltip(rect,tooltip);
        }

      string low_line=base+"_LOW";
      if(ObjectCreate(0,low_line,OBJ_TREND,0,day_start,g_zones[i].low,day_end,g_zones[i].low))
        {
         ObjectSetInteger(0,low_line,OBJPROP_COLOR,c);
         ObjectSetInteger(0,low_line,OBJPROP_WIDTH,2);
         ObjectSetInteger(0,low_line,OBJPROP_STYLE,STYLE_SOLID);
         ObjectSetInteger(0,low_line,OBJPROP_RAY_LEFT,false);
         ObjectSetInteger(0,low_line,OBJPROP_RAY_RIGHT,false);
         SetObjectTooltip(low_line,tooltip+"\nBoundary: LOW");
        }

      string high_line=base+"_HIGH";
      if(ObjectCreate(0,high_line,OBJ_TREND,0,day_start,g_zones[i].high,day_end,g_zones[i].high))
        {
         ObjectSetInteger(0,high_line,OBJPROP_COLOR,c);
         ObjectSetInteger(0,high_line,OBJPROP_WIDTH,2);
         ObjectSetInteger(0,high_line,OBJPROP_STYLE,STYLE_SOLID);
         ObjectSetInteger(0,high_line,OBJPROP_RAY_LEFT,false);
         ObjectSetInteger(0,high_line,OBJPROP_RAY_RIGHT,false);
         SetObjectTooltip(high_line,tooltip+"\nBoundary: HIGH");
        }

      double mid=(g_zones[i].low+g_zones[i].high)/2.0;
      string lbl=base+"_LBL";
      if(ObjectCreate(0,lbl,OBJ_TEXT,0,day_start+4*3600,mid))
        {
         ObjectSetString(0,lbl,OBJPROP_TEXT,StringFormat("%s %s-%s",g_zones[i].id,
                         DoubleToString(g_zones[i].low,_Digits),DoubleToString(g_zones[i].high,_Digits)));
         ObjectSetInteger(0,lbl,OBJPROP_COLOR,c);
         ObjectSetInteger(0,lbl,OBJPROP_FONTSIZE,8);
         SetObjectTooltip(lbl,tooltip);
        }
     }
   ChartRedraw(0);
  }

// Rule IDs: a-5..a-9, a-11
bool LoadZonesForDay(string day_key)
  {
   ArrayResize(g_zones,0);
   g_day_valid=false;
   for(int i=0;i<ArraySize(g_raw_zones);i++)
     {
      if(g_raw_zones[i].day_key!=day_key) continue;
      int n=ArraySize(g_zones); ArrayResize(g_zones,n+1);
      g_zones[n].day_key=day_key;
      g_zones[n].id="";
      g_zones[n].low=g_raw_zones[i].low;
      g_zones[n].high=g_raw_zones[i].high;
      g_zones[n].priority=g_raw_zones[i].priority;
      g_zones[n].engaged_buy=false;
      g_zones[n].engaged_sell=false;
      g_zones[n].reversal_usage=USAGE_UNUSED;
      g_zones[n].reversal_fill_count=0;
      g_zones[n].pullback_fill_count=0;
      g_zones[n].last_reversal_buy_signal_bar=0;
      g_zones[n].last_reversal_sell_signal_bar=0;
     }

   SortZones(g_zones);
   for(int j=0;j<ArraySize(g_zones);j++) g_zones[j].id=StringFormat("R%d",j+1);
   MergeZones(g_zones);

   g_day_valid=(ArraySize(g_zones)>0);
   WriteJournal("a-5/a-11","ZONES_LOADED","","","",0,0,0,0,0,0,0,StringFormat("day=%s final_zone_count=%d",day_key,ArraySize(g_zones)));
   datetime ds=StringToTime(day_key+" 00:00");
   DrawCurrentZones(ds);
   return g_day_valid;
  }

int FindZoneIndex(string day_key,string zone_id)
  {
   if(day_key!=g_day_key) return -1;
   for(int i=0;i<ArraySize(g_zones);i++) if(g_zones[i].id==zone_id) return i;
   return -1;
  }

//+------------------------------------------------------------------+
//| Candle + trend                                                   |
//+------------------------------------------------------------------+
// Rule IDs: a-1..a-3
void ClassifyCandle(datetime bar_time,double o,double h,double l,double c)
  {
   string cls="DOJI";
   if(c>o) cls="BULLISH";
   else if(c<o) cls="BEARISH";
   WriteJournal("a-1/a-2/a-3","CANDLE_CLASSIFIED","","","",o,c,l,h,0,0,0,StringFormat("bar=%s class=%s",TimeToString(bar_time,TIME_DATE|TIME_MINUTES),cls));
  }

// Rule ID: trend-1
bool UpdateTrendReference()
  {
   MqlRates rates[];
   ArrayResize(rates,3);
   int copied=CopyRates(_Symbol,PERIOD_M15,1,3,rates);
   if(copied<3) return false;
   g_ref_high=rates[0].high;
   g_ref_low=rates[0].low;
   for(int i=1;i<3;i++)
     {
      g_ref_high=MathMax(g_ref_high,rates[i].high);
      g_ref_low=MathMin(g_ref_low,rates[i].low);
     }
   WriteJournal("trend-1","TREND_REFERENCE_UPDATED","","","",g_ref_low,g_ref_high,0,0,0,0,0,"High[1..3]/Low[1..3]");
   return true;
  }

// Rule ID: trend-1
void UpdateTrendState(double bid)
  {
   ENUM_TREND_STATE old=g_trend;
   if(bid>g_ref_high) g_trend=TREND_UP;
   else if(bid<g_ref_low) g_trend=TREND_DOWN;
   if(old!=g_trend)
      WriteJournal("trend-1","TREND_STATE_CHANGED","","","",bid,0,g_ref_low,g_ref_high,0,0,0,TrendToString(old)+" -> "+TrendToString(g_trend));
  }

// Rule IDs: b-3, ZONE_ENGAGED decision
void ResetEngagementForCurrentBar(double bar_open)
  {
   for(int i=0;i<ArraySize(g_zones);i++)
     {
      g_zones[i].engaged_buy=(bar_open>=g_zones[i].low && bar_open<=g_zones[i].high);
      g_zones[i].engaged_sell=g_zones[i].engaged_buy;
      if(g_zones[i].engaged_buy)
         WriteJournal("b-3","ZONE_ENGAGED",g_zones[i].id,"","",bar_open,0,0,0,0,0,0,"bar opened inside zone");
     }
  }

// Rule IDs: trend-2, b-1, confirmed single-tick multi-zone policy
int CountDirectionalZoneCrosses(double prev_bid,double bid)
  {
   int count=0;
   for(int i=0;i<ArraySize(g_zones);i++)
     {
      if(prev_bid<g_zones[i].low && bid>=g_zones[i].low) count++;
      else if(prev_bid>g_zones[i].high && bid<=g_zones[i].high) count++;
     }
   return count;
  }

void UpdateZoneEngagement(double prev_bid,double bid,bool multi_zone_tick_gap)
  {
   for(int i=0;i<ArraySize(g_zones);i++)
     {
      if(multi_zone_tick_gap)
        {
         if(bid>=g_zones[i].low && bid<=g_zones[i].high)
           {
            g_zones[i].engaged_buy=true;
            g_zones[i].engaged_sell=true;
           }
         continue;
        }
      if(!g_zones[i].engaged_buy && prev_bid<g_zones[i].low && bid>=g_zones[i].low)
        {
         g_zones[i].engaged_buy=true;
         WriteJournal("b-3","ZONE_ENGAGED",g_zones[i].id,"","",bid,0,0,0,0,0,0,"entered/crossed zone from below");
        }
      if(!g_zones[i].engaged_sell && prev_bid>g_zones[i].high && bid<=g_zones[i].high)
        {
         g_zones[i].engaged_sell=true;
         WriteJournal("b-3","ZONE_ENGAGED",g_zones[i].id,"","",bid,0,0,0,0,0,0,"entered/crossed zone from above");
        }
     }
  }

//+------------------------------------------------------------------+
//| SL/TP and request tracking                                       |
//+------------------------------------------------------------------+
int AdjacentZoneIndex(int zone_index,bool upper)
  {
   int idx=(upper ? zone_index+1 : zone_index-1);
   if(idx<0 || idx>=ArraySize(g_zones)) return -1;
   return idx;
  }

// Rule IDs: b-29, b-30, C1 v9
bool CalculateRBasedSLTP(int zone_index,bool buy,double entry,double &sl,double &tp,double &r0,string &target_zone_id,string &reason)
  {
   sl=0.0; tp=0.0; r0=0.0; target_zone_id=""; reason="";
   if(zone_index<0 || zone_index>=ArraySize(g_zones)) { reason="zone index unavailable"; return false; }
   if(InpRCapUSD<=0.0) { reason="R_CAP must be > 0"; return false; }

   if(buy)
     {
      int stop_idx=zone_index-1;
      if(stop_idx<0) { reason="C1 v9 missing lower stop zone"; return false; }
      sl=MathMax(g_zones[stop_idx].high,entry-InpRCapUSD);
      r0=entry-sl;
      if(r0<=0.0) { reason="invalid non-positive R0 for Buy"; return false; }
      for(int j=zone_index+1;j<ArraySize(g_zones);j++)
        {
         if(g_zones[j].low-entry>=r0)
           {
            tp=g_zones[j].low;
            target_zone_id=g_zones[j].id;
            break;
           }
        }
      if(tp<=0.0) { reason="C1 v9 no target zone at least 1R above"; return false; }
     }
   else
     {
      int stop_idx=zone_index+1;
      if(stop_idx>=ArraySize(g_zones)) { reason="C1 v9 missing upper stop zone"; return false; }
      sl=MathMin(g_zones[stop_idx].low,entry+InpRCapUSD);
      r0=sl-entry;
      if(r0<=0.0) { reason="invalid non-positive R0 for Sell"; return false; }
      for(int j=zone_index-1;j>=0;j--)
        {
         if(entry-g_zones[j].high>=r0)
           {
            tp=g_zones[j].high;
            target_zone_id=g_zones[j].id;
            break;
           }
        }
      if(tp<=0.0) { reason="C1 v9 no target zone at least 1R below"; return false; }
     }

   sl=NormalizeDouble(sl,_Digits);
   tp=NormalizeDouble(tp,_Digits);
   r0=MathAbs(entry-sl);
   WriteJournal("b-29/b-30","RISK_MODEL_READY",g_zones[zone_index].id,buy?"BUY":"SELL","",entry,0,sl,tp,0,0,0,
                StringFormat("R_CAP=%.2f R0=%.5f target_zone=%s",InpRCapUSD,r0,target_zone_id));
   return true;
  }

int AddRequestMeta(string comment,double requested,double sl,double tp,double r0,string target_zone_id,string parent_breakout_id="",int reversal_ordinal=0)
  {
   int n=ArraySize(g_requests); ArrayResize(g_requests,n+1);
   g_requests[n].active=true;
   g_requests[n].comment=comment;
   g_requests[n].requested_price=requested;
   g_requests[n].sl=sl;
   g_requests[n].tp=tp;
   g_requests[n].r0=r0;
   g_requests[n].target_zone_id=target_zone_id;
   g_requests[n].parent_breakout_id=parent_breakout_id;
   g_requests[n].reversal_ordinal=reversal_ordinal;
   return n;
  }

void DeactivateRequest(int idx)
  {
   if(idx>=0 && idx<ArraySize(g_requests)) g_requests[idx].active=false;
  }

int FindRequest(string comment)
  {
   for(int i=ArraySize(g_requests)-1;i>=0;i--)
      if(g_requests[i].active && g_requests[i].comment==comment) return i;
   return -1;
  }

string MakeComment(string type,string day_key,string zone_id,bool buy)
  {
   string d=day_key; StringReplace(d,".","");
   return type+"|"+d+"|"+zone_id+"|"+(buy?"B":"S");
  }

bool ParseComment(string c,string &type,string &day_key,string &zone_id,bool &buy)
  {
   string parts[];
   ushort sep=StringGetCharacter("|",0);
   int n=StringSplit(c,sep,parts);
   if(n<4) return false;
   type=parts[0];
   string d=parts[1];
   if(StringLen(d)!=8) return false;
   day_key=StringSubstr(d,0,4)+"."+StringSubstr(d,4,2)+"."+StringSubstr(d,6,2);
   zone_id=parts[2];
   buy=(parts[3]=="B");
   return true;
  }

//+------------------------------------------------------------------+
//| Position / usage tracking                                        |
//+------------------------------------------------------------------+
ulong FindPositionTicketByIdentifier(ulong position_id)
  {
   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if((ulong)PositionGetInteger(POSITION_IDENTIFIER)==position_id && (ulong)PositionGetInteger(POSITION_MAGIC)==EA_MAGIC)
         return ticket;
     }
   return 0;
  }

bool HasOpenPositionWithComment(string comment)
  {
   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=EA_MAGIC) continue;
      if(PositionGetString(POSITION_COMMENT)==comment) return true;
     }
   return false;
  }

int FindPositionTrack(ulong position_id)
  {
   for(int i=0;i<ArraySize(g_positions);i++) if(g_positions[i].active && g_positions[i].position_id==position_id) return i;
   return -1;
  }

bool HasActivePullbackPosition(string day_key,string zone_id,bool buy)
  {
   for(int i=0;i<ArraySize(g_positions);i++)
      if(g_positions[i].active && g_positions[i].trade_type=="P" && g_positions[i].day_key==day_key &&
         g_positions[i].zone_id==zone_id && g_positions[i].buy==buy) return true;
   return false;
  }

void MarkZoneUsageActive(string day_key,string zone_id,string type)
  {
   if(type!="R") return;
   int z=FindZoneIndex(day_key,zone_id);
   if(z<0) return;
   g_zones[z].reversal_usage=USAGE_ACTIVE;
  }

void MarkZoneUsageConsumed(string day_key,string zone_id,string type)
  {
   if(type!="R") return;
   int z=FindZoneIndex(day_key,zone_id);
   if(z<0) return;
   int allowed=AllowedReversalCountForZone(z);
   int executed=g_zones[z].reversal_fill_count;
   if(executed>=allowed)
     {
      g_zones[z].reversal_usage=USAGE_CONSUMED;
      WriteJournal("TEST-HIGH-R/b-24/b-26","ZONE_CONSUMED",zone_id,"R","",0,0,0,0,0,0,0,
                   StringFormat("reversal daily max reached; executed=%d allowed=%d",executed,allowed));
     }
   else
     {
      g_zones[z].reversal_usage=USAGE_UNUSED;
      WriteJournal("TEST-HIGH-R","HIGH_REVERSAL_SLOT_CLOSED",zone_id,"R","",0,0,0,0,0,0,0,
                   StringFormat("reversal closed; executed=%d allowed=%d remaining=%d",executed,allowed,allowed-executed));
     }
  }

void CompletePullbackCycleOnFill(string day_key,string zone_id,bool buy)
  {
   int idx=FindActiveCycle(day_key,zone_id,buy);
   if(idx>=0)
     {
      g_cycles[idx].active=false;
      g_cycles[idx].order_ticket=0;
     }
  }

// Rule IDs: b-24..b-26, b-29
void AddPositionTrack(ulong position_id,string day_key,string zone_id,string type,bool buy,
                      double risk_anchor,double actual_fill,double initial_sl,double tp,double r0,string target_zone_id,
                      string parent_breakout_id="",bool stacked_pullback=false,int reversal_ordinal=0)
  {
   if(FindPositionTrack(position_id)>=0) return;
   int n=ArraySize(g_positions); ArrayResize(g_positions,n+1);
   g_positions[n].active=true;
   g_positions[n].position_id=position_id;
   g_positions[n].position_ticket=FindPositionTicketByIdentifier(position_id);
   g_positions[n].day_key=day_key;
   g_positions[n].zone_id=zone_id;
   g_positions[n].trade_type=type;
   g_positions[n].buy=buy;
   g_positions[n].risk_anchor_entry=risk_anchor;
   g_positions[n].actual_fill=actual_fill;
   g_positions[n].initial_sl=initial_sl;
   g_positions[n].tp=tp;
   g_positions[n].r0=r0;
   g_positions[n].r_stage=0;
   g_positions[n].desired_sl=0.0;
   g_positions[n].sl_retry_logged=false;
   g_positions[n].target_zone_id=target_zone_id;
   g_positions[n].parent_breakout_id=parent_breakout_id;
   g_positions[n].stacked_pullback=stacked_pullback;
   g_positions[n].reversal_ordinal=reversal_ordinal;
   g_positions[n].session_close_requested=false;
   g_positions[n].session_close_reason="";
   g_positions[n].last_carry_audit_key="";
   if(type=="R")
     {
      int z=FindZoneIndex(day_key,zone_id);
      if(z>=0) g_zones[z].reversal_fill_count++;
     }
   if(type=="P")
     {
      int z=FindZoneIndex(day_key,zone_id);
      if(z>=0) g_zones[z].pullback_fill_count++;
     }
   MarkZoneUsageActive(day_key,zone_id,type);
   if(type=="P") CompletePullbackCycleOnFill(day_key,zone_id,buy);
  }

//+------------------------------------------------------------------+
//| MVP simple finalist context helpers                              |
//+------------------------------------------------------------------+
int CountEAOpenPositions()
  {
   int n=0;
   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=EA_MAGIC) continue;
      n++;
     }
   return n;
  }

bool MVPHasLiveSlot()
  { return (InpMaxLivePositions>0 && CountEAOpenPositions()<InpMaxLivePositions); }

double MVPDirectionalFreeSpace(int zone_index,bool buy)
  {
   if(zone_index<0 || zone_index>=ArraySize(g_zones)) return 0.0;
   if(buy)
     {
      if(zone_index+1>=ArraySize(g_zones)) return DBL_MAX;
      return MathMax(0.0,g_zones[zone_index+1].low-g_zones[zone_index].high);
     }
   if(zone_index<=0) return DBL_MAX;
   return MathMax(0.0,g_zones[zone_index].low-g_zones[zone_index-1].high);
  }

bool MVPPullbackAllowed(int zone_index,bool buy,string &reason)
  {
   reason="";
   if(!MVPSimpleActive()) return true;
   if(zone_index<0 || zone_index>=ArraySize(g_zones)) { reason="zone unavailable"; return false; }
   string pri=Lower(g_zones[zone_index].priority);
   if(pri!="high" && g_zones[zone_index].pullback_fill_count>=1) { reason="Normal PB max1 reached"; return false; }
   double fs=MVPDirectionalFreeSpace(zone_index,buy);
   if(fs<15.0) { reason=StringFormat("PB free_space %.5f < 15",fs); return false; }
   return true;
  }

bool MVPReversalAllowed(int zone_index,bool buy,string &reason)
  {
   reason="";
   if(!MVPSimpleActive()) return true;
   if(InpMVPSimpleProfile==MVP_SIMPLE_PB_ONLY_SPACE15) { reason="PB-only finalist"; return false; }
   if(zone_index<0 || zone_index>=ArraySize(g_zones)) { reason="zone unavailable"; return false; }
   if(Lower(g_zones[zone_index].priority)!="high") { reason="Reversal High-only"; return false; }
   if(InpMVPSimpleProfile==MVP_SIMPLE_SPACE15_HIGHSPACE_H2)
     {
      double fs=MVPDirectionalFreeSpace(zone_index,buy);
      if(fs<15.0) { reason=StringFormat("Reversal free_space %.5f < 15",fs); return false; }
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Reversal                                                         |
//+------------------------------------------------------------------+
// Rule ID: b-31. One reversal signal per M15 candle + Zone + direction.
// Same-direction recrosses inside the same candle are raw price noise, not new strategy signals.
// The opposite direction remains independent because trend-1 permits a genuine intrabar trend flip.
bool ClaimReversalSignalSlot(int zone_index,bool buy)
  {
   if(zone_index<0 || zone_index>=ArraySize(g_zones) || g_bar_time<=0) return false;
   if(buy)
     {
      if(g_zones[zone_index].last_reversal_buy_signal_bar==g_bar_time) return false;
      g_zones[zone_index].last_reversal_buy_signal_bar=g_bar_time;
     }
   else
     {
      if(g_zones[zone_index].last_reversal_sell_signal_bar==g_bar_time) return false;
      g_zones[zone_index].last_reversal_sell_signal_bar=g_bar_time;
     }
   return true;
  }

bool IsHighPriorityZone(int zone_index)
  {
   if(zone_index<0 || zone_index>=ArraySize(g_zones)) return false;
   string p=g_zones[zone_index].priority;
   StringToLower(p);
   return (p=="high");
  }

int AllowedReversalCountForZone(int zone_index)
  {
   if(zone_index<0 || zone_index>=ArraySize(g_zones)) return 0;
   if(MVPSimpleActive())
     {
      if(!IsHighPriorityZone(zone_index)) return 0;
      return MVPSimpleHighMax();
     }
   if(IsHighPriorityZone(zone_index))
      return (InpHighReversalMaxPerDay>1 ? InpHighReversalMaxPerDay : 1);
   return 1;
  }

// TEST-HIGH-R only. Builds baseline b-30 risk first, then expands the initial
// stop distance by InpHighReversalSLMultiplier for High-zone Reversals.
// The resulting expanded risk becomes this position's fixed R0; target
// qualification and all b-29 stages use the expanded R0.
bool CalculateExperimentalHighReversalSLTP(int zone_index,bool buy,double entry,double &sl,double &tp,double &r0,
                                           string &target_zone_id,string &reason,double &r_base)
  {
   sl=0.0; tp=0.0; r0=0.0; r_base=0.0; target_zone_id=""; reason="";
   if(zone_index<0 || zone_index>=ArraySize(g_zones)) { reason="zone index unavailable"; return false; }
   if(InpRCapUSD<=0.0) { reason="R_CAP must be > 0"; return false; }
   if(InpHighReversalSLMultiplier<=0.0) { reason="experimental SL multiplier must be > 0"; return false; }

   double base_sl=0.0;
   if(buy)
     {
      int stop_idx=zone_index-1;
      if(stop_idx<0) { reason="C1 v9 missing lower stop zone"; return false; }
      base_sl=MathMax(g_zones[stop_idx].high,entry-InpRCapUSD);
      r_base=entry-base_sl;
      if(r_base<=0.0) { reason="invalid non-positive base R for Buy"; return false; }

      r0=InpHighReversalSLMultiplier*r_base;
      sl=entry-r0;
      for(int j=zone_index+1;j<ArraySize(g_zones);j++)
        {
         if(g_zones[j].low-entry>=r0)
           {
            tp=g_zones[j].low;
            target_zone_id=g_zones[j].id;
            break;
           }
        }
      if(tp<=0.0) { reason="TEST-HIGH-R no target zone at least expanded 1R above"; return false; }
     }
   else
     {
      int stop_idx=zone_index+1;
      if(stop_idx>=ArraySize(g_zones)) { reason="C1 v9 missing upper stop zone"; return false; }
      base_sl=MathMin(g_zones[stop_idx].low,entry+InpRCapUSD);
      r_base=base_sl-entry;
      if(r_base<=0.0) { reason="invalid non-positive base R for Sell"; return false; }

      r0=InpHighReversalSLMultiplier*r_base;
      sl=entry+r0;
      for(int j=zone_index-1;j>=0;j--)
        {
         if(entry-g_zones[j].high>=r0)
           {
            tp=g_zones[j].high;
            target_zone_id=g_zones[j].id;
            break;
           }
        }
      if(tp<=0.0) { reason="TEST-HIGH-R no target zone at least expanded 1R below"; return false; }
     }

   sl=NormalizeDouble(sl,_Digits);
   tp=NormalizeDouble(tp,_Digits);
   r0=MathAbs(entry-sl);
   WriteJournal("TEST-HIGH-R/b-29/b-30","RISK_MODEL_READY",g_zones[zone_index].id,buy?"BUY":"SELL","",entry,0,sl,tp,0,0,0,
                StringFormat("HIGH_TEST multiplier=%.2f R_base=%.5f R0_exp=%.5f target_zone=%s",
                             InpHighReversalSLMultiplier,r_base,r0,target_zone_id));
   return true;
  }

// TEST-HARNESS / MVP-RISK: telemetry only. Does not block or modify execution.
void LogMarginPrecheck(bool buy,double price,string zone_id,string signal,string parent_breakout_id="")
  {
   double required=0.0;
   ENUM_ORDER_TYPE type=(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   bool ok=OrderCalcMargin(type,_Symbol,InpTestVolumeLot,price,required);
   double margin=AccountInfoDouble(ACCOUNT_MARGIN);
   double free_margin=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double level=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   string note=StringFormat("lot=%.4f required_new_margin=%s account_margin=%.2f free_margin=%.2f margin_level=%.2f",
                            InpTestVolumeLot,ok?DoubleToString(required,2):"N/A",margin,free_margin,level);
   WriteJournal("MVP-RISK/TEST-HARNESS","MARGIN_PRECHECK",zone_id,signal,"Telemetry",price,0,0,0,0,0,0,note,"",parent_breakout_id);
   WriteSummary("QA","MARGIN_PRECHECK",zone_id,signal,"Telemetry",price,0,0,0,0,0,false,0.0,note,"",parent_breakout_id);
  }

void LogMarginPostFill(string zone_id,string signal,ulong position_ticket,string parent_breakout_id="")
  {
   double margin=AccountInfoDouble(ACCOUNT_MARGIN);
   double free_margin=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double level=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   string note=StringFormat("lot=%.4f account_margin=%.2f free_margin=%.2f margin_level=%.2f",InpTestVolumeLot,margin,free_margin,level);
   WriteJournal("MVP-RISK/TEST-HARNESS","MARGIN_POST_FILL",zone_id,signal,"Telemetry",0,0,0,0,0,0,position_ticket,note,"",parent_breakout_id);
   WriteSummary("QA","MARGIN_POST_FILL",zone_id,signal,"Telemetry",0,0,0,0,0,position_ticket,false,0.0,note,"",parent_breakout_id);
  }

// Rule IDs: b-1, b-11, b-24, b-29, b-30, b-31, QA-R2
bool SendReversal(int zone_index,bool buy)
  {
   if(g_daily_stop || zone_index<0 || SessionBlocksReversalEntries()) return false;
   MqlTick tick; if(!SymbolInfoTick(_Symbol,tick)) return false;
   double requested=(buy ? tick.ask : tick.bid);
   string signal=(buy?"R-B":"R-S");

   string mvp_reason="";
   if(!MVPReversalAllowed(zone_index,buy,mvp_reason))
     {
      if(InpMVPProfileTelemetry) WriteSummary("MVP_FILTER","REVERSAL_BLOCKED_MVP_CONTEXT",g_zones[zone_index].id,signal,"Shadow",requested,0,0,0,0,0,false,0.0,mvp_reason);
      return false;
     }
   if(!MVPHasLiveSlot())
     {
      if(InpMVPProfileTelemetry) WriteSummary("MVP_FILTER","ENTRY_BLOCKED_POSITION_CAP",g_zones[zone_index].id,signal,"Market",requested,0,0,0,0,0,false,0.0,StringFormat("live=%d cap=%d",CountEAOpenPositions(),InpMaxLivePositions));
      return false;
     }

   // TEST-HIGH-R branch:
   // normal zones remain max 1 real Reversal/day;
   // high zones allow up to InpHighReversalMaxPerDay real Reversal fills/day.
   int allowed=AllowedReversalCountForZone(zone_index);
   int next_ordinal=g_zones[zone_index].reversal_fill_count+1;
   if(g_zones[zone_index].reversal_fill_count>=allowed)
     {
      if(InpQADiscoveryMode)
        {
         double sl2=0,tp2=0,r02=0,rbase2=0; string target2="",reason2="";
         bool high=IsHighPriorityZone(zone_index);
         bool theoretical_ok=(high ?
            CalculateExperimentalHighReversalSLTP(zone_index,buy,requested,sl2,tp2,r02,target2,reason2,rbase2) :
            CalculateRBasedSLTP(zone_index,buy,requested,sl2,tp2,r02,target2,reason2));
         string note=StringFormat("counted_in_pnl=false allowed=%d executed=%d theoretical=%s target=%s %s",
                                  allowed,g_zones[zone_index].reversal_fill_count,theoretical_ok?"true":"false",target2,reason2);
         WriteJournal("TEST-HIGH-R/b-24/QA-R2","SECONDARY_REVERSAL_CANDIDATE",g_zones[zone_index].id,signal,"Shadow",requested,0,sl2,tp2,0,0,0,note);
         WriteSummary("SECONDARY_REVERSAL","SECONDARY_REVERSAL_CANDIDATE",g_zones[zone_index].id,signal,"Shadow",
                      requested,0,sl2,tp2,r02,0,false,0.0,note,"","",false,next_ordinal);
        }
      else
         WriteJournal("TEST-HIGH-R/b-24","ZONE_USAGE_BLOCKED",g_zones[zone_index].id,"R","Market",0,0,0,0,0,0,0,
                      StringFormat("daily reversal max reached: allowed=%d executed=%d",allowed,g_zones[zone_index].reversal_fill_count));
      return false;
     }

   bool high=IsHighPriorityZone(zone_index);
   double sl=0,tp=0,r0=0,r_base=0; string target_zone="",reason="";
   bool risk_ok=(high ?
      CalculateExperimentalHighReversalSLTP(zone_index,buy,requested,sl,tp,r0,target_zone,reason,r_base) :
      CalculateRBasedSLTP(zone_index,buy,requested,sl,tp,r0,target_zone,reason));
   if(!risk_ok)
     {
      string ev=(StringFind(reason,"stop zone")>=0 ? "TRADE_REJECTED_NO_STOP_ZONE" : "TRADE_REJECTED_NO_1R_TARGET");
      WriteJournal("b-30",ev,g_zones[zone_index].id,signal,"Market",requested,0,0,0,0,0,0,reason);
      WriteSummary("SIGNAL",ev,g_zones[zone_index].id,signal,"Market",requested,0,0,0,0,0,false,0.0,reason);
      return false;
     }
   string comment=MakeComment("R",g_day_key,g_zones[zone_index].id,buy);
   int req=AddRequestMeta(comment,requested,sl,tp,r0,target_zone,"",next_ordinal);
   string reason_ready=(high ?
      StringFormat("TEST HIGH reversal_ordinal=%d/%d SLx=%.2f R_base=%.5f R0=%.5f target=%s",next_ordinal,allowed,InpHighReversalSLMultiplier,r_base,r0,target_zone) :
      StringFormat("reversal_ordinal=%d/%d directional touch + trend valid; R0=%.5f target=%s",next_ordinal,allowed,r0,target_zone));
   string eid=WriteJournal(high?"TEST-HIGH-R/b-1/b-11/b-29/b-30":"b-1/b-11/b-29/b-30","REVERSAL_SIGNAL",g_zones[zone_index].id,signal,"Market",requested,0,sl,tp,0,0,0,reason_ready);
   WriteSummary("SIGNAL","REVERSAL_SIGNAL",g_zones[zone_index].id,signal,"Market",requested,0,sl,tp,r0,0,false,0.0,reason_ready,"","",false,next_ordinal);
   DrawSignalEvent(eid,TimeCurrent(),requested,signal,g_zones[zone_index].id,
                   "Market",sl,tp,"Reversal entry request; R-based risk model");
   LogMarginPrecheck(buy,requested,g_zones[zone_index].id,signal);

   bool ok=(buy ? trade.Buy(InpTestVolumeLot,_Symbol,0.0,sl,tp,comment) : trade.Sell(InpTestVolumeLot,_Symbol,0.0,sl,tp,comment));
   uint rc=trade.ResultRetcode();
   if(!ok || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_DONE_PARTIAL))
     {
      DeactivateRequest(req);
      string ev=(rc==TRADE_RETCODE_NO_MONEY ? "EXECUTION_BLOCKED_MARGIN" : "ORDER_REJECTED");
      WriteJournal("b-1/b-11/QA-MARGIN",ev,g_zones[zone_index].id,signal,"Market",requested,0,sl,tp,trade.ResultOrder(),trade.ResultDeal(),0,trade.ResultRetcodeDescription());
      WriteSummary("EXECUTION",ev,g_zones[zone_index].id,signal,"Market",requested,0,sl,tp,r0,0,false,0.0,trade.ResultRetcodeDescription());
      return false;
     }
   return true;
  }

// Rule IDs: trend-2, b-1, b-31, multi-zone tick-gap decision
void ProcessDirectionalReversalTouches(double prev_bid,double bid,bool multi_zone_tick_gap)
  {
   if(!g_day_valid || g_daily_stop || multi_zone_tick_gap) return;
   for(int i=0;i<ArraySize(g_zones);i++)
     {
      if(g_trend==TREND_UP && prev_bid<g_zones[i].low && bid>=g_zones[i].low)
        {
         if(!ClaimReversalSignalSlot(i,false)) continue;
         WriteJournal("trend-2/b-31","ZONE_TOUCH_DIRECTION_CONFIRMED",g_zones[i].id,"R-S","Market",bid,0,0,0,0,0,0,"first valid R-S touch for this M15+zone+direction");
         SendReversal(i,false);
        }
      else if(g_trend==TREND_DOWN && prev_bid>g_zones[i].high && bid<=g_zones[i].high)
        {
         if(!ClaimReversalSignalSlot(i,true)) continue;
         WriteJournal("trend-2/b-31","ZONE_TOUCH_DIRECTION_CONFIRMED",g_zones[i].id,"R-B","Market",bid,0,0,0,0,0,0,"first valid R-B touch for this M15+zone+direction");
         SendReversal(i,true);
        }
     }
  }

//+------------------------------------------------------------------+
//| Pullback conservative b-8                                        |
//+------------------------------------------------------------------+
string NextBreakoutId()
  {
   g_breakout_seq++;
   return StringFormat("BO#%02d",g_breakout_seq);
  }

int FindActiveCycle(string day_key,string zone_id,bool buy)
  {
   for(int i=0;i<ArraySize(g_cycles);i++)
      if(g_cycles[i].active && g_cycles[i].day_key==day_key && g_cycles[i].zone_id==zone_id && g_cycles[i].buy==buy) return i;
   return -1;
  }

// Rule IDs: b-8, b-25, 2A confirmed no duplicate/restart
void CreatePullbackCycle(int zone_index,bool buy,datetime breakout_bar_time,string parent_breakout_id)
  {
   if(g_daily_stop || zone_index<0 || SessionBlocksPullbackEntries()) return;
   string mvp_reason="";
   if(!MVPPullbackAllowed(zone_index,buy,mvp_reason))
     {
      if(InpMVPProfileTelemetry) WriteSummary("MVP_FILTER","PULLBACK_CYCLE_BLOCKED_MVP_CONTEXT",g_zones[zone_index].id,buy?"PB-B":"PB-S","Shadow",0,0,0,0,0,0,false,0.0,mvp_reason,"",parent_breakout_id);
      return;
     }
   if(FindActiveCycle(g_day_key,g_zones[zone_index].id,buy)>=0)
     {
      WriteJournal("b-8/b-25","PULLBACK_CYCLE_NOT_RESTARTED_ALREADY_ACTIVE",g_zones[zone_index].id,buy?"PB-B":"PB-S","Stop",0,0,0,0,0,0,0,"valid breakout recorded but prior unfilled cycle remains unchanged","",parent_breakout_id);
      return;
     }
   int n=ArraySize(g_cycles); ArrayResize(g_cycles,n+1);
   g_cycles[n].active=true;
   g_cycles[n].buy=buy;
   g_cycles[n].day_key=g_day_key;
   g_cycles[n].zone_id=g_zones[zone_index].id;
   g_cycles[n].zone_low=g_zones[zone_index].low;
   g_cycles[n].zone_high=g_zones[zone_index].high;
   g_cycles[n].breakout_bar_time=breakout_bar_time;
   g_cycles[n].valid_bar_no=1;
   g_cycles[n].penetration_latched=false;
   g_cycles[n].order_ticket=0;
   g_cycles[n].waiting_logged=false;
   g_cycles[n].parent_breakout_id=parent_breakout_id;
   WriteJournal("b-8/b-25","PULLBACK_CYCLE_CREATED",g_zones[zone_index].id,buy?"PB-B":"PB-S","Stop",0,0,0,0,0,0,0,"valid t+1..t+5 window; pullback does not consume zone in v9","",parent_breakout_id);
   WriteSummary("SIGNAL","PULLBACK_CYCLE_CREATED",g_zones[zone_index].id,buy?"PB-B":"PB-S","Stop",0,0,0,0,0,0,false,0.0,"cycle created from independent valid breakout","",parent_breakout_id);
  }

void EndCycle(int idx,string event_name,string reason)
  {
   if(idx<0 || idx>=ArraySize(g_cycles) || !g_cycles[idx].active) return;
   ulong ticket=g_cycles[idx].order_ticket;
   if(ticket>0 && OrderSelect(ticket)) trade.OrderDelete(ticket);
   WriteJournal("b-8/b-23",event_name,g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S","Stop",0,0,0,0,ticket,0,0,reason,"",g_cycles[idx].parent_breakout_id);
   g_cycles[idx].active=false;
  }

void ExpireCycle(int idx,string reason)
  {
   EndCycle(idx,"PENDING_EXPIRED",reason);
  }

// Rule ID: b-8 t+1..t+5
void AgePullbackCyclesOnNewBar()
  {
   for(int i=0;i<ArraySize(g_cycles);i++)
     {
      if(!g_cycles[i].active) continue;
      if(g_cycles[i].valid_bar_no>=5) ExpireCycle(i,"start of t+6");
      else g_cycles[i].valid_bar_no++;
     }
  }

// Rule ID: b-8 exact native stop retry
bool CanPlaceExactStop(bool buy,double price)
  {
   MqlTick tick; if(!SymbolInfoTick(_Symbol,tick)) return false;
   long stops=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   double min_dist=(double)stops*_Point;
   if(buy) return (price>tick.ask && (price-tick.ask)>=min_dist);
   return (price<tick.bid && (tick.bid-price)>=min_dist);
  }

// Rule IDs: b-8, b-11, b-25, b-29, b-30, 5A-Revised
bool PlaceConservativePending(int idx)
  {
   if(SessionBlocksPullbackEntries()) return false;
   if(!MVPHasLiveSlot()) return false;
   if(idx<0 || idx>=ArraySize(g_cycles) || !g_cycles[idx].active || !g_cycles[idx].penetration_latched) return false;
   int z=FindZoneIndex(g_cycles[idx].day_key,g_cycles[idx].zone_id);
   if(z<0) { ExpireCycle(idx,"zone unavailable for exact pending placement"); return false; }

   double requested=NormalizeDouble(g_cycles[idx].buy ? g_cycles[idx].zone_high : g_cycles[idx].zone_low,_Digits);
   if(!CanPlaceExactStop(g_cycles[idx].buy,requested))
     {
      if(!g_cycles[idx].waiting_logged)
        {
         WriteJournal("b-8","PENDING_WAITING_NATIVE_VALIDITY",g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S","Stop",requested,0,0,0,0,0,0,"exact Rule price temporarily invalid due market/Stops Level","",g_cycles[idx].parent_breakout_id);
         g_cycles[idx].waiting_logged=true;
        }
      return false;
     }

   double sl=0,tp=0,r0=0; string target_zone="",reason="";
   if(!CalculateRBasedSLTP(z,g_cycles[idx].buy,requested,sl,tp,r0,target_zone,reason))
     {
      string ev=(StringFind(reason,"stop zone")>=0 ? "TRADE_REJECTED_NO_STOP_ZONE" : "TRADE_REJECTED_NO_1R_TARGET");
      WriteJournal("b-30",ev,g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S","Stop",requested,0,0,0,0,0,0,reason,"",g_cycles[idx].parent_breakout_id);
      WriteSummary("SIGNAL",ev,g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S","Stop",requested,0,0,0,0,0,false,0.0,reason,"",g_cycles[idx].parent_breakout_id);
      ExpireCycle(idx,"b-30 C1 rejection");
      return false;
     }

   string comment=MakeComment("P",g_cycles[idx].day_key,g_cycles[idx].zone_id,g_cycles[idx].buy);
   int req=AddRequestMeta(comment,requested,sl,tp,r0,target_zone,g_cycles[idx].parent_breakout_id);
   LogMarginPrecheck(g_cycles[idx].buy,requested,g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S",g_cycles[idx].parent_breakout_id);
   bool ok=(g_cycles[idx].buy ? trade.BuyStop(InpTestVolumeLot,requested,_Symbol,sl,tp,ORDER_TIME_GTC,0,comment)
                              : trade.SellStop(InpTestVolumeLot,requested,_Symbol,sl,tp,ORDER_TIME_GTC,0,comment));
   uint rc=trade.ResultRetcode();
   if(!ok || (rc!=TRADE_RETCODE_PLACED && rc!=TRADE_RETCODE_DONE))
     {
      DeactivateRequest(req);
      string ev=(rc==TRADE_RETCODE_NO_MONEY ? "EXECUTION_BLOCKED_MARGIN" : "PENDING_PLACE_RETRY");
      WriteJournal("b-8/b-11/QA-MARGIN",ev,g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S","Stop",requested,0,sl,tp,trade.ResultOrder(),trade.ResultDeal(),0,trade.ResultRetcodeDescription(),"",g_cycles[idx].parent_breakout_id);
      if(ev=="EXECUTION_BLOCKED_MARGIN")
         WriteSummary("EXECUTION",ev,g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S","Stop",requested,0,sl,tp,r0,0,false,0.0,trade.ResultRetcodeDescription(),"",g_cycles[idx].parent_breakout_id);
      return false;
     }
   g_cycles[idx].order_ticket=trade.ResultOrder();
   g_cycles[idx].waiting_logged=false;
   string note=StringFormat("exact zone edge; native MT5 activation; R0=%.5f target=%s",r0,target_zone);
   string eid=WriteJournal("b-8/b-11/b-29/b-30","PENDING_PLACED",g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S","Stop",requested,0,sl,tp,g_cycles[idx].order_ticket,0,0,note,"",g_cycles[idx].parent_breakout_id);
   WriteSummary("SIGNAL","PENDING_PLACED",g_cycles[idx].zone_id,g_cycles[idx].buy?"PB-B":"PB-S","Stop",requested,0,sl,tp,r0,0,false,0.0,note,"",g_cycles[idx].parent_breakout_id);
   DrawSignalEvent(eid,TimeCurrent(),requested,g_cycles[idx].buy?"PB-B":"PB-S",g_cycles[idx].zone_id,
                   "Stop",sl,tp,"Conservative pullback entry; exact broken-zone edge",g_cycles[idx].parent_breakout_id);
   return true;
  }

// Rule IDs: b-8, 3A, 4A, 5A-Revised
void ManagePullbackCycles(double bid)
  {
   if(g_daily_stop || SessionBlocksPullbackEntries()) return;
   for(int i=0;i<ArraySize(g_cycles);i++)
     {
      if(!g_cycles[i].active || g_cycles[i].day_key!=g_day_key) continue;
      int z=FindZoneIndex(g_cycles[i].day_key,g_cycles[i].zone_id);
      if(z<0) continue;
      string mvp_reason="";
      if(!MVPPullbackAllowed(z,g_cycles[i].buy,mvp_reason))
        {
         EndCycle(i,"PENDING_CANCELLED_MVP_CONTEXT",mvp_reason);
         continue;
        }

      if(!g_cycles[i].penetration_latched)
        {
         bool penetrated=(g_cycles[i].buy ? bid<=g_cycles[i].zone_high-PULLBACK_PENETRATION_USD
                                         : bid>=g_cycles[i].zone_low+PULLBACK_PENETRATION_USD);
         if(penetrated)
           {
            g_cycles[i].penetration_latched=true;
            string eid=WriteJournal("b-8","PULLBACK_PENETRATION_LATCHED",g_cycles[i].zone_id,g_cycles[i].buy?"PB-B":"PB-S","Stop",bid,0,0,0,0,0,0,"no maximum penetration in S1; first tick t+1 valid","",g_cycles[i].parent_breakout_id);
            DrawEvent(eid,TimeCurrent(),bid,"PB penetration");
           }
        }

      if(g_cycles[i].penetration_latched && g_cycles[i].order_ticket==0)
         PlaceConservativePending(i);
      else if(g_cycles[i].order_ticket>0 && !OrderSelect(g_cycles[i].order_ticket))
        {
         // Native fill is handled by OnTradeTransaction, which closes the matching cycle.
         // If the cycle is still active here, the pending disappeared without a recognized fill; retry exact price remains allowed.
         g_cycles[i].order_ticket=0;
         g_cycles[i].waiting_logged=false;
        }
     }
  }

// Rule ID: day-bound pullback decision + b-23
void CancelAllPullbackCycles(string event_name,string reason)
  {
   for(int i=0;i<ArraySize(g_cycles);i++) if(g_cycles[i].active) EndCycle(i,event_name,reason);
  }

//+------------------------------------------------------------------+
//| Breakout transition                                              |
//+------------------------------------------------------------------+
int FindActiveReversalTrack(string day_key,string zone_id,bool buy_reversal)
  {
   for(int i=0;i<ArraySize(g_positions);i++)
      if(g_positions[i].active && g_positions[i].day_key==day_key && g_positions[i].zone_id==zone_id &&
         g_positions[i].trade_type=="R" && g_positions[i].buy==buy_reversal) return i;
   return -1;
  }

bool CloseAllInvalidatedReversals(string day_key,string zone_id,bool buy_reversal)
  {
   for(int i=0;i<ArraySize(g_positions);i++)
     {
      if(!g_positions[i].active || g_positions[i].day_key!=day_key || g_positions[i].zone_id!=zone_id ||
         g_positions[i].trade_type!="R" || g_positions[i].buy!=buy_reversal) continue;
      if(!CloseInvalidatedReversal(i,zone_id)) return false;
     }
   return true;
  }

// Rule ID: b-3 exit invalidated reversal
bool CloseInvalidatedReversal(int track_index,string zone_id)
  {
   if(track_index<0) return true;
   ulong ticket=g_positions[track_index].position_ticket;
   if(ticket==0) ticket=FindPositionTicketByIdentifier(g_positions[track_index].position_id);
   string eid=WriteJournal("b-3","REVERSAL_EXIT_REQUESTED",zone_id,"R","Market",0,0,0,0,0,0,ticket,"valid buffered breakout");
   DrawEvent(eid,TimeCurrent(),0,"Reversal exit");
   bool ok=trade.PositionClose(ticket);
   uint rc=trade.ResultRetcode();
   if(!ok || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_DONE_PARTIAL))
     {
      WriteJournal("b-3","REVERSAL_EXIT_FAILED",zone_id,"R","Market",0,0,0,0,0,0,ticket,trade.ResultRetcodeDescription());
      return false;
     }
   WriteJournal("b-3","REVERSAL_EXIT_CONFIRMED",zone_id,"R","Market",0,0,0,0,0,trade.ResultDeal(),ticket,"close request done");
   return true;
  }

// Rule IDs: b-3, b-4, b-8, trend-1
void ProcessClosedBar(datetime closed_bar_time,ENUM_TREND_STATE trend_at_close,double o,double h,double l,double c)
  {
   ClassifyCandle(closed_bar_time,o,h,l,c);
   if(!g_day_valid) return;
   ENUM_TREND_STATE saved=g_trend;
   g_trend=trend_at_close; // Journal/visual for the decision uses the snapshot required by Rule.

   for(int i=0;i<ArraySize(g_zones);i++)
     {
      bool buy_breakout=(g_zones[i].engaged_buy && trend_at_close==TREND_UP && c>g_zones[i].high+BREAKOUT_BUFFER_USD);
      bool sell_breakout=(g_zones[i].engaged_sell && trend_at_close==TREND_DOWN && c<g_zones[i].low-BREAKOUT_BUFFER_USD);
      if(!buy_breakout && !sell_breakout) continue;

      bool buy=buy_breakout;
      string breakout_id=NextBreakoutId();
      string bo_note=StringFormat("%s; ZONE_ENGAGED + buffered close + trend snapshot",breakout_id);
      string eid=WriteJournal("b-3/b-4/trend-1","BREAKOUT_SIGNAL",g_zones[i].id,buy?"BO-B":"BO-S","Close",c,0,0,0,0,0,0,bo_note,breakout_id,"");
      WriteSummary("SIGNAL","BREAKOUT_SIGNAL",g_zones[i].id,buy?"BO-B":"BO-S","Close",c,0,0,0,0,0,false,0.0,"ZONE_ENGAGED + buffered close + trend snapshot",breakout_id,"");
      DrawSignalEvent(eid,closed_bar_time+PeriodSeconds(PERIOD_M15)-1,c,buy?"BO-B":"BO-S",g_zones[i].id,
                   "Close",0,0,StringFormat("Breakout signal only; buffer=%.2f; zone=%s..%s; SL/TP=N/A",
                   BREAKOUT_BUFFER_USD,DoubleToString(g_zones[i].low,_Digits),DoubleToString(g_zones[i].high,_Digits)),breakout_id);

      // Buy breakout invalidates an active Sell reversal; Sell breakout invalidates active Buy reversal.
      if(!CloseAllInvalidatedReversals(g_day_key,g_zones[i].id,!buy)) continue;
      if(!g_daily_stop) CreatePullbackCycle(i,buy,closed_bar_time,breakout_id);
     }
   g_trend=saved;
  }

//+------------------------------------------------------------------+
//| b-29 R-based profit protection                                   |
//+------------------------------------------------------------------+
// Known native costs only; spread is already represented by native fill prices.
double KnownPositionCosts(ulong position_id)
  {
   if(!HistorySelectByPosition(position_id)) return 0.0;
   double costs=0.0;
   for(int i=0;i<HistoryDealsTotal();i++)
     {
      ulong d=HistoryDealGetTicket(i);
      if(d==0) continue;
      if((ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID)!=position_id) continue;
      if((ulong)HistoryDealGetInteger(d,DEAL_MAGIC)!=EA_MAGIC) continue;
      costs+=HistoryDealGetDouble(d,DEAL_COMMISSION)+HistoryDealGetDouble(d,DEAL_SWAP)+HistoryDealGetDouble(d,DEAL_FEE);
     }
   return costs;
  }

// Converts known monetary costs to an XAUUSD price distance using native OrderCalcProfit.
double PriceDistanceForMoney(bool buy,double reference_price,double money)
  {
   if(money<=0.0) return 0.0;
   double p=0.0;
   ENUM_ORDER_TYPE type=(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   double close_price=(buy?reference_price+1.0:reference_price-1.0);
   if(!OrderCalcProfit(type,_Symbol,InpTestVolumeLot,reference_price,close_price,p)) return 0.0;
   p=MathAbs(p);
   if(p<=0.0) return 0.0;
   return money/p;
  }

// b-29 Stage 4: most recent two confirmed one-left/one-right pivots define current HL/LH.
bool FindConfirmedStructureSL(bool buy,double &pivot_price,datetime &pivot_time)
  {
   pivot_price=0.0; pivot_time=0;
   double latest=0.0,previous=0.0;
   datetime latest_time=0;
   int found=0;
   int bars=Bars(_Symbol,PERIOD_M15);
   int max_shift=bars-2;
   if(max_shift>100) max_shift=100;
   for(int s=2;s<=max_shift;s++)
     {
      double cur=(buy?iLow(_Symbol,PERIOD_M15,s):iHigh(_Symbol,PERIOD_M15,s));
      double newer=(buy?iLow(_Symbol,PERIOD_M15,s-1):iHigh(_Symbol,PERIOD_M15,s-1));
      double older=(buy?iLow(_Symbol,PERIOD_M15,s+1):iHigh(_Symbol,PERIOD_M15,s+1));
      bool swing=(buy ? (cur<newer && cur<older) : (cur>newer && cur>older));
      if(!swing) continue;
      if(found==0)
        {
         latest=cur;
         latest_time=iTime(_Symbol,PERIOD_M15,s);
         found=1;
        }
      else
        {
         previous=cur;
         found=2;
         break;
        }
     }
   if(found<2) return false;
   bool structure_ok=(buy ? latest>previous : latest<previous);
   if(!structure_ok) return false;
   pivot_price=NormalizeDouble(latest,_Digits);
   pivot_time=latest_time;
   return true;
  }

bool StopImproves(bool buy,double current_sl,double desired_sl)
  {
   if(desired_sl<=0.0) return false;
   if(current_sl<=0.0) return true;
   if(buy) return desired_sl>current_sl+(_Point*0.1);
   return desired_sl<current_sl-(_Point*0.1);
  }

bool CanModifyStopExact(bool buy,double desired_sl)
  {
   MqlTick tick; if(!SymbolInfoTick(_Symbol,tick)) return false;
   long stops=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   double min_dist=(double)stops*_Point;
   if(buy) return (desired_sl<tick.bid && (tick.bid-desired_sl)>=min_dist);
   return (desired_sl>tick.ask && (desired_sl-tick.ask)>=min_dist);
  }

// b-29: exact SL modification, no arbitrary buffer; retry if native constraints block it.
bool ModifyStopExact(int track_index,double desired_sl,string stage_note)
  {
   if(track_index<0 || track_index>=ArraySize(g_positions) || !g_positions[track_index].active) return false;
   ulong ticket=g_positions[track_index].position_ticket;
   if(ticket==0) ticket=FindPositionTicketByIdentifier(g_positions[track_index].position_id);
   if(ticket==0 || !PositionSelectByTicket(ticket)) return false;
   double current_sl=PositionGetDouble(POSITION_SL);
   double current_tp=PositionGetDouble(POSITION_TP);
   desired_sl=NormalizeDouble(desired_sl,_Digits);
   if(!StopImproves(g_positions[track_index].buy,current_sl,desired_sl)) return true;

   g_positions[track_index].desired_sl=desired_sl;
   if(!CanModifyStopExact(g_positions[track_index].buy,desired_sl))
     {
      if(!g_positions[track_index].sl_retry_logged)
        {
         WriteJournal("b-29","SL_MOVE_RETRY",g_positions[track_index].zone_id,g_positions[track_index].trade_type,"ModifySL",0,0,desired_sl,current_tp,0,0,ticket,
                      stage_note+"; exact level temporarily invalid by Stops Level/market");
         WriteSummary("MANAGEMENT","SL_MOVE_RETRY",g_positions[track_index].zone_id,g_positions[track_index].trade_type,"ModifySL",0,0,desired_sl,current_tp,
                      g_positions[track_index].r0,ticket,true,0.0,stage_note);
         g_positions[track_index].sl_retry_logged=true;
        }
      return false;
     }

   if(!g_positions[track_index].sl_retry_logged)
      WriteJournal("b-29","SL_MOVE_REQUESTED",g_positions[track_index].zone_id,g_positions[track_index].trade_type,"ModifySL",0,0,desired_sl,current_tp,0,0,ticket,stage_note);
   bool ok=trade.PositionModify(ticket,desired_sl,current_tp);
   uint rc=trade.ResultRetcode();
   if(!ok || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_NO_CHANGES))
     {
      if(!g_positions[track_index].sl_retry_logged)
        {
         WriteJournal("b-29","SL_MOVE_RETRY",g_positions[track_index].zone_id,g_positions[track_index].trade_type,"ModifySL",0,0,desired_sl,current_tp,0,0,ticket,trade.ResultRetcodeDescription());
         g_positions[track_index].sl_retry_logged=true;
        }
      return false;
     }
   g_positions[track_index].sl_retry_logged=false;
   g_positions[track_index].desired_sl=0.0;
   WriteJournal("b-29","SL_MOVE_CONFIRMED",g_positions[track_index].zone_id,g_positions[track_index].trade_type,"ModifySL",0,0,desired_sl,current_tp,0,0,ticket,stage_note);
   WriteSummary("MANAGEMENT","SL_MOVE_CONFIRMED",g_positions[track_index].zone_id,g_positions[track_index].trade_type,"ModifySL",0,0,desired_sl,current_tp,
                g_positions[track_index].r0,ticket,true,0.0,stage_note);
   return true;
  }

// Rule ID: b-29. Buy progress uses executable Bid; Sell progress uses executable Ask.
void ManageProfitProtection(const MqlTick &tick)
  {
   for(int i=0;i<ArraySize(g_positions);i++)
     {
      if(!g_positions[i].active || g_positions[i].r0<=0.0) continue;
      ulong ticket=g_positions[i].position_ticket;
      if(ticket==0) ticket=FindPositionTicketByIdentifier(g_positions[i].position_id);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;

      double favorable=(g_positions[i].buy ? tick.bid-g_positions[i].risk_anchor_entry
                                           : g_positions[i].risk_anchor_entry-tick.ask);
      if(favorable<0.0) favorable=0.0;

      if(g_positions[i].r_stage<1 && favorable>=1.0*g_positions[i].r0)
        {
         g_positions[i].r_stage=1;
         WriteJournal("b-29","R_STAGE_CHANGED",g_positions[i].zone_id,g_positions[i].trade_type,"",g_positions[i].risk_anchor_entry,0,0,g_positions[i].tp,0,0,ticket,"stage=1 >=1R risk-zero eligible");
         WriteSummary("MANAGEMENT","R_STAGE_CHANGED",g_positions[i].zone_id,g_positions[i].trade_type,"",g_positions[i].risk_anchor_entry,0,0,g_positions[i].tp,g_positions[i].r0,ticket,true,0.0,"stage=1 >=1R");
        }
      if(g_positions[i].r_stage<2 && favorable>=1.5*g_positions[i].r0)
        {
         g_positions[i].r_stage=2;
         WriteJournal("b-29","R_STAGE_CHANGED",g_positions[i].zone_id,g_positions[i].trade_type,"",g_positions[i].risk_anchor_entry,0,0,g_positions[i].tp,0,0,ticket,"stage=2 >=1.5R lock +0.5R");
         WriteSummary("MANAGEMENT","R_STAGE_CHANGED",g_positions[i].zone_id,g_positions[i].trade_type,"",g_positions[i].risk_anchor_entry,0,0,g_positions[i].tp,g_positions[i].r0,ticket,true,0.0,"stage=2 >=1.5R");
        }
      if(g_positions[i].r_stage<3 && favorable>=2.0*g_positions[i].r0)
        {
         g_positions[i].r_stage=3;
         WriteJournal("b-29","R_STAGE_CHANGED",g_positions[i].zone_id,g_positions[i].trade_type,"",g_positions[i].risk_anchor_entry,0,0,g_positions[i].tp,0,0,ticket,"stage=3 >=2R structural trail active");
         WriteSummary("MANAGEMENT","R_STAGE_CHANGED",g_positions[i].zone_id,g_positions[i].trade_type,"",g_positions[i].risk_anchor_entry,0,0,g_positions[i].tp,g_positions[i].r0,ticket,true,0.0,"stage=3 >=2R");
        }

      double desired=0.0;
      string note="";
      if(g_positions[i].r_stage>=3)
        {
         double pivot=0.0; datetime pt=0;
         if(FindConfirmedStructureSL(g_positions[i].buy,pivot,pt))
           {
            double current_sl=PositionGetDouble(POSITION_SL);
            if(StopImproves(g_positions[i].buy,current_sl,pivot))
              {
               desired=pivot;
               note=StringFormat("stage=3 structure pivot=%s time=%s",DoubleToString(pivot,_Digits),TimeToString(pt,TIME_DATE|TIME_MINUTES));
               WriteJournal("b-29","STRUCTURE_TRAIL_CANDIDATE",g_positions[i].zone_id,g_positions[i].trade_type,"",0,0,pivot,g_positions[i].tp,0,0,ticket,note);
              }
           }
        }
      if(desired<=0.0 && g_positions[i].r_stage>=2)
        {
         desired=(g_positions[i].buy ? g_positions[i].risk_anchor_entry+0.5*g_positions[i].r0
                                     : g_positions[i].risk_anchor_entry-0.5*g_positions[i].r0);
         note="stage=2 lock +0.5R";
        }
      if(desired<=0.0 && g_positions[i].r_stage>=1)
        {
         double costs=KnownPositionCosts(g_positions[i].position_id);
         double cover_money=MathMax(0.0,-costs);
         double offset=PriceDistanceForMoney(g_positions[i].buy,g_positions[i].actual_fill,cover_money);
         desired=(g_positions[i].buy ? g_positions[i].actual_fill+offset : g_positions[i].actual_fill-offset);
         note=StringFormat("stage=1 BE actual_fill + known_native_costs=%.2f",cover_money);
        }
      if(desired>0.0) ModifyStopExact(i,desired,note);
     }
  }

//+------------------------------------------------------------------+
//| Daily loss + native costs                                        |
//+------------------------------------------------------------------+
// Rule ID: b-20
void LogDealCosts(ulong deal_ticket,ulong position_ticket)
  {
   double profit=HistoryDealGetDouble(deal_ticket,DEAL_PROFIT);
   double commission=HistoryDealGetDouble(deal_ticket,DEAL_COMMISSION);
   double swap=HistoryDealGetDouble(deal_ticket,DEAL_SWAP);
   double fee=HistoryDealGetDouble(deal_ticket,DEAL_FEE);
   double price=HistoryDealGetDouble(deal_ticket,DEAL_PRICE);
   WriteJournal("b-20","DEAL_COSTS_RECORDED","","","",0,price,0,0,0,deal_ticket,position_ticket,
                StringFormat("profit=%.2f commission=%.2f swap=%.2f fee=%.2f",profit,commission,swap,fee));
  }

// Rule ID: b-20. Full-position net used for S1 0.01-lot non-partial lifecycle.
double CalculatePositionNet(ulong position_id)
  {
   if(!HistorySelectByPosition(position_id)) return 0.0;
   double net=0.0;
   for(int i=0;i<HistoryDealsTotal();i++)
     {
      ulong d=HistoryDealGetTicket(i);
      if(d==0) continue;
      if((ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID)!=position_id) continue;
      if((ulong)HistoryDealGetInteger(d,DEAL_MAGIC)!=EA_MAGIC) continue;
      net+=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_COMMISSION)+HistoryDealGetDouble(d,DEAL_SWAP)+HistoryDealGetDouble(d,DEAL_FEE);
     }
   return net;
  }

// Rule ID: b-23 + QA-DL
void CheckDailyLossGuard()
  {
   if(g_daily_stop) return;
   // In QA Discovery, the tester deposit may be intentionally large only to avoid native margin stop-out.
   // b-23 shadow detection therefore uses a separate strategy-capital basis and never enforces the stop.
   double capital_basis=(InpQADiscoveryMode ? InpQAStrategyCapitalBasis : g_initial_deposit);
   if(capital_basis<=0.0) return;
   // Baseline b-23 applies only below 300. TEST-HARNESS may explicitly override this for isolated capital scenarios.
   if(!InpTestDailyLossOverride && capital_basis>=300.0) return;
   double loss_pct=(InpTestDailyLossOverride ? InpTestDailyLossPercent : 20.0);
   double threshold=-(loss_pct/100.0)*capital_basis;
   if(g_daily_realized_net<=threshold)
     {
      if(InpQADiscoveryMode)
        {
         if(!g_daily_would_trigger_logged)
           {
            WriteJournal("b-23/QA-DL","DAILY_LOSS_WOULD_TRIGGER","","","",0,0,0,0,0,0,0,
                         StringFormat("QA bypass: daily_net=%.2f threshold=%.2f capital_basis=%.2f loss_pct=%.2f override=%s; signal engine continues",g_daily_realized_net,threshold,capital_basis,loss_pct,InpTestDailyLossOverride?"true":"false"));
            WriteSummary("QA","DAILY_LOSS_WOULD_TRIGGER","","","",0,0,0,0,0,0,false,0.0,
                         StringFormat("daily_net=%.2f threshold=%.2f capital_basis=%.2f loss_pct=%.2f override=%s",g_daily_realized_net,threshold,capital_basis,loss_pct,InpTestDailyLossOverride?"true":"false"));
            g_daily_would_trigger_logged=true;
           }
         return;
        }
      g_daily_stop=true;
      string dl_note=StringFormat("daily_net=%.2f threshold=%.2f capital_basis=%.2f loss_pct=%.2f override=%s",g_daily_realized_net,threshold,capital_basis,loss_pct,InpTestDailyLossOverride?"true":"false");
      WriteJournal("b-23","DAILY_LOSS_STOP","","","",0,0,0,0,0,0,0,dl_note);
      WriteSummary("RISK","DAILY_LOSS_STOP","","","",0,0,0,0,0,0,false,0.0,dl_note);
      CancelAllPullbackCycles("PENDING_CANCELLED_DAILY_STOP","daily loss guard active");
     }
  }

//+------------------------------------------------------------------+
//| Trade transaction                                                |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || trans.deal==0) return;
   ulong deal=trans.deal;
   if(!HistoryDealSelect(deal)) return;
   if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)!=EA_MAGIC) return;

   ulong position_id=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   ulong position_ticket=FindPositionTicketByIdentifier(position_id);
   ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
   double fill=HistoryDealGetDouble(deal,DEAL_PRICE);
   string comment=HistoryDealGetString(deal,DEAL_COMMENT);
   if(StringLen(comment)==0 && trans.order>0 && HistoryOrderSelect(trans.order))
      comment=HistoryOrderGetString(trans.order,ORDER_COMMENT);
   LogDealCosts(deal,position_ticket);

   if(entry==DEAL_ENTRY_IN || entry==DEAL_ENTRY_INOUT)
     {
      string type,day_key,zone_id; bool buy=false;
      if(ParseComment(comment,type,day_key,zone_id,buy))
        {
         int req=FindRequest(comment);
         double requested=0,sl=0,tp=0,r0=0; string target_zone="",parent_breakout_id=""; int reversal_ordinal=0;
         if(req>=0)
           {
            requested=g_requests[req].requested_price;
            sl=g_requests[req].sl;
            tp=g_requests[req].tp;
            r0=g_requests[req].r0;
            target_zone=g_requests[req].target_zone_id;
            parent_breakout_id=g_requests[req].parent_breakout_id;
            reversal_ordinal=g_requests[req].reversal_ordinal;
            DeactivateRequest(req);
           }
         bool stacked_pullback=(type=="P" && HasActivePullbackPosition(day_key,zone_id,buy));
         AddPositionTrack(position_id,day_key,zone_id,type,buy,requested,fill,sl,tp,r0,target_zone,parent_breakout_id,stacked_pullback,reversal_ordinal);
         string sig=(type=="R"?(buy?"R-B":"R-S"):(buy?"PB-B":"PB-S"));
         string note=(type=="R" ? StringFormat("native fill; reversal_ordinal=%d R0=%.5f target=%s",reversal_ordinal,r0,target_zone) : StringFormat("native fill; R0=%.5f target=%s",r0,target_zone));
         string eid=WriteJournal(type=="R"?"b-1/b-26/b-29":"b-8/b-25/b-29","ORDER_FILLED",zone_id,sig,type=="R"?"Market":"Stop",requested,fill,sl,tp,trans.order,deal,position_ticket,note,"",parent_breakout_id);
         WriteSummary("PRIMARY_TRADE","ORDER_FILLED",zone_id,sig,type=="R"?"Market":"Stop",requested,fill,sl,tp,r0,position_ticket,true,0.0,note,"",parent_breakout_id,stacked_pullback,reversal_ordinal);
         LogMarginPostFill(zone_id,sig,position_ticket,parent_breakout_id);
         if(CountEAOpenPositions()>InpMaxLivePositions)
           {
            WriteSummary("MVP_RISK","POSITION_CAP_OVERFLOW",zone_id,sig,"Emergency",requested,fill,sl,tp,r0,position_ticket,false,0.0,StringFormat("live=%d cap=%d; closing newest",CountEAOpenPositions(),InpMaxLivePositions),"",parent_breakout_id,stacked_pullback,reversal_ordinal);
            trade.PositionClose(position_ticket);
           }
         if(stacked_pullback)
           {
            string tag_note="new Pullback position opened while an older same Zone+Direction Pullback position remained active; execution unchanged";
            WriteJournal("QA-PB-STACK","PULLBACK_STACKED_POSITION_OPENED",zone_id,sig,"Tag",requested,fill,sl,tp,trans.order,deal,position_ticket,tag_note,"",parent_breakout_id);
            WriteSummary("QA_TAG","PULLBACK_STACKED_POSITION_OPENED",zone_id,sig,"Tag",requested,fill,sl,tp,r0,position_ticket,false,0.0,tag_note,"",parent_breakout_id,true);
           }
         DrawEvent(eid,TimeCurrent(),fill,"FILLED "+type);
        }
     }

   if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY || entry==DEAL_ENTRY_INOUT)
     {
      int p=FindPositionTrack(position_id);
      if(p>=0)
        {
         double net=CalculatePositionNet(position_id);
         g_daily_realized_net+=net;
         MarkZoneUsageConsumed(g_positions[p].day_key,g_positions[p].zone_id,g_positions[p].trade_type);
         string zone=g_positions[p].zone_id;
         string type=g_positions[p].trade_type;
         double r0=g_positions[p].r0;
         ulong tracked_ticket=g_positions[p].position_ticket;
         string parent_breakout_id=g_positions[p].parent_breakout_id;
         bool stacked_pullback=g_positions[p].stacked_pullback;
         int max_r_stage=g_positions[p].r_stage;
         string sig=(type=="R"?(g_positions[p].buy?"R-B":"R-S"):(g_positions[p].buy?"PB-B":"PB-S"));
         bool session_close_requested=g_positions[p].session_close_requested;
         string session_close_reason=g_positions[p].session_close_reason;
         if(session_close_requested)
           {
            string session_note=StringFormat("mode=%s position_net=%.2f %s",SessionModeToString(),net,session_close_reason);
            WriteJournal("AR-SESSION-01","SESSION_FLAT_CLOSE_CONFIRMED",zone,sig,"Market",0,fill,0,0,0,deal,tracked_ticket,session_note,"",parent_breakout_id);
            WriteSummary("QA_TAG","SESSION_FLAT_CLOSE_CONFIRMED",zone,sig,"Market",0,fill,0,0,r0,tracked_ticket,false,0.0,session_note,"",parent_breakout_id,stacked_pullback,g_positions[p].reversal_ordinal);
           }
         g_positions[p].active=false;
         string note=StringFormat("position_net=%.2f daily_net=%.2f R0=%.5f max_r_stage=%d stacked_pullback=%s reversal_ordinal=%d",net,g_daily_realized_net,r0,max_r_stage,stacked_pullback?"true":"false",g_positions[p].reversal_ordinal);
         string eid=WriteJournal("b-20/b-23/b-26/b-29","POSITION_CLOSED",zone,sig,"",0,fill,0,0,0,deal,tracked_ticket,note,"",parent_breakout_id);
         WriteSummary("PRIMARY_TRADE","POSITION_CLOSED",zone,sig,"",0,fill,0,0,r0,tracked_ticket,true,net,note,"",parent_breakout_id,stacked_pullback,g_positions[p].reversal_ordinal);
         DrawEvent(eid,TimeCurrent(),fill,"EXIT");
         CheckDailyLossGuard();
        }
     }
  }

//+------------------------------------------------------------------+
//| New bar / day state                                              |
//+------------------------------------------------------------------+
void HandleDayChange(string new_day)
  {
   if(g_day_key!="" && new_day!=g_day_key)
     {
      CancelAllPullbackCycles("PENDING_CANCELLED_DAY_CHANGE","day changed; old daily zones invalid for new pullback entries");
      g_daily_realized_net=0.0;
      g_daily_stop=false;
      g_daily_would_trigger_logged=false;
     }
   if(new_day!=g_day_key) g_breakout_seq=0;
   g_day_key=new_day;
   LoadZonesForDay(g_day_key);
  }

void ProcessNewBar(datetime new_bar_time)
  {
   // Existing cycles age before a possible new cycle is created from the just-closed bar.
   AgePullbackCyclesOnNewBar();

   if(g_bar_time>0)
     {
      double o=iOpen(_Symbol,PERIOD_M15,1);
      double h=iHigh(_Symbol,PERIOD_M15,1);
      double l=iLow(_Symbol,PERIOD_M15,1);
      double c=iClose(_Symbol,PERIOD_M15,1);
      ENUM_TREND_STATE trend_snapshot=g_trend; // snapshot before rolling 3-bar reference
      ProcessClosedBar(g_bar_time,trend_snapshot,o,h,l,c);
     }

   string new_day=DayKey(new_bar_time);
   if(new_day!=g_day_key) HandleDayChange(new_day);

   g_bar_time=new_bar_time;
   UpdateTrendReference();
   double current_open=iOpen(_Symbol,PERIOD_M15,0);
   ResetEngagementForCurrentBar(current_open);
  }

//+------------------------------------------------------------------+
//| EA lifecycle                                                     |
//+------------------------------------------------------------------+
int OnInit()
  {
   // visual-1..3: clear stale custom objects from earlier EA visual versions.
   DeleteVisuals();
   if((bool)MQLInfoInteger(MQL_TESTER))
     {
      FileDelete(InpJournalFile,HarnessFileScopeFlag());
      FileDelete(InpSummaryFile,HarnessFileScopeFlag());
     }
   trade.SetExpertMagicNumber(EA_MAGIC);
   trade.SetTypeFillingBySymbol(_Symbol);
   g_initial_deposit=AccountInfoDouble(ACCOUNT_BALANCE);

   if(InpRCapUSD<=0.0)
     {
      WriteJournal("b-29/b-30","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"InpRCapUSD must be > 0");
      return INIT_FAILED;
     }
   if(InpHighReversalMaxPerDay<1 || InpHighReversalSLMultiplier<=0.0)
     {
      WriteJournal("TEST-HIGH-R","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,
                   "InpHighReversalMaxPerDay must be >=1 and InpHighReversalSLMultiplier must be >0");
      return INIT_FAILED;
     }
   if(InpTestVolumeLot<=0.0)
     {
      WriteJournal("TEST-HARNESS","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"InpTestVolumeLot must be > 0");
      return INIT_FAILED;
     }
   if(InpTestDailyLossOverride && (InpTestDailyLossPercent<=0.0 || InpTestDailyLossPercent>=100.0))
     {
      WriteJournal("TEST-HARNESS/b-23","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"InpTestDailyLossPercent must be >0 and <100 when override=true");
      return INIT_FAILED;
     }
   if(InpQADiscoveryMode && InpQAStrategyCapitalBasis<=0.0)
     {
      WriteJournal("b-23/QA-DL","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"InpQAStrategyCapitalBasis must be > 0 in QA Discovery");
      return INIT_FAILED;
     }
   if(InpSessionPreCloseMinutes<=0.0 || InpSessionPreCloseMinutes>60.0)
     {
      WriteJournal("AR-SESSION-01","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"InpSessionPreCloseMinutes must be >0 and <=60");
      return INIT_FAILED;
     }
   if(InpMaxLivePositions<1)
     {
      WriteJournal("MVP-SIMPLE","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"InpMaxLivePositions must be >=1");
      return INIT_FAILED;
     }
   if(!ValidateTimeframe()) return INIT_FAILED;
   if(!ValidateAccountMode()) return INIT_FAILED;
   if(!ValidateVolumeCompatibility()) return INIT_FAILED;
   if(!LoadAllRawZones()) return INIT_FAILED;
   LogWeeklySessionSchedule();
   if(Bars(_Symbol,PERIOD_M15)<4)
     {
      WriteJournal("trend-1","TEST_CONFIGURATION_ERROR","","","",0,0,0,0,0,0,0,"Need at least 4 M15 bars (current + 3 closed references)");
      return INIT_FAILED;
     }

   g_bar_time=iTime(_Symbol,PERIOD_M15,0);
   HandleDayChange(DayKey(g_bar_time));
   if(!UpdateTrendReference()) return INIT_FAILED;
   ResetEngagementForCurrentBar(iOpen(_Symbol,PERIOD_M15,0));
   MqlTick tick;
   if(SymbolInfoTick(_Symbol,tick)) g_prev_bid=tick.bid;

   WriteJournal("MVP-SIMPLE/AR-SESSION-01","EA_INITIALIZED","","","",0,0,0,0,0,0,0,StringFormat("version=1.80 profile=%s session_mode=%s preclose_minutes=%.2f profile_high_max=%d high_sl_multiplier=%.2f max_live=%d volume=%.4f initial_deposit=%.2f zones=%d",MVPSimpleProfileToString(),SessionModeToString(),InpSessionPreCloseMinutes,MVPSimpleHighMax(),InpHighReversalSLMultiplier,InpMaxLivePositions,InpTestVolumeLot,g_initial_deposit,ArraySize(g_zones)));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   WriteJournal("S1","EA_DEINITIALIZED","","","",0,0,0,0,0,0,0,StringFormat("reason=%d",reason));
   if(InpCleanupVisualOnDeinit) DeleteVisuals();
  }

void OnTick()
  {
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return;

   ManageSessionSafety(tick.time);

   datetime bt=iTime(_Symbol,PERIOD_M15,0);
   if(bt!=g_bar_time) ProcessNewBar(bt);

   UpdateTrendState(tick.bid);

   if(g_prev_bid>0.0 && g_day_valid)
     {
      int crosses=CountDirectionalZoneCrosses(g_prev_bid,tick.bid);
      bool multi=(crosses>1);
      if(multi)
         WriteJournal("trend-2/b-1","MULTI_ZONE_TICK_GAP","","","",g_prev_bid,tick.bid,0,0,0,0,0,StringFormat("crossed_zones=%d; no synthetic path/signals",crosses));
      UpdateZoneEngagement(g_prev_bid,tick.bid,multi);
      if(!SessionBlocksReversalEntries()) ProcessDirectionalReversalTouches(g_prev_bid,tick.bid,multi);
     }

   ManagePullbackCycles(tick.bid);
   ManageProfitProtection(tick);
   g_prev_bid=tick.bid;
  }
//+------------------------------------------------------------------+
