"""Trend computation utilities for the vectorized XAUUSD strategy.

Extracted from the_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from br_py_log_n_profile import log_d, profile_it
from numpy.typing import NDArray

from application.xauusd_trading_strategy_1_vector.config.trend_points import (
    TREND_SIDES,
    trend_columns,
    trend_point_count,
)
from application.xauusd_trading_strategy_1_vector.domain.schema import (
    PerTickState,
    ReferenceTrendInfo,
    TrendInfo,
    VectorizedTick,
)
from br_pre_commit import pandera_validate
from domain.xau_usd.enums import XauTrend
from helper.importer import pt


@profile_it
@pandera_validate
def compute_bar_time(datetime_series: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Floor datetime to 15-minute intervals (PERIOD_M15)."""
    return datetime_series.floor("15min")
    # return pd.to_datetime(ts // (60 * 15))


@pandera_validate
def compute_reference_high(tick_state_row: pt.Series[float]) -> float:
    """Compute reference high from trend history for a single row."""
    # log_w(NOT_TESTED)
    count = int(tick_state_row["trend_count"])
    columns = trend_columns("high")[: min(count, trend_point_count())]
    if not columns:
        return 0.0
    return max(float(tick_state_row[column]) for column in columns)


@pandera_validate
def compute_reference_low(tick_state_row: pt.Series[float]) -> float:
    """Compute reference low from trend history for a single row."""
    # log_w(NOT_TESTED)
    count = int(tick_state_row["trend_count"])
    columns = trend_columns("low")[: min(count, trend_point_count())]
    if not columns:
        return 0.0
    return min(float(tick_state_row[column]) for column in columns)


@profile_it
def _reduce_trend_arrays(
    trend_arrays: list[NDArray[np.float64]],
    counts: NDArray[np.int64],
    compare: Callable[[NDArray[np.float64], NDArray[np.float64]], NDArray[np.bool_]],
) -> NDArray[np.float64]:
    """Reduce per-point trend arrays to a single reference array.

    For each slot i (starting at 1), the value at slot i replaces the
    running reduced value where counts > i and compare(arr, reduced)
    is true. Slots beyond the configured trend point count are ignored;
    ordered comparisons preserve scalar ties and NaNs.
    """
    reduced = trend_arrays[0]
    log_d(f"_reduce_trend_arrays loops for {len(trend_arrays[1:])} times.")
    for i, arr in enumerate(trend_arrays[1:], start=1):
        reduced = np.where((counts > i) & compare(arr, reduced), arr, reduced)
    return reduced


@profile_it
@pandera_validate
def compute_references(per_tick_state: pt.DataFrame[TrendInfo]) -> pt.DataFrame[ReferenceTrendInfo]:
    """Populate reference_high and reference_low columns on the per-tick DataFrame."""

    counts = per_tick_state["trend_count"].to_numpy(dtype=np.int64)
    for side, compare in zip(TREND_SIDES, (np.greater, np.less), strict=True):
        trend_arrays = [per_tick_state[column].to_numpy(dtype=float) for column in trend_columns(side)]
        reduced = _reduce_trend_arrays(trend_arrays, counts, compare)
        per_tick_state[f"reference_{side}"] = np.where(counts == 0, 0.0, reduced)
    return per_tick_state


@profile_it
@pandera_validate
def update_trend(
    ticks: pt.DataFrame[VectorizedTick], per_tick_state: pt.DataFrame[PerTickState]
) -> pt.DataFrame[PerTickState]:
    """Update trend column based on bid vs reference levels.

    Only rows with trend_count > 0 are updated. Trend becomes UP when bid
    exceeds reference_high, DOWN when bid falls below reference_low, and
    otherwise stays unchanged.
    """

    compute_references(per_tick_state)
    has_reference = per_tick_state["trend_count"] > 0
    changes = pd.Series(
        np.where(
            has_reference & (ticks["bid"] > per_tick_state["reference_high"]),
            XauTrend.UP.value,
            np.where(has_reference & (ticks["bid"] < per_tick_state["reference_low"]), XauTrend.DOWN.value, np.nan),
        ),
        index=per_tick_state.index,
    )
    per_tick_state["trend"] = (
        changes.groupby(ticks["broker_day"], sort=False).ffill().fillna(XauTrend.NONE.value).astype(int)
    )
    return per_tick_state
