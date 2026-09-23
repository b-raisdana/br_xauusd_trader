"""Zone engagement utilities for the vectorized XAUUSD strategy.

Extracted from vectorized_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

from typing import List

import pandas as pd

from domain.xau_usd.models import XauZone


def count_directional_crosses_vectorized(
    zones: List[XauZone],
    previous_bid: pd.Series,
    current_bid: pd.Series,
) -> pd.Series:
    """Count directional zone crosses for each row.

    An upward cross is previous_bid < zone.low <= current_bid.
    A downward cross is previous_bid > zone.high >= current_bid.
    """
    crosses = pd.Series(0, index=previous_bid.index)
    for zone in zones:
        upward_cross = (previous_bid < zone.low) & (current_bid >= zone.low)
        crosses += upward_cross.astype(int)
        downward_cross = (previous_bid > zone.high) & (current_bid <= zone.high)
        crosses += downward_cross.astype(int)
    return crosses


def update_zone_engagement(
    state: pd.DataFrame,
    zones: List[XauZone],
) -> pd.DataFrame:
    """Update buy/sell engagement based on bid movement across zone boundaries.

    Handles multi-zone tick gaps (crosses > 1) by setting engagement based on
    current bid position inside the zone. For single crosses, engagement is
    set incrementally only when not already engaged.
    """
    bar_changed = state["bar_time"].ne(state["bar_time"].shift())
    bar_changed = state["bar_time"].ne(state["bar_time"].shift())
    bar_ids = bar_changed.cumsum()
    previous_bid = state["bid"].shift().where(~bar_changed, state["bid"])
    current_bid = state["bid"]
    crosses = count_directional_crosses_vectorized(zones, previous_bid, current_bid)
    multi_zone_gap = crosses > 1
    state["multi_zone_tick_gap"] = multi_zone_gap
    buy = pd.Series(False, index=state.index)
    sell = pd.Series(False, index=state.index)
    for zone in zones:
        inside_zone = current_bid.between(zone.low, zone.high)
        entered_inside = (bar_changed | multi_zone_gap) & inside_zone
        buy |= entered_inside | (~multi_zone_gap & (previous_bid < zone.low) & (current_bid >= zone.low))
        sell |= entered_inside | (~multi_zone_gap & (previous_bid > zone.high) & (current_bid <= zone.high))
    state["buy_engaged"] = buy.groupby(bar_ids, sort=False).cummax()
    state["sell_engaged"] = sell.groupby(bar_ids, sort=False).cummax()
    return state
