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
