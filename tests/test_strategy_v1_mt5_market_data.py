import asyncio
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from infrastructure.strategy_v1 import mt5_market_data
from infrastructure.strategy_v1.mt5_market_data import Mt5MarketDataAdapter


def test_mt5_tick_adapter_rounds_request_window_and_filters_exact_utc_bounds(monkeypatch):
    times = pd.to_datetime(["2026-07-29T01:00:00.000Z", "2026-07-29T01:00:01.000Z", "2026-07-29T01:00:02.000Z"]).astype(
        "datetime64[ns, UTC]"
    )
    index = pd.MultiIndex.from_arrays(
        [["XAUUSD!"] * 3, ["opofinance"] * 3, times.floor("s"), times],
        names=["symbol", "broker", "date", "precise_time"],
    )
    ticks = pd.DataFrame(
        {
            "bid": [100.0, 100.1, 100.2],
            "ask": [100.2, 100.3, 100.4],
            "last": [0.0, 0.0, 0.0],
            "volume": np.zeros(3, dtype=np.uint64),
            "flags": np.zeros(3, dtype=np.uint32),
            "volume_real": [0.0, 0.0, 0.0],
        },
        index=index,
    )
    calls = []

    async def fake_get_ticks(time_range: str, *, symbol: str) -> pd.DataFrame:
        calls.append((time_range, symbol))
        return ticks

    monkeypatch.setattr(mt5_market_data, "get_ticks", fake_get_ticks)
    start = datetime(2026, 7, 29, 1, 0, 0, 500_000, tzinfo=UTC)
    end = datetime(2026, 7, 29, 1, 0, 1, 500_000, tzinfo=UTC)
    result = asyncio.run(Mt5MarketDataAdapter().get_ticks("XAUUSD!", start, end))
    assert calls == [("26-07-29.01-00T26-07-29.01-01", "XAUUSD!")]
    assert result.bid.tolist() == [100.1]


def test_mt5_data_adapter_rejects_naive_or_reversed_time_boundaries():
    adapter = Mt5MarketDataAdapter()
    with pytest.raises(ValueError, match="UTC-aware"):
        adapter._time_range(datetime(2026, 7, 29), datetime(2026, 7, 30, tzinfo=UTC))
    with pytest.raises(ValueError, match="after start"):
        adapter._time_range(
            datetime(2026, 7, 30, tzinfo=UTC),
            datetime(2026, 7, 29, tzinfo=UTC),
        )
