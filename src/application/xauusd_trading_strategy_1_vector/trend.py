"""Trend computation utilities for the vectorized XAUUSD strategy.

Extracted from vectorized_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from domain.xau_usd.enums import XauTrend


def compute_bar_time(datetime_series: pd.Series) -> pd.Series:
    """Floor datetime to 15-minute intervals (PERIOD_M15)."""
    if not isinstance(datetime_series, pd.DatetimeIndex):
        datetime_series = pd.to_datetime(datetime_series)
    return datetime_series.dt.floor("15min")


def compute_reference_high(row: pd.Series) -> float:
    """Compute reference high from trend history for a single row."""
    count = int(row["trend_count"])
    if count == 0:
        return 0.0
    if count == 1:
        return float(row["trend_high_0"])
    if count == 2:
        return max(float(row["trend_high_0"]), float(row["trend_high_1"]))
    return max(
        float(row["trend_high_0"]),
        float(row["trend_high_1"]),
        float(row["trend_high_2"]),
    )


def compute_reference_low(row: pd.Series) -> float:
    """Compute reference low from trend history for a single row."""
    count = int(row["trend_count"])
    if count == 0:
        return 0.0
    if count == 1:
        return float(row["trend_low_0"])
    if count == 2:
        return min(float(row["trend_low_0"]), float(row["trend_low_1"]))
    return min(
        float(row["trend_low_0"]),
        float(row["trend_low_1"]),
        float(row["trend_low_2"]),
    )


def compute_references(state: pd.DataFrame) -> pd.DataFrame:
    """Populate reference_high and reference_low columns on the state DataFrame."""
    state["reference_high"] = state.apply(compute_reference_high, axis=1)
    state["reference_low"] = state.apply(compute_reference_low, axis=1)
    return state


def update_trend(state: pd.DataFrame) -> pd.DataFrame:
    """Update trend column based on bid vs reference levels.

    Only rows with trend_count > 0 are updated. Trend becomes UP when bid
    exceeds reference_high, DOWN when bid falls below reference_low, and
    otherwise stays unchanged.
    """
    compute_references(state)
    has_reference = state["trend_count"] > 0
    state.loc[has_reference, "trend"] = np.where(
        state.loc[has_reference, "bid"] > state.loc[has_reference, "reference_high"],
        XauTrend.UP.value,
        np.where(
            state.loc[has_reference, "bid"] < state.loc[has_reference, "reference_low"],
            XauTrend.DOWN.value,
            state.loc[has_reference, "trend"],
        ),
    )
    return state
