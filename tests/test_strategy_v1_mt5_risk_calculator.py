from types import SimpleNamespace

import MetaTrader5 as mt5
import pytest

from infrastructure.strategy_v1.mt5_risk_calculator import Mt5RiskCalculator


def test_mt5_risk_calculator_uses_native_profit_margin_and_symbol_account_metadata(monkeypatch):
    monkeypatch.setattr(mt5, "account_info", lambda: SimpleNamespace(currency="USD", equity=400.0, margin_free=300.0))
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda _symbol: SimpleNamespace(
            point=0.01,
            trade_tick_size=0.01,
            trade_tick_value=1.0,
            trade_contract_size=100.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            swap_long=-50.544,
            swap_short=9.114,
            swap_mode=0,
        ),
    )
    monkeypatch.setattr(mt5, "order_calc_profit", lambda *_args: -600.0)
    monkeypatch.setattr(mt5, "order_calc_margin", lambda *_args: 90.0)

    calculator = Mt5RiskCalculator()
    snapshot = calculator.get_risk_snapshot("XAUUSD!")

    assert snapshot.account_currency == "USD"
    assert snapshot.equity_usd == 400.0
    assert snapshot.contract_size == 100.0
    assert calculator.profit_at_stop_per_lot("XAUUSD!", "buy", 4000.0, 3994.0) == -600.0
    assert calculator.margin_per_lot("XAUUSD!", "sell", 4000.0) == 90.0


def test_mt5_risk_calculator_rejects_non_usd_accounts_and_missing_calculations(monkeypatch):
    monkeypatch.setattr(mt5, "account_info", lambda: SimpleNamespace(currency="EUR"))
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: SimpleNamespace())
    calculator = Mt5RiskCalculator()

    with pytest.raises(ValueError, match="require USD"):
        calculator.get_risk_snapshot("XAUUSD!")
    monkeypatch.setattr(mt5, "order_calc_profit", lambda *_args: None)
    with pytest.raises(RuntimeError, match="profit calculation failed"):
        calculator.profit_at_stop_per_lot("XAUUSD!", "buy", 4000.0, 3994.0)
