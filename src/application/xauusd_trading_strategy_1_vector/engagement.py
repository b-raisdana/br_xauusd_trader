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
    previous_bid = state["last_bid"].shift(1)
    previous_bid.iloc[0] = state.iloc[0]["bar_open"]
    current_bid = state["bid"]

    crosses = count_directional_crosses_vectorized(zones, previous_bid, current_bid)
    state["multi_zone_tick_gap"] = crosses > 1

    multi_zone_gap = state["multi_zone_tick_gap"]

    for zone in zones:
        inside_zone = (current_bid >= zone.low) & (current_bid <= zone.high)

        state.loc[multi_zone_gap & inside_zone, "buy_engaged"] = True
        state.loc[multi_zone_gap & inside_zone, "sell_engaged"] = True

        buy_cross = (~state["buy_engaged"]) & (previous_bid < zone.low) & (current_bid >= zone.low)
        state.loc[buy_cross, "buy_engaged"] = True

        sell_cross = (~state["sell_engaged"]) & (previous_bid > zone.high) & (current_bid <= zone.high)
        state.loc[sell_cross, "sell_engaged"] = True

    return state
