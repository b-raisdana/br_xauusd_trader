"""Trend computation utilities for the vectorized XAUUSD strategy.

Extracted from the_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from br_py_log_n_profile import profile_it

from application.xauusd_trading_strategy_1_vector.config.core_vectors import CoreVectors
from application.xauusd_trading_strategy_1_vector.domain.schema import PerTickBaseState, ReferenceInput, ReferenceResult
from domain.xau_usd.enums import XauTrend
from helper.importer import pt
from helper.pandera import pandera_validate


def _get_trend_max_points() -> int:
    """Get the maximum number of trend points from config."""
    return CoreVectors.current().vec_trend_max_points


@profile_it
@pandera_validate(allow_pandas_dataframe=True)
def compute_bar_time(datetime_series: pt.Series[pd.Timestamp]) -> pt.Series[pd.Timestamp]:
    """Floor datetime to 15-minute intervals (PERIOD_M15)."""
    if isinstance(datetime_series, pd.DatetimeIndex):
        return datetime_series.floor("15min")
    return datetime_series.dt.floor("15min")


@profile_it
@pandera_validate(allow_pandas_dataframe=True)
def compute_reference_high(tick_state_row: pd.Series) -> float:
    """Compute reference high from trend history for a single row."""
    # log_w(NOT_TESTED)
    max_points = _get_trend_max_points()
    count = int(tick_state_row["trend_count"])
    if count == 0:
        return 0.0
    if count == 1:
        return float(tick_state_row["trend_high_0"])
    values = [float(tick_state_row[f"trend_high_{i}"]) for i in range(min(count, max_points))]
    return max(values)


@pandera_validate(allow_pandas_dataframe=True)
def compute_reference_low(tick_state_row: pd.Series) -> float:
    """Compute reference low from trend history for a single row."""
    # log_w(NOT_TESTED)
    max_points = _get_trend_max_points()
    count = int(tick_state_row["trend_count"])
    if count == 0:
        return 0.0
    if count == 1:
        return float(tick_state_row["trend_low_0"])
    values = [float(tick_state_row[f"trend_low_{i}"]) for i in range(min(count, max_points))]
    return min(values)


@pandera_validate(inplace=True)
def compute_references(per_tick_state: pt.DataFrame[ReferenceInput]) -> pt.DataFrame[ReferenceResult]:
    """Populate reference_high and reference_low columns on the per-tick DataFrame."""

    max_points = _get_trend_max_points()
    counts = per_tick_state["trend_count"].to_numpy(dtype=np.int64)
    for side, compare in (("high", np.greater), ("low", np.less)):
        trend_arrays = [per_tick_state[f"trend_{side}_{i}"].to_numpy(dtype=float) for i in range(max_points)]
        reduced = trend_arrays[0]
        # Ignore unused slots; ordered comparisons preserve scalar ties and NaNs.
        for i, arr in enumerate(trend_arrays[1:], start=1):
            reduced = np.where((counts > i) & compare(arr, reduced), arr, reduced)
        per_tick_state[f"reference_{side}"] = np.where(counts == 0, 0.0, reduced)
    return per_tick_state


@profile_it
@pandera_validate(allow_pandas_dataframe=True)
def update_trend(per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PerTickBaseState]:
    """Update trend column based on bid vs reference levels.

    Only rows with trend_count > 0 are updated. Trend becomes UP when bid
    exceeds reference_high, DOWN when bid falls below reference_low, and
    otherwise stays unchanged.
    """

    compute_references(per_tick_state)
    has_reference = per_tick_state["trend_count"] > 0
    changes = pd.Series(
        np.where(
            has_reference & (per_tick_state["bid"] > per_tick_state["reference_high"]),
            XauTrend.UP.value,
            np.where(
                has_reference & (per_tick_state["bid"] < per_tick_state["reference_low"]), XauTrend.DOWN.value, np.nan
            ),
        ),
        index=per_tick_state.index,
    )
    per_tick_state["trend"] = (
        changes.groupby(per_tick_state["broker_day"], sort=False).ffill().fillna(XauTrend.NONE.value).astype(int)
    )
    return per_tick_state
