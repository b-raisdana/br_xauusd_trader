"""Replay boundaries reject malformed data before the numeric scan."""

import numpy as np
import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors
from test_batch_execution_replay import frames
from test_oracle_scalar_replay import config

from application.xauusd_trading_strategy_1_vector.execution_batch.structure import structural_stops
from application.xauusd_trading_strategy_1_vector.vectorized_replay import VectorizedExecutionReplay


def test_structure_requires_utc_stream_times():
    streams = pd.DataFrame({"precise_time": pd.date_range("2026-09-24", periods=1)})
    with pytest.raises((SchemaError, SchemaErrors)):
        structural_stops(streams, None)


@pytest.mark.parametrize("indexed", [False, True])
def test_structure_accepts_column_or_index_candle_times(indexed):
    times = pd.date_range("2026-09-24", periods=3, freq="15min", tz="UTC").as_unit("ns")
    candles = pd.DataFrame({"bar_time": times, "high": [103.0, 102.0, 103.0], "low": [101.0, 100.0, 101.0]})
    streams = pd.DataFrame({"precise_time": [times[-1] + pd.Timedelta(minutes=15)]})
    expected = structural_stops(streams, candles)
    if indexed:
        candles = candles.set_index("bar_time")
    np.testing.assert_array_equal(structural_stops(streams, candles), expected)


def test_structure_requires_candle_time_identity():
    streams = pd.DataFrame({"precise_time": pd.date_range("2026-09-24", periods=1, tz="UTC").as_unit("ns")})
    with pytest.raises((SchemaError, SchemaErrors)):
        structural_stops(streams, pd.DataFrame({"high": [102.0], "low": [100.0]}))


def test_replay_rejects_incomplete_nonempty_windows_before_execution():
    streams, zones, candidates, _ = frames([103.0], pd.DatetimeIndex(["2026-09-24"], tz="UTC"), {}, {})
    engine = VectorizedExecutionReplay(config(), "test")
    with pytest.raises((SchemaError, SchemaErrors)):
        engine.run(streams, zones, candidates, pd.DataFrame({"stream_tick": [0]}))
    assert engine.last_tick == -1
