"""Trend computation utilities for the vectorized XAUUSD strategy.

Extracted from vectorized_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from br_py_log_n_profile.do_log.log_it import NOT_TESTED, log_w

from domain.schemas.xauusd_vector_strategy import PerTickBaseState, ReferenceInput, ReferenceResult
from domain.xau_usd.enums import XauTrend
from helper.importer import pt
from helper.pandera import pandera_validate


@pandera_validate(allow_pandas_dataframe=True)
def compute_bar_time(datetime_series: pt.Series[pd.Timestamp]) -> pt.Series[pd.Timestamp]:
    """Floor datetime to 15-minute intervals (PERIOD_M15)."""
    if isinstance(datetime_series, pd.DatetimeIndex):
        return datetime_series.floor("15min")
    return datetime_series.dt.floor("15min")


@pandera_validate(allow_pandas_dataframe=True)
def compute_reference_high(tick_state_row: pd.Series) -> float:
    """Compute reference high from trend history for a single row."""
    log_w(NOT_TESTED)
    count = int(tick_state_row["trend_count"])
    if count == 0:
        return 0.0
    if count == 1:
        return float(tick_state_row["trend_high_0"])
    if count == 2:
        return max(float(tick_state_row["trend_high_0"]), float(tick_state_row["trend_high_1"]))
    return max(
        float(tick_state_row["trend_high_0"]),
        float(tick_state_row["trend_high_1"]),
        float(tick_state_row["trend_high_2"]),
    )


@pandera_validate(allow_pandas_dataframe=True)
def compute_reference_low(tick_state_row: pd.Series) -> float:
    """Compute reference low from trend history for a single row."""
    log_w(NOT_TESTED)
    count = int(tick_state_row["trend_count"])
    if count == 0:
        return 0.0
    if count == 1:
        return float(tick_state_row["trend_low_0"])
    if count == 2:
        return min(float(tick_state_row["trend_low_0"]), float(tick_state_row["trend_low_1"]))
    return min(
        float(tick_state_row["trend_low_0"]),
        float(tick_state_row["trend_low_1"]),
        float(tick_state_row["trend_low_2"]),
    )


@pandera_validate(inplace=True)
def compute_references(per_tick_state: pt.DataFrame[ReferenceInput]) -> pt.DataFrame[ReferenceResult]:
    """Populate reference_high and reference_low columns on the per-tick DataFrame."""
    log_w(NOT_TESTED)
    counts = per_tick_state["trend_count"].to_numpy(dtype=np.int64)
    for side, compare in (("high", np.greater), ("low", np.less)):
        first = per_tick_state[f"trend_{side}_0"].to_numpy(dtype=float)
        second = per_tick_state[f"trend_{side}_1"].to_numpy(dtype=float)
        third = per_tick_state[f"trend_{side}_2"].to_numpy(dtype=float)
        # Ordered comparisons retain Python max/min behavior for ties and NaNs.
        first_two = np.where(compare(second, first), second, first)
        first_three = np.where(compare(third, first_two), third, first_two)
        per_tick_state[f"reference_{side}"] = np.where(
            counts == 0, 0.0, np.where(counts == 1, first, np.where(counts == 2, first_two, first_three))
        )
    return per_tick_state


@pandera_validate(allow_pandas_dataframe=True)
def update_trend(per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PerTickBaseState]:
    """Update trend column based on bid vs reference levels.

    Only rows with trend_count > 0 are updated. Trend becomes UP when bid
    exceeds reference_high, DOWN when bid falls below reference_low, and
    otherwise stays unchanged.
    """
    log_w(NOT_TESTED)
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
