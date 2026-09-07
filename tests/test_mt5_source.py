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
    assert "OnTradeTransaction" not in source
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
    ):
        assert contract in contracts
    assert "PARITY_PRICE_TOLERANCE = 1e-9" in contracts
    assert "CORE_VECTOR_SMOKE_PASS vectors=18 mode=inert" in source


def test_execution_projector_is_inert_and_uses_shared_contracts() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "include" / "XauExecution.mqh").read_text(encoding="utf-8")

    assert "InitializeExecutionProjection" in source
    assert "ProjectExecutionOutcome" in source
    assert "ExecutionTransition" in source
    assert "ProtectionModificationValid" in source
    assert "OrderSend" not in source
    assert "CTrade" not in source


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
