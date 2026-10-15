"""Strict extrema become usable only after their newer neighbour has closed."""

import numpy as np
import pandas as pd

from application.xauusd_trading_strategy_1_vector.execution_batch.protection import structure
from application.xauusd_trading_strategy_1_vector.execution_batch.structure import structural_stops


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


def test_structural_stop_uses_two_newest_strict_extrema():
    class Kernel:
        structure_buy = np.nan
        structure_sell = np.nan
        hi = [
            np.array([10.0, 10.0]),
            np.array([11.0, 7.0]),
            np.array([12.0, 11.0]),
            np.array([13.0, 9.0]),
            np.array([14.0, 12.0]),
        ]

    assert structure.py_func(Kernel(), buy=True) == 9.0
