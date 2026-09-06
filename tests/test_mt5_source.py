from pathlib import Path


def test_current_mt5_baseline_is_strict_vector_driven_and_live_inert() -> None:
    root = Path(__file__).parents[1]
    source = (root / "src" / "mt5" / "XAUUSD_MVP.mq5").read_text(encoding="utf-8")
    contracts = (root / "src" / "mt5" / "include" / "XauContracts.mqh").read_text(encoding="utf-8")
    assert "#property strict" in source
    assert '#include "generated/CoreVectors.mqh"' in source
    assert "RunCoreVectorSmoke()" in source
    assert "input bool InpEnableTrading=false" in source
    assert "if(InpEnableTrading)" in source
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
    ):
        assert contract in contracts
    assert "PARITY_PRICE_TOLERANCE = 1e-9" in contracts
