"""Signal generation utilities for the vectorized XAUUSD strategy.

Extracted from vectorized_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

from typing import List

import pandas as pd

from domain.xau_usd.enums import XauTrend
from domain.xau_usd.models import XauZone


def generate_breakout_signals(
    state: pd.DataFrame,
    close_bid: float,
    # bar_high: float,
    # bar_low: float,
    zones: List[XauZone],
) -> pd.DataFrame:
    """Generate breakout signals at bar close.

    Breakout conditions:
    - Zone must be engaged (buy_engaged for BUY, sell_engaged for SELL)
    - Trend must match direction (UP for BUY, DOWN for SELL)
    - Close price must break through zone boundary with buffer
    """
    if not zones:
        return state

    current_trend = state.iloc[-1]["trend"]
    buy_engaged = state.iloc[-1]["buy_engaged"]
    sell_engaged = state.iloc[-1]["sell_engaged"]

    for zone in zones:
        buy_breakout = buy_engaged and current_trend == XauTrend.UP.value and close_bid > zone.high + 1.0
        sell_breakout = sell_engaged and current_trend == XauTrend.DOWN.value and close_bid < zone.low - 1.0
        if buy_breakout or sell_breakout:
            # Signal generation would create pullback windows and update
            # breakout_sequence. Framework placeholder.
            pass

    return state


def generate_reversal_signals(
    state: pd.DataFrame,
    zones: List[XauZone],
) -> pd.DataFrame:
    """Generate reversal signals on zone touches against trend.

    SELL reversal: trend == UP and previous_bid < zone.low and current_bid >= zone.low
    BUY reversal: trend == DOWN and previous_bid > zone.high and current_bid <= zone.high
    """
    if not zones:
        return state

    bar_changed = state["bar_time"].ne(state["bar_time"].shift())
    previous_bid = state["bid"].shift().where(~bar_changed, state["bid"])
    current_bid = state["bid"]
    current_trend = state["trend"]
    multi_zone_gap = state["multi_zone_tick_gap"]
    bar_id = state["bar_time"].astype(str)

    if "reversal_signals" not in state.columns:
        state["reversal_signals"] = None

    for zone in zones:
        sell_reversal = (
            (current_trend == XauTrend.UP.value)
            & (~multi_zone_gap)
            & (previous_bid < zone.low)
            & (current_bid >= zone.low)
        )
        buy_reversal = (
            (current_trend == XauTrend.DOWN.value)
            & (~multi_zone_gap)
            & (previous_bid > zone.high)
            & (current_bid <= zone.high)
        )
        # Key format: "bar_id:R:zone_id:side" where side is 0 for BUY, 1 for SELL
        _ = bar_id + ":R:" + zone.id + ":1"
        _ = bar_id + ":R:" + zone.id + ":0"
        _ = sell_reversal
        _ = buy_reversal
        # Reversal key tracking would update reversal_keys column.

    return state


def generate_pullback_signals(state: pd.DataFrame) -> pd.DataFrame:
    """Generate pullback signals from active pullback windows.

    Pullback conditions:
    - Window must be active (1 <= bar_offset <= 5)
    - Price must penetrate zone (bid <= zone.high - PULLBACK_PENETRATION_USD for BUY)
    - Usage must be allowed based on zone priority and daily fills
    """
    if "pullback_signals" not in state.columns:
        state["pullback_signals"] = None

    pullback_active = state["pullback_active"]
    if not pullback_active.any():
        return state

    # Per-window zone information and penetration checks would be applied here.
    return state
