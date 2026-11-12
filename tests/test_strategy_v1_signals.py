import pandas as pd

from domain.xau_usd.strategy_v1 import signals
from domain.xau_usd.strategy_v1.config import StrategyV1Config


def test_indicator_confirmations_use_three_prior_rsi_values_and_exact_macd_gates(monkeypatch):
    index = pd.date_range("2026-07-29T10:00Z", periods=4, freq="5min").astype("datetime64[ns, UTC]")
    close = pd.Series([1.0, 2.0, 3.0, 4.0], index=index)
    rsi_values = pd.Series([25.0, 50.0, 50.0, 50.0], index=index)
    macd_values = pd.DataFrame(
        {
            "macd": [0.0] * 4,
            "signal": [-2.0, 2.0, -1.99, 2.0],
            "histogram": [-0.4, 0.4, -0.4, 0.5],
            "histogram_previous": [-0.5, 0.5, -0.5, 0.6],
        },
        index=index,
    )
    monkeypatch.setattr(signals, "rsi", lambda _close, _config: rsi_values)
    monkeypatch.setattr(signals, "zero_lag_macd", lambda _close, _config: macd_values)

    result = signals.indicator_confirmations(close, StrategyV1Config())

    assert result.rsi_buy_ready.tolist() == [False, False, True, False]
    assert result.macd_buy_confirmed.tolist() == [True, False, False, False]
    assert result.macd_sell_confirmed.tolist() == [False, True, False, False]
