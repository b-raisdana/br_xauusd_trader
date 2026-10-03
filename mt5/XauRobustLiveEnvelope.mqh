// XAUUSD_ROBUST_FINAL broker execution envelope.
// Included only by the generated Live RC, after the byte-locked Strategy body.

const string XAU_RELEASE_KILL_BUTTON="XAU_RELEASE_KILL";
bool g_xau_release_fail_closed=false;
string g_xau_release_fail_reason="";
int g_xau_release_reconcile_failures=0;

bool XauReleaseIsTester()
  {
   return (bool)MQLInfoInteger(MQL_TESTER);
  }

string XauReleaseModeName()
  {
   if(InpReleaseMode==XAU_RELEASE_DEMO) return "DEMO";
   if(InpReleaseMode==XAU_RELEASE_LIVE) return "LIVE";
   return "DISABLED";
  }

bool XauReleaseIdentityMatches(string &reason)
  {
   if(InpAllowedAccountLogin<=0)
     {
      reason="allowed account login is not configured";
      return false;
     }
   if(AccountInfoInteger(ACCOUNT_LOGIN)!=InpAllowedAccountLogin)
     {
      reason="account login does not match the local allowlist";
      return false;
     }
   if(AccountInfoString(ACCOUNT_SERVER)!=InpAllowedServer)
     {
      reason="account server mismatch";
      return false;
     }
   if(_Symbol!=InpAllowedSymbol)
     {
      reason="chart symbol mismatch";
      return false;
     }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      reason="account is not Hedge mode";
      return false;
     }
   return true;
  }

bool XauReleasePermissionsReady(string &reason)
  {
   if(!(bool)TerminalInfoInteger(TERMINAL_CONNECTED))
     {
      reason="terminal is disconnected";
      return false;
     }
   if(!(bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
     {
      reason="terminal Algo Trading is disabled";
      return false;
     }
   if(!(bool)MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      reason="EA Allow Algo Trading is disabled";
      return false;
     }
   if(!(bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) ||
      !(bool)AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
     {
      reason="broker account does not allow EA trading";
      return false;
     }
   return true;
  }

bool XauReleaseModeMatchesAccount(string &reason)
  {
   long mode=AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(InpReleaseMode==XAU_RELEASE_DEMO)
     {
      if(mode!=ACCOUNT_TRADE_MODE_DEMO)
        {
         reason="DEMO release mode requires a Demo account";
         return false;
        }
      return true;
     }
   if(InpReleaseMode==XAU_RELEASE_LIVE)
     {
      if(mode!=ACCOUNT_TRADE_MODE_REAL)
        {
         reason="LIVE release mode requires a Real account";
         return false;
        }
      if(!InpConfirmRealMoney)
        {
         reason="real-money confirmation input is false";
         return false;
        }
      return true;
     }
   reason="release mode is disabled";
   return false;
  }

bool XauReleaseHasExternalXAUExposure()
  {
   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=EA_MAGIC) return true;
     }
   for(int i=0;i<OrdersTotal();i++)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0 || OrderGetString(ORDER_SYMBOL)!=_Symbol) continue;
      if((ulong)OrderGetInteger(ORDER_MAGIC)!=EA_MAGIC) return true;
     }
   return false;
  }

bool XauReleasePreflight()
  {
   if(XauReleaseIsTester()) return true;
   if(InpEmergencyStop)
     {
      Print("XAU LIVE RC fail-closed: emergency stop input is active.");
      return false;
     }
   if(InpReconciliationGraceSeconds<1 || InpReconciliationGraceSeconds>60)
     {
      Print("XAU LIVE RC fail-closed: reconciliation grace must be 1..60 seconds.");
      return false;
     }
   string reason="";
   if(!XauReleaseIdentityMatches(reason) || !XauReleaseModeMatchesAccount(reason) ||
      !XauReleasePermissionsReady(reason))
     {
      Print("XAU LIVE RC fail-closed: ",reason);
      return false;
     }
   if(InpRejectExternalXAUExposure && XauReleaseHasExternalXAUExposure())
     {
      Print("XAU LIVE RC fail-closed: manual/external XAUUSD exposure exists.");
      return false;
     }
   PrintFormat("XAU LIVE RC preflight passed: mode=%s server=%s symbol=%s",
               XauReleaseModeName(),AccountInfoString(ACCOUNT_SERVER),_Symbol);
   return true;
  }

void XauReleaseLatch(string reason)
  {
   if(g_xau_release_fail_closed) return;
   g_xau_release_fail_closed=true;
   g_xau_release_fail_reason=reason;
   g_restart_lock=true;
   WriteJournal("LIVE-ENVELOPE","LIVE_FAIL_CLOSED_LATCHED","","","Safety",0,0,0,0,0,0,0,reason);
   Print("XAU LIVE RC fail-closed latched: ",reason);
  }

void XauReleaseEmergencyStop(string reason)
  {
   XauReleaseLatch(reason);
   CancelAllPullbackCycles("LIVE_KILL_PENDING_CANCELLED",reason);
   MaintainRestartFailClosed(reason);
  }

bool XauReleaseRuntimeGuard()
  {
   if(XauReleaseIsTester()) return true;
   if(g_xau_release_fail_closed) return false;
   if(InpEmergencyStop)
     {
      XauReleaseLatch("emergency stop input activated");
      return false;
     }
   string reason="";
   if(!XauReleaseIdentityMatches(reason) || !XauReleaseModeMatchesAccount(reason) ||
      !XauReleasePermissionsReady(reason))
     {
      XauReleaseLatch(reason);
      return false;
     }
   if(InpRejectExternalXAUExposure && XauReleaseHasExternalXAUExposure())
     {
      XauReleaseLatch("manual/external XAUUSD exposure detected");
      return false;
     }
   return true;
  }

bool XauReleaseProjectionMatches(string &reason)
  {
   int actual_positions=0;
   for(int i=0;i<PositionsTotal();i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || (ulong)PositionGetInteger(POSITION_MAGIC)!=EA_MAGIC) continue;
      actual_positions++;
      ulong identifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(FindPositionTrack(identifier)<0)
        {
         reason="EA position is absent from the internal position projection";
         return false;
        }
     }
   int tracked_positions=0;
   for(int i=0;i<ArraySize(g_positions);i++)
      if(g_positions[i].active) tracked_positions++;
   if(actual_positions!=tracked_positions)
     {
      reason=StringFormat("position projection count mismatch native=%d tracked=%d",
                          actual_positions,tracked_positions);
      return false;
     }

   int actual_orders=0;
   for(int i=0;i<OrdersTotal();i++)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0 || (ulong)OrderGetInteger(ORDER_MAGIC)!=EA_MAGIC) continue;
      actual_orders++;
      bool found=false;
      for(int c=0;c<ArraySize(g_cycles);c++)
         if(g_cycles[c].active && g_cycles[c].order_ticket==ticket) found=true;
      if(!found)
        {
         reason="EA pending order is absent from the pullback-cycle projection";
         return false;
        }
     }
   int tracked_orders=0;
   for(int c=0;c<ArraySize(g_cycles);c++)
      if(g_cycles[c].active && g_cycles[c].order_ticket>0) tracked_orders++;
   if(actual_orders!=tracked_orders)
     {
      reason=StringFormat("pending projection count mismatch native=%d tracked=%d",
                          actual_orders,tracked_orders);
      return false;
     }
   return true;
  }

void XauReleaseInstallControls()
  {
   if(XauReleaseIsTester()) return;
   ObjectDelete(0,XAU_RELEASE_KILL_BUTTON);
   if(!ObjectCreate(0,XAU_RELEASE_KILL_BUTTON,OBJ_BUTTON,0,0,0)) return;
   ObjectSetInteger(0,XAU_RELEASE_KILL_BUTTON,OBJPROP_CORNER,CORNER_RIGHT_UPPER);
   ObjectSetInteger(0,XAU_RELEASE_KILL_BUTTON,OBJPROP_XDISTANCE,12);
   ObjectSetInteger(0,XAU_RELEASE_KILL_BUTTON,OBJPROP_YDISTANCE,28);
   ObjectSetInteger(0,XAU_RELEASE_KILL_BUTTON,OBJPROP_XSIZE,170);
   ObjectSetInteger(0,XAU_RELEASE_KILL_BUTTON,OBJPROP_YSIZE,30);
   ObjectSetInteger(0,XAU_RELEASE_KILL_BUTTON,OBJPROP_BGCOLOR,clrFireBrick);
   ObjectSetInteger(0,XAU_RELEASE_KILL_BUTTON,OBJPROP_COLOR,clrWhite);
   ObjectSetString(0,XAU_RELEASE_KILL_BUTTON,OBJPROP_TEXT,"KILL XAU EA / FLATTEN");
   ChartRedraw();
  }

void XauReleaseRemoveControls()
  {
   if(!XauReleaseIsTester()) ObjectDelete(0,XAU_RELEASE_KILL_BUTTON);
  }

int OnInit()
  {
   int result=ApprovedStrategyOnInit();
   if(result!=INIT_SUCCEEDED) return result;
   if(!XauReleaseIsTester())
     {
      EventSetTimer(1);
      XauReleaseInstallControls();
      WriteJournal("LIVE-ENVELOPE","LIVE_RELEASE_ARMED","","","Safety",0,0,0,0,0,0,0,
                   "mode="+XauReleaseModeName()+" exact approved Strategy body active");
     }
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(!XauReleaseIsTester() && HasEAOrderOrPosition())
      XauReleaseEmergencyStop("EA deinitialization with native exposure");
   EventKillTimer();
   XauReleaseRemoveControls();
   ApprovedStrategyOnDeinit(reason);
  }

void OnTick()
  {
   if(XauReleaseIsTester())
     {
      ApprovedStrategyOnTick();
      return;
     }
   if(!XauReleaseRuntimeGuard())
     {
      XauReleaseEmergencyStop(g_xau_release_fail_reason);
      return;
     }
   ApprovedStrategyOnTick();
  }

void OnTimer()
  {
   if(XauReleaseIsTester()) return;
   if(!XauReleaseRuntimeGuard())
     {
      XauReleaseEmergencyStop(g_xau_release_fail_reason);
      return;
     }
   string reason="";
   if(XauReleaseProjectionMatches(reason))
     {
      g_xau_release_reconcile_failures=0;
      return;
     }
   g_xau_release_reconcile_failures++;
   if(g_xau_release_reconcile_failures>=InpReconciliationGraceSeconds)
      XauReleaseEmergencyStop(reason);
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK && sparam==XAU_RELEASE_KILL_BUTTON)
      XauReleaseEmergencyStop("operator kill button");
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   ApprovedStrategyOnTradeTransaction(trans,request,result);
  }
