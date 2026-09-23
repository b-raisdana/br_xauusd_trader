"""Breakout candidates and window ownership; reversal/PB execution remains pending."""

from __future__ import annotations

from typing import List

import numpy as np
from br_py_log_n_profile import NOT_TESTED, log_w

from domain.schemas.xauusd_vector_strategy import PerTickBaseState, ReversalInput, ReversalResult
from domain.xau_usd.constants import BREAKOUT_BUFFER_USD
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily, XauTrend
from domain.xau_usd.models import XauPullbackWindowState, XauSignalCandidate, XauZone
from domain.xau_usd.state import create_pullback_window
from helper.importer import pt
from helper.pandera import pandera_validate


@pandera_validate(allow_pandas_dataframe=True)
def generate_breakout_signals(
    per_tick_state: pt.DataFrame[PerTickBaseState],
    zones: List[XauZone],
) -> pt.DataFrame[PerTickBaseState]:
    """Emit closed-bar candidates at the next observed bar, with per-zone lineage."""
    log_w(NOT_TESTED)
    size = len(per_tick_state)
    signals = np.empty(size, dtype=object)
    windows = np.empty(size, dtype=object)
    signals.fill(())
    windows.fill(())
    per_tick_state["breakout_sequence"] = 0
    if not size:
        per_tick_state["breakout_signals"] = signals
        per_tick_state["pullback_windows_opened"] = windows
        return per_tick_state

    changed = per_tick_state["bar_time"].ne(per_tick_state["bar_time"].shift()).to_numpy()
    starts = np.flatnonzero(changed)[1:]
    closes = starts - 1
    tick_bar_ids = changed.cumsum() - 1
    prices = per_tick_state["bid"].to_numpy()
    trends = per_tick_state["trend"].to_numpy()
    records = []
    for zone_number, zone in enumerate(zones):
        for direction, trend, side in (
            (XauDirection.BUY, XauTrend.UP, "buy"),
            (XauDirection.SELL, XauTrend.DOWN, "sell"),
        ):
            engaged = per_tick_state[f"{side}_engaged:{zone.id}"].to_numpy()[closes]
            beyond = (
                prices[closes] > zone.high + BREAKOUT_BUFFER_USD
                if direction == XauDirection.BUY
                else prices[closes] < zone.low - BREAKOUT_BUFFER_USD
            )
            valid = engaged & (trends[closes] == trend.value) & beyond
            records.extend((int(row), zone_number, direction) for row in starts[valid])

    records.sort(key=lambda record: (record[0], record[1], record[2].value))
    latest_windows = {}
    opened_windows = {}
    counts = np.zeros(size, dtype=np.int64)
    # Only emitted events need objects and sequential window ownership; tick/bar
    # calculations above remain batched. An active parent cannot be overwritten.
    for sequence, (row, zone_number, direction) in enumerate(records, start=1):
        zone = zones[zone_number]
        close_row = row - 1
        breakout_id = f"BO{sequence}"
        candidate = XauSignalCandidate(
            candidate_id=breakout_id,
            bar_id=str(per_tick_state["bar_time"].iloc[close_row]),
            zone_id=zone.id,
            family=XauSignalFamily.BREAKOUT,
            direction=direction,
            order_type=XauOrderType.MARKET,
            signal_time=per_tick_state["bar_time"].iloc[row].to_pydatetime(),
            entry_price=float(prices[close_row]),
        )
        signals[row] += (candidate,)
        counts[row] += 1
        key = (zone_number, direction)
        previous_bar = latest_windows.get(key)
        # At close, offset five is still active; expiration occurs at next open.
        if previous_bar is not None and tick_bar_ids[close_row] - previous_bar <= 5:
            continue
        pullback_window_state = XauPullbackWindowState()
        create_pullback_window(pullback_window_state, breakout_id, zone, direction)
        pullback_window_state.bar_offset = 1
        windows[row] += (pullback_window_state,)
        latest_windows[key] = tick_bar_ids[close_row]
        opened_windows.setdefault(key, []).append((row, breakout_id))

    per_tick_state["pullback_active"] = False
    per_tick_state["pullback_bar_offset"] = 0
    for zone_number, zone in enumerate(zones):
        for direction in (XauDirection.BUY, XauDirection.SELL):
            openings = opened_windows.get((zone_number, direction), [])
            prefix = f"pullback:{zone.id}:{direction.value}"
            parents = np.full(size, "", dtype=object)
            offsets = np.zeros(size, dtype=np.int64)
            if openings:
                rows, ids = zip(*openings, strict=True)
                rows = np.asarray(rows)
                latest = np.searchsorted(rows, np.arange(size), side="right") - 1
                offsets = np.where(latest >= 0, tick_bar_ids - tick_bar_ids[rows[latest.clip(0)]] + 1, 0)
                active = (offsets >= 1) & (offsets <= 5)
                parents = np.where(active, np.asarray(ids, dtype=object)[latest.clip(0)], "")
                offsets = np.where(active, offsets, 0)
            per_tick_state[f"{prefix}:parent"] = parents
            per_tick_state[f"{prefix}:offset"] = offsets
            per_tick_state["pullback_active"] |= offsets > 0
            per_tick_state["pullback_bar_offset"] = np.maximum(per_tick_state["pullback_bar_offset"], offsets)

    per_tick_state["breakout_sequence"] = counts.cumsum()
    per_tick_state["breakout_signals"] = signals
    per_tick_state["pullback_windows_opened"] = windows
    return per_tick_state


@pandera_validate(allow_pandas_dataframe=True)
def generate_reversal_signals(
    per_tick_state: pt.DataFrame[ReversalInput],
    zones: List[XauZone],
) -> pt.DataFrame[ReversalResult]:
    """Generate reversal signals on zone touches against trend.

    SELL reversal: trend == UP and previous_bid < zone.low and current_bid >= zone.low
    BUY reversal: trend == DOWN and previous_bid > zone.high and current_bid <= zone.high
    """
    log_w(NOT_TESTED)
    if not zones:
        return per_tick_state

    bar_changed = per_tick_state["bar_time"].ne(per_tick_state["bar_time"].shift())
    previous_bid = np.where(bar_changed, per_tick_state["bid"], per_tick_state["bid"].shift())
    current_bid = per_tick_state["bid"]
    current_trend = per_tick_state["trend"]
    multi_zone_gap = per_tick_state["multi_zone_tick_gap"]
    bar_id = per_tick_state["bar_time"].astype(str)

    if "reversal_signals" not in per_tick_state.columns:
        per_tick_state["reversal_signals"] = None

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

    return per_tick_state


@pandera_validate(allow_pandas_dataframe=True)
def generate_pullback_signals(per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PerTickBaseState]:
    """Generate pullback signals from active pullback windows.

    Pullback conditions:
    - Window must be active (1 <= bar_offset <= 5)
    - Price must penetrate zone (bid <= zone.high - PULLBACK_PENETRATION_USD for BUY)
    - Usage must be allowed based on zone priority and daily fills
    """
    log_w(NOT_TESTED)
    if "pullback_signals" not in per_tick_state.columns:
        per_tick_state["pullback_signals"] = None

    pullback_active = per_tick_state["pullback_active"]
    if not pullback_active.any():
        return per_tick_state

    # Per-window zone information and penetration checks would be applied here.
    return per_tick_state
