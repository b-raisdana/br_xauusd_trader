"""Zone engagement utilities for the vectorized XAUUSD strategy.

Extracted from the_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from br_py_log_n_profile import profile_it

from application.xauusd_trading_strategy_1_vector.domain.schema import (
    PerTickState,
    VectorizedTick,
)
from br_pre_commit import pandera_validate
from domain.xau_usd.models import XauZone
from helper.importer import pt


@pandera_validate(allow_pandas_dataframe=True)
def count_directional_crosses_vectorized(
    zones: List[XauZone],
    previous_bid: pt.Series[float],
    current_bid: pt.Series[float],
) -> pt.Series[int]:
    """Count directional zone crosses for each row.

    An upward cross is previous_bid < zone.low <= current_bid.
    A downward cross is previous_bid > zone.high >= current_bid.
    """

    crosses = pd.Series(0, index=previous_bid.index)
    for zone in zones:
        upward_cross = previous_bid.lt(zone.low) & current_bid.ge(zone.low)
        crosses += upward_cross.astype(int)
        downward_cross = previous_bid.gt(zone.high) & current_bid.le(zone.high)
        crosses += downward_cross.astype(int)
    return crosses


@profile_it
@pandera_validate
def update_zone_engagement(
    ticks: pt.DataFrame[VectorizedTick],
    per_tick_state: pt.DataFrame[PerTickState],  # EngagementInput],
    zones: List[XauZone],
) -> pt.DataFrame[PerTickState]:
    """Update buy/sell engagement based on bid movement across zone boundaries.

    Handles multi-zone tick gaps (crosses > 1) by setting engagement based on
    current bid position inside the zone. For single crosses, engagement is
    set incrementally only when not already engaged.
    """

    bar_changed = ticks["bar_time"].ne(ticks["bar_time"].shift()).to_numpy()
    bar_ids = bar_changed.cumsum()
    current_bid = ticks["bid"].to_numpy()
    previous_bid = np.where(bar_changed, current_bid, ticks["bid"].shift())
    crosses = count_directional_crosses_vectorized(
        zones, pd.Series(previous_bid, index=per_tick_state.index), ticks["bid"]
    )
    multi_zone_gap = crosses.to_numpy() > 1
    per_tick_state["multi_zone_tick_gap"] = multi_zone_gap
    buy = np.zeros(len(per_tick_state), dtype=bool)
    sell = np.zeros(len(per_tick_state), dtype=bool)
    for zone in zones:
        inside_zone = (current_bid >= zone.low) & (current_bid <= zone.high)
        opened_inside = bar_changed & inside_zone
        buy_cross = (previous_bid < zone.low) & (current_bid >= zone.low)
        sell_cross = (previous_bid > zone.high) & (current_bid <= zone.high)
        zone_buy = pd.Series(np.where(multi_zone_gap, inside_zone, opened_inside | buy_cross))
        zone_sell = pd.Series(np.where(multi_zone_gap, inside_zone, opened_inside | sell_cross))
        per_tick_state[f"buy_engaged:{zone.id}"] = zone_buy.groupby(bar_ids, sort=False).cummax().to_numpy()
        per_tick_state[f"sell_engaged:{zone.id}"] = zone_sell.groupby(bar_ids, sort=False).cummax().to_numpy()
        buy |= per_tick_state[f"buy_engaged:{zone.id}"].to_numpy()
        sell |= per_tick_state[f"sell_engaged:{zone.id}"].to_numpy()
    per_tick_state["buy_engaged"] = pd.Series(buy, index=per_tick_state.index).groupby(bar_ids, sort=False).cummax()
    per_tick_state["sell_engaged"] = pd.Series(sell, index=per_tick_state.index).groupby(bar_ids, sort=False).cummax()
    return per_tick_state
