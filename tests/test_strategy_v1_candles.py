from datetime import UTC, datetime

import pandas as pd
import pandera
import pytest

from domain.xau_usd.strategy_v1 import closed_candles
from domain.xau_usd.strategy_v1.config import StrategyV1Config


def _candles() -> pd.DataFrame:
    index = pd.MultiIndex.from_arrays(
        [
            ["M5"] * 3,
            pd.date_range("2026-07-29T10:00Z", periods=3, freq="5min"),
        ],
        names=["timeframe", "date"],
    )
    return pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "high": [2.0, 3.0, 4.0],
            "low": [0.0, 1.0, 2.0],
            "close": [1.5, 2.5, 3.5],
        },
        index=index,
    )


def test_closed_candles_include_equality_and_exclude_the_live_candle():
    result = closed_candles(_candles(), datetime(2026, 7, 29, 10, 10, tzinfo=UTC), 5, StrategyV1Config())

    assert result.index.get_level_values("date").tolist() == list(
        pd.date_range("2026-07-29T10:00Z", periods=2, freq="5min"),
    )
    assert str(result.index.get_level_values("date").dtype) == "datetime64[ns, UTC]"


def test_closed_candles_reject_wrong_timeframe_or_naive_as_of():
    with pytest.raises(ValueError, match="timeframe_minutes"):
        closed_candles(_candles(), datetime(2026, 7, 29, 10, 10, tzinfo=UTC), 1, StrategyV1Config())
    with pytest.raises(ValueError, match="UTC-aware"):
        closed_candles(_candles(), datetime(2026, 7, 29, 10, 10), 5, StrategyV1Config())


def test_closed_candles_reject_malformed_ohlc():
    bad = _candles()
    bad.loc[bad.index[0], "high"] = 0.5

    with pytest.raises(pandera.errors.SchemaErrors):
        closed_candles(bad, datetime(2026, 7, 29, 10, 10, tzinfo=UTC), 5, StrategyV1Config())
