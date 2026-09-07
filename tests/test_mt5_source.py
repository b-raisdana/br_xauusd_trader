from pathlib import Path


def test_current_mt5_baseline_is_strict_vector_driven_and_live_inert() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")
    contracts = (root / "src" / "mt5" / "include" / "XauContracts.mqh").read_text(encoding="utf-8")
    assert "#property strict" in source
    assert '#include "generated/CoreVectors.mqh"' in source
    assert "RunCoreVectorSmoke()" in source
    assert "RunExecutionProjectorSmoke()" in source
    assert "RunNativeAdapterSmoke()" in source
    assert "NATIVE_ADAPTER_SMOKE_PASS" in source
    assert "RunVisualPayloadSmoke()" in source
    assert "VISUAL_PAYLOAD_SMOKE_PASS" in source
    assert "TIME_BASIS_PROBE index=" in source
    assert "input bool InpEnableTrading=false" in source
    assert "if(InpEnableTrading)" in source
    assert "input bool InpObserveNativeOutcomes=false" in source
    assert "input long InpStrategyMagic=0" in source
    assert "input bool InpRunCurrentEventLoop=false" in source
    assert "input bool InpEnableTesterExecution=false" in source
    assert "input double InpStrategyCapital=200.0" in source
    assert "trade.Buy" not in source
    assert "trade.Sell" not in source
    for contract in (
        "BreakoutValid",
        "ReversalDirectionalTouch",
        "InitialStop",
        "InitialTarget",
        "PortfolioRiskAllows",
        "UpdateTrend",
        "PullbackPenetrated",
        "StrictPullbackTrend",
        "PreZoneCrossed",
        "ProfitProtectionStop",
        "DailyLossLocked",
        "SessionEndActive",
        "BuildMergedZones",
        "CountDirectionalCrosses",
        "PullbackWindowActive",
        "PullbackUsageAllowed",
        "PullbackTpFailureAction",
        "RestartSameDayLocked",
        "ExecutionTransition",
        "ProtectionModificationValid",
        "CausalTrendThenReversal",
        "MaximumPositions",
        "ConcurrencyAllowsEntry",
        "NativeMarginAllowsEntry",
        "EvaluateProtectedEntry",
        "EvaluateOperationalSafety",
        "HasMinimumFreeSpace",
    ):
        assert contract in contracts
    assert "PARITY_PRICE_TOLERANCE = 1e-9" in contracts
    assert "CORE_VECTOR_SMOKE_PASS vectors=19 mode=inert" in source


def test_execution_projector_is_inert_and_uses_shared_contracts() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauExecution.mqh").read_text(encoding="utf-8")

    assert "InitializeExecutionProjection" in source
    assert "ProjectExecutionOutcome" in source
    assert "ExecutionTransition" in source
    assert "ProtectionModificationValid" in source
    assert "OrderSend" not in source
    assert "CTrade" not in source


def test_execution_ticket_correlation_is_unique_and_inert() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauExecution.mqh").read_text(encoding="utf-8")

    assert "XauExecutionBinding" in source
    assert "BindExecutionOrder" in source
    assert "BindExecutionPosition" in source
    assert "ResolveExecutionRequest" in source
    assert "OrderSend" not in source


def test_execution_binding_persistence_is_atomic_and_fail_closed() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauExecution.mqh").read_text(encoding="utf-8")

    assert "SaveExecutionBindingsAtomically" in source
    assert "LoadExecutionBindings" in source
    assert "SameExecutionBindings" in source
    assert "FileFlush" in source
    assert "FileMove(temporary,0,file_name,FILE_REWRITE)" in source
    assert "XAU_EXECUTION_BINDINGS\\t1" in source


def test_native_outcome_orchestration_is_correlated_before_projection() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauExecution.mqh").read_text(encoding="utf-8")

    assert "ProjectCorrelatedNativeOutcome" in source
    assert "ResolveExecutionRequest" in source
    assert "FindExecutionProjection" in source
    assert "projections[index]=projected" in source


def test_native_callback_is_opt_in_correlated_and_persists_before_publish() -> None:
    root = Path(__file__).parents[1]
    ea = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")
    execution = (root / "src" / "mt5" / "include" / "XauExecution.mqh").read_text(encoding="utf-8")

    assert "OnTradeTransaction" in ea
    assert "if(!InpObserveNativeOutcomes)" in ea
    assert "LoadNativeDealOutcome(transaction,_Symbol,InpStrategyMagic,outcome)" in ea
    assert "PersistThenPublishCorrelatedNativeOutcome" in ea
    assert execution.index("SaveExecutionBindingsAtomically(bindings_file,candidate_bindings)") < (
        execution.index("CopyExecutionProjections(candidate_projections,projections)")
    )
    assert "OrderSend" not in ea
    assert "CTrade" not in ea


def test_mql_state_orders_breakout_before_candle_roll() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauState.mqh").read_text(encoding="utf-8")

    assert "BeginTrendDay" in source
    assert "ProcessTrendTick" in source
    assert "CloseBarBreakoutBeforeRoll" in source
    assert source.index("breakout=BreakoutValid") < source.index("return RecordTrendCandle")
    assert "OrderSend" not in source


def test_mql_coordinator_owns_causal_day_bar_tick_and_close_order() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauCoordinator.mqh").read_text(encoding="utf-8")

    for contract in (
        "BeginCoordinatorDay",
        "BeginCoordinatorBar",
        "ProcessCoordinatorTick",
        "CloseCoordinatorBar",
    ):
        assert contract in source
    assert source.index("ProcessTrendTick(state.trend,bid)") < source.index(
        "UpdateZoneEngagement(state.zones,previous_bid,bid,multi_zone_gap)"
    )
    assert source.index("BreakoutValid") < source.index("RecordTrendCandle")
    assert "OrderSend" not in source
    assert "CTrade" not in source


def test_mql_daily_signal_state_shares_usage_and_attempt_ledgers() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauState.mqh").read_text(encoding="utf-8")

    for contract in (
        "InitializeDailyZoneStates",
        "BeginSignalBar",
        "UpdateZoneEngagement",
        "NextBreakoutId",
        "ConsumeReversalUsage",
        "RecordEntryAttempt",
    ):
        assert contract in source


def test_mql_pullback_window_uses_shared_daily_state() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauState.mqh").read_text(encoding="utf-8")

    for contract in (
        "CreatePullbackWindow",
        "BeginPullbackBar",
        "EvaluatePullbackPrice",
        "RecordPullbackAttempt",
        "RecordPullbackFill",
        "RecordPullbackPendingRemoved",
    ):
        assert contract in source
    assert "PullbackUsageAllowed" in source
    assert "RecordEntryAttempt" in source


def test_mql_strict_conflict_and_tp_state_is_reversible() -> None:
    root = Path(__file__).parents[1]
    state = (root / "src" / "mt5" / "include" / "XauState.mqh").read_text(encoding="utf-8")
    contracts = (root / "src" / "mt5" / "include" / "XauContracts.mqh").read_text(encoding="utf-8")

    for contract in (
        "PreZoneCrossOnce",
        "InitializePullbackTp",
        "ProposePullbackTpExtension",
        "RecordPullbackTpExtension",
        "EvaluatePullbackTpFailure",
        "RecordPullbackTpRestore",
    ):
        assert contract in state
    assert "BlocksOppositeReversal" in contracts


def test_native_adapter_is_read_only_and_uses_broker_apis() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauNative.mqh").read_text(encoding="utf-8")

    assert "OrderCalcProfit" in source
    assert "OrderCalcMargin" in source
    assert "SymbolInfoSessionTrade" in source
    assert "LoadNativeDealOutcome" in source
    assert "ClassifyNativeDealEntry" in source
    assert "HistoryDealSelect" in source
    assert "DEAL_MAGIC" in source
    assert "DEAL_POSITION_ID" in source
    assert "SymbolInfoInteger" in source
    assert "SymbolInfoDouble" in source
    assert "OrderSend" not in source
    assert "CTrade" not in source
    assert "AccountInfo" not in source


def test_contract_smoke_configuration_is_local_and_trading_disabled() -> None:
    root = Path(__file__).parents[1]
    config = (root / "config" / "mt5" / "contract_smoke.ini").read_text(encoding="utf-8")

    assert "AllowLiveTrading=0" in config
    assert "UseLocal=1" in config
    assert "UseRemote=0" in config
    assert "UseCloud=0" in config
    assert "Visual=0" in config
    assert "InpEnableTrading=false" in config
    assert "InpEmitTimeBasisProbe=true" in config
    assert "InpObserveNativeOutcomes=false" in config
    assert "InpStrategyMagic=0" in config
    assert "InpRunCurrentEventLoop=true" in config
    assert "InpEnableTesterExecution=false" in config
    assert "InpStrategyCapital=200.0" in config


def test_current_event_loop_loads_canonical_zones_and_remains_inert() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")

    assert '#include "generated/DailyZones.mqh"' in source
    assert "LoadGeneratedRawZones" in source
    assert "BuildMergedZones" in source
    assert "CopyRates" in source
    assert "ProcessCurrentEventLoopTick" in source
    assert "ProcessCoordinatorTick" in source
    assert "CloseCoordinatorBar" in source
    assert "CURRENT_EVENT_LOOP_DONE breakout=" in source
    assert "OrderSend" not in source
    assert "CTrade" not in source


def test_visual_adapter_is_audit_derived_and_contains_no_trading_path() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauVisual.mqh").read_text(encoding="utf-8")

    for label in ("Time=%s", "Zone=%s", "Entry=%s", "SL=%s", "TP=%s", "Event=%s"):
        assert label in source
    assert "OBJ_RECTANGLE" in source
    assert "OBJ_TEXT" in source
    assert "zone_priority" in source
    assert "OrderSend" not in source
    assert "CTrade" not in source


def test_mql_audit_appends_before_execution_projection() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauAudit.mqh").read_text(encoding="utf-8")

    assert "SerializeOrderAudit" in source
    assert "AppendAuditLine" in source
    assert "AppendOrderThenProject" in source
    assert source.index("AppendAuditLine(audit_file,line)") < source.index(
        "ArrayResize(projections,index+1)"
    )
    assert "FileFlush" in source
    assert "AccountInfo" not in source
    assert "OrderSend" not in source


def test_mql_prepared_request_connects_candidate_risk_safety_audit_and_attempt() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauRequests.mqh").read_text(encoding="utf-8")

    for contract in (
        "PrepareCandidateEntry",
        "HasMinimumFreeSpace",
        "InitialStop",
        "InitialTarget",
        "PortfolioRiskAllows",
        "EvaluateProtectedEntry",
        "BuildPreparedOrderAudit",
        "CommitPreparedEntryAttempt",
    ):
        assert contract in source
    assert "OrderSend" not in source
    assert "AccountInfo" not in source


def test_mql_broker_submission_is_hard_locked_to_strategy_tester() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauTesterBroker.mqh").read_text(encoding="utf-8")
    ea = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")

    assert "MQLInfoInteger(MQL_TESTER)" in source
    assert "prepared.decision != XAU_ENTRY_ALLOWED" in source
    assert source.index("TesterExecutionAllowed(enabled)") < source.index(
        "OrderSend(request,result)"
    )
    assert "InpEnableTesterExecution &&" in ea
    assert "(!(bool)MQLInfoInteger(MQL_TESTER)" in ea
    assert "OrderSend" not in ea


def test_mql_tester_risk_snapshot_is_project_filtered_and_tester_locked() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauTesterRisk.mqh").read_text(encoding="utf-8")

    assert "TesterExecutionAllowed(enabled)" in source
    assert "DEAL_SYMBOL" in source and "DEAL_MAGIC" in source
    assert "POSITION_SYMBOL" in source and "POSITION_MAGIC" in source
    assert "ORDER_SYMBOL" in source and "ORDER_MAGIC" in source
    assert "position_closed[index]" in source
    assert "NativeCashRisk" in source
    assert "ACCOUNT_LOGIN" not in source
    assert "ACCOUNT_NAME" not in source
    assert "TesterPositionRiskFree" in source


def test_mql_tester_risk_treats_break_even_or_better_stop_as_zero_open_risk() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauTesterRisk.mqh").read_text(encoding="utf-8")

    assert "const bool protected_stop=" in source
    assert "stop >= entry" in source
    assert "stop <= entry" in source
    assert "if(!protected_stop && !NativeCashRisk" in source


def test_tester_candidate_flow_is_audit_before_send_and_binding_after_acceptance() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")

    assert "ProcessTesterCandidates" in source
    assert source.index("AppendOrderThenProject(ORDER_AUDIT_FILE") < source.index(
        "SubmitTesterPreparedEntry(true"
    )
    assert source.index("SubmitTesterPreparedEntry(true") < source.index(
        "CommitPreparedEntryAttempt(g_market_state"
    )
    assert "BindExecutionOrder" in source
    assert "ApplyProjectOwnedNativeOutcome" in source
    assert "TESTER_RISK_DONE net=" in source


def test_tester_session_end_cancels_and_flattens_only_project_state() -> None:
    root = Path(__file__).parents[1]
    ea = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")
    broker = (root / "src" / "mt5" / "include" / "XauTesterBroker.mqh").read_text(encoding="utf-8")

    assert "NativeContainingTradeSession" in ea
    assert "SessionEndActive" in ea
    assert "CancelTesterPendingOrders" in ea
    assert "CloseTesterPositions" in ea
    assert "ApplyTesterPendingCancellation" in ea
    assert "ORDER_MAGIC" in broker and "POSITION_MAGIC" in broker
    assert "MQLInfoInteger(MQL_TESTER)" in broker
    assert "ModifyTesterProtection" in broker


def test_tester_same_day_restart_simulation_flattens_before_candidates() -> None:
    root = Path(__file__).parents[1]
    ea = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")
    config = (root / "config" / "mt5" / "tester_restart.ini").read_text(encoding="utf-8")

    assert "input bool InpSimulateSameDayRestart=false;" in ea
    assert "EvaluateOperationalSafety(session_active,g_restart_lock)" in ea
    assert "TESTER_RESTART_FLAT" in ea
    assert ea.index("ExecuteTesterOperationalSafety(tick)") < ea.index(
        "ProcessTesterCandidates(tick,candidates)"
    )
    assert "InpSimulateSameDayRestart && !InpEnableTesterExecution" in ea
    assert "AllowLiveTrading=0" in config
    assert "InpSimulateSameDayRestart=true" in config
    assert "UseRemote=0" in config and "UseCloud=0" in config


def test_pullback_tp_runtime_is_bound_to_project_position_and_tester_broker() -> None:
    root = Path(__file__).parents[1]
    ea = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")
    broker = (root / "src" / "mt5" / "include" / "XauTesterBroker.mqh").read_text(encoding="utf-8")

    assert "ManageTesterPullbackTp" in ea
    assert "LoadPullbackStrictDirections" in ea
    assert "PreZoneCrossOnce" in ea
    assert "ProposePullbackTpExtension" in ea
    assert "EvaluatePullbackTpFailure" in ea
    assert "RecordPullbackTpRestore" in ea
    assert "CloseTesterPosition" in ea and "CloseTesterPosition" in broker
    assert "POSITION_MAGIC" in broker and "MQLInfoInteger(MQL_TESTER)" in broker
    assert "TESTER_TP_DONE" in ea
    assert "TESTER_ATTRIBUTION" in ea
    assert "TESTER_TP_STATE_RECOVERED" in ea
    assert "TESTER_PULLBACK_FILL_RECOVERED" in ea
    assert "status != XAU_EXECUTION_FILLED" in ea
    assert "status != XAU_EXECUTION_CANCELLED" in ea
    assert "ORDER_TYPE_BUY_STOP ? ORDER_TYPE_BUY" in (
        root / "src" / "mt5" / "include" / "XauTesterRisk.mqh"
    ).read_text(encoding="utf-8")


def test_tester_symbol_specification_excludes_account_identity() -> None:
    root = Path(__file__).parents[1]
    ea = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")

    assert "TESTER_SYMBOL_SPEC" in ea
    assert "SYMBOL_TRADE_CONTRACT_SIZE" in ea
    assert "SYMBOL_TRADE_TICK_SIZE" in ea and "SYMBOL_TRADE_TICK_VALUE" in ea
    assert "SYMBOL_TRADE_STOPS_LEVEL" in ea and "SYMBOL_TRADE_FREEZE_LEVEL" in ea
    assert "NativeContainingTradeSession" in ea
    assert "ACCOUNT_LOGIN" not in ea and "ACCOUNT_NAME" not in ea


def test_200_profile_acceptance_config_cannot_enable_live_trading() -> None:
    root = Path(__file__).parents[1]
    config = (root / "config" / "mt5" / "tester_200.ini").read_text(encoding="utf-8")

    assert "AllowLiveTrading=0" in config
    assert "InpEnableTrading=false" in config
    assert "InpEnableTesterExecution=true" in config
    assert "InpObserveNativeOutcomes=true" in config
    assert "InpStrategyCapital=200.0" in config


def test_multiday_profile_is_locked_to_canonical_zone_range_and_local_tester() -> None:
    config = (Path(__file__).parents[1] / "config" / "mt5" / "tester_multiday_200.ini").read_text(
        encoding="utf-8"
    )

    assert "FromDate=2026.07.29" in config and "ToDate=2026.08.29" in config
    assert "Model=4" in config and "Optimization=0" in config
    assert "AllowLiveTrading=0" in config
    assert "UseLocal=1" in config
    assert "UseRemote=0" in config and "UseCloud=0" in config
    assert "InpEnableTesterExecution=true" in config
    assert "InpSimulateSameDayRestart=false" in config
    assert "Deposit=200" in config
    assert "UseRemote=0" in config and "UseCloud=0" in config


def test_300_profile_acceptance_config_cannot_enable_live_trading() -> None:
    root = Path(__file__).parents[1]
    config = (root / "config" / "mt5" / "tester_300.ini").read_text(encoding="utf-8")

    assert "AllowLiveTrading=0" in config
    assert "InpEnableTrading=false" in config
    assert "InpEnableTesterExecution=true" in config
    assert "InpObserveNativeOutcomes=true" in config
    assert "InpStrategyCapital=300.0" in config
    assert "Deposit=300" in config
    assert "UseRemote=0" in config and "UseCloud=0" in config
