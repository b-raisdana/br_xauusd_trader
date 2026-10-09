"""Strict extrema become usable only after their newer neighbour has closed."""

import numpy as np
import pandas as pd
from test_batch_execution_replay import frames
from test_oracle_scalar_replay import candidate, config

from application.xauusd_trading_strategy_1_vector.execution_batch.structure import structural_stops
from application.xauusd_trading_strategy_1_vector.vectorized_replay import VectorizedExecutionReplay


def test_structure_candidates_match_closed_history_without_lookahead():
    times = pd.date_range("2026-09-24", periods=10, freq="15min", tz="UTC").as_unit("ns")
    lows = [97.0, 100.0, 98.0, 102.0, 101.0, 105.0, 110.0, 112.0, 111.0, 113.0]
    bars = pd.DataFrame({"bar_time": times, "low": lows, "high": np.asarray(lows) + 5.0})
    streams = pd.DataFrame({"precise_time": [times[8] + pd.Timedelta(minutes=14), times[9] + pd.Timedelta(minutes=15)]})
    before_after = structural_stops(streams, bars)
    assert before_after[:, 0].tolist() == [101.0, 111.0]
    modified = bars.copy()
    modified.loc[9, "low"] = 50.0
    changed = structural_stops(streams, modified)
    assert changed[0, 0] == before_after[0, 0]
    assert changed[1, 0] != before_after[1, 0]


def test_replay_uses_native_closed_candles_for_structural_stop():
    times = pd.DatetimeIndex(["2026-09-24 03:00", "2026-09-24 03:01"], tz="UTC")
    streams, zones, candidates, windows = frames([103.0, 116.0], times, {0: [candidate()]}, {})
    zones.loc[zones.zone_id.eq("target"), "low"] = 150.0
    zones.loc[zones.zone_id.eq("target"), "high"] = 152.0
    zones.loc[zones.zone_id.eq("next"), "low"] = 160.0
    zones.loc[zones.zone_id.eq("next"), "high"] = 162.0
    lows = [97.0, 100.0, 98.0, 102.0, 101.0, 105.0, 110.0, 112.0, 111.0, 113.0]
    bars = pd.DataFrame(
        {
            "bar_time": pd.date_range("2026-09-24", periods=10, freq="15min", tz="UTC").as_unit("ns"),
            "low": lows,
            "high": np.asarray(lows) + 5.0,
        }
    )
    engine = VectorizedExecutionReplay(config(), "test")
    tables = engine.run(streams, zones, candidates, windows, bars)
    assert tables[3].stop_loss.iloc[-1] == 111.0
    assert engine.modifications.resulting_stop_loss.iloc[-1] == 111.0
