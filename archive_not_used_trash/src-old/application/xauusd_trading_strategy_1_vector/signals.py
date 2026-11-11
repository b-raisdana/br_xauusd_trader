"""Breakout, reversal and pullback candidates; order execution is handled separately."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import TypedDict

import numpy as np
import pandas as pd
from br_py_log_n_profile import log_e, profile_it
from numpy.typing import NDArray

from application.xauusd_trading_strategy_1_vector.pullback_utils import create_pullback_window
from br_pre_commit import pandera_validate
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily, XauTrend
from domain.xau_usd.models import XauSignalCandidate, XauZone
from helper.importer import pt

from .config.strategy_config import StrategyConfig
from .domain.schema import (
    PerTickState,
    VectorizedTick,
    XauPullbackWindowState,
)
from .domain.state import evaluate_pullback_price


class PullbackStream(TypedDict):
    day: datetime | None
    bar: datetime | None
    windows: dict[tuple[str, XauDirection], XauPullbackWindowState]
    fills: dict[str, int]


PULLBACK_WINDOW_BARS = 5


@profile_it
def _create_reversal_candidate(
    bar_id: str,
    zone: XauZone,
    direction: XauDirection,
    tick_time: pd.Timestamp | None,
    entry_price: float,
) -> XauSignalCandidate:
    """Create a reversal signal candidate."""
    key = f"{bar_id}:R:{zone.id}:{direction.value}"
    return XauSignalCandidate(
        candidate_id=key,
        bar_id=bar_id,
        zone_id=zone.id,
        family=XauSignalFamily.REVERSAL,
        direction=direction,
        order_type=XauOrderType.MARKET,
        signal_time=tick_time.to_pydatetime() if tick_time is not None else None,
        entry_price=entry_price,
    )


@profile_it
def _process_zone_reversals(
    per_tick_state: pt.DataFrame[PerTickState],
    zone: XauZone,
    signals: NDArray[np.object_],
    seen_keys: set[str],
    bar_id: list[str],
    tick_times: pd.DatetimeIndex | None,
    current_bid: pt.Series[float],
    current_trend: pt.Series[int],
    multi_zone_gap: pt.Series[bool],
    previous_bid: NDArray[np.float64],
) -> None:
    """Process reversal signals for a single zone."""
    sell_reversal = (
        (current_trend == XauTrend.UP.value) & (~multi_zone_gap) & (previous_bid < zone.low) & (current_bid >= zone.low)
    )
    buy_reversal = (
        (current_trend == XauTrend.DOWN.value)
        & (~multi_zone_gap)
        & (previous_bid > zone.high)
        & (current_bid <= zone.high)
    )
    for mask, direction in ((sell_reversal, XauDirection.SELL), (buy_reversal, XauDirection.BUY)):
        for row in np.flatnonzero(mask.to_numpy()):
            key = f"{bar_id[row]}:R:{zone.id}:{direction.value}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            signals[row] += (
                _create_reversal_candidate(
                    bar_id=bar_id[row],
                    zone=zone,
                    direction=direction,
                    tick_time=tick_times[row] if tick_times is not None else None,
                    entry_price=float(current_bid.iloc[row]),
                ),
            )


def _find_bar_boundaries(
    ticks: pt.DataFrame[VectorizedTick],
) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.int64]]:
    """Find bar change boundaries."""

    changed = ticks["bar_time"].ne(ticks["bar_time"].shift()).to_numpy()
    starts = np.flatnonzero(changed)[1:]
    closes = starts - 1
    tick_bar_ids = changed.cumsum() - 1
    return starts, closes, tick_bar_ids


def _detect_zone_breakouts(
    ticks: pt.DataFrame[VectorizedTick],
    per_tick_state: pt.DataFrame[PerTickState],
    zones: list[XauZone],
    starts: NDArray[np.int64],
    closes: NDArray[np.int64],
) -> list[tuple[int, int, XauDirection]]:
    """Detect valid breakout events per zone and direction."""
    prices = ticks["bid"].to_numpy()
    trends = per_tick_state["trend"].to_numpy()
    breakout_buffer = StrategyConfig.current().breakout_buffer_usd
    records: list[tuple[int, int, XauDirection]] = []

    for zone_number, zone in enumerate(zones):
        for direction, trend, side in (
            (XauDirection.BUY, XauTrend.UP, "buy"),
            (XauDirection.SELL, XauTrend.DOWN, "sell"),
        ):
            engaged = per_tick_state[f"{side}_engaged:{zone.id}"].to_numpy()[closes]
            beyond = (
                prices[closes] > zone.high + breakout_buffer
                if direction == XauDirection.BUY
                else prices[closes] < zone.low - breakout_buffer
            )
            valid = engaged & (trends[closes] == trend.value) & beyond
            records.extend((int(row), zone_number, direction) for row in starts[valid])

    records.sort(key=lambda record: (record[0], record[1], record[2].value))
    return records


def _create_breakout_candidate(
    ticks: pt.DataFrame[VectorizedTick],
    row: int,
    close_row: int,
    zone: XauZone,
    direction: XauDirection,
    sequence: int,
    prices: NDArray[np.float64],
) -> XauSignalCandidate:
    """Create a breakout signal candidate."""
    breakout_id = f"BO{sequence}"
    return XauSignalCandidate(
        candidate_id=breakout_id,
        bar_id=str(ticks["bar_time"].iloc[close_row]),
        zone_id=zone.id,
        family=XauSignalFamily.BREAKOUT,
        direction=direction,
        order_type=XauOrderType.MARKET,
        signal_time=ticks["bar_time"].iloc[row].to_pydatetime(),
        entry_price=float(prices[close_row]),
    )


def _update_pullback_columns(
    per_tick_state: pt.DataFrame[PerTickState],
    zones: list[XauZone],
    opened_windows: dict[tuple[int, XauDirection], list[tuple[int, str]]],
    tick_bar_ids: NDArray[np.int64],
    size: int,
) -> pt.DataFrame[PerTickState]:
    """Update pullback state columns per zone and direction."""
    per_tick_state["pullback_active"] = False
    per_tick_state["pullback_bar_offset"] = 0

    for zone_number, zone in enumerate(zones):
        for direction in (XauDirection.BUY, XauDirection.SELL):
            openings = opened_windows.get((zone_number, direction), [])
            prefix = f"pullback:{zone.id}:{direction.value}"
            parents = np.full(size, "", dtype=object)
            offsets = np.zeros(size, dtype=np.int64)

            if openings:
                opening_rows, ids = zip(*openings, strict=True)
                rows = np.asarray(opening_rows, dtype=np.int64)
                latest = np.searchsorted(rows, np.arange(size), side="right") - 1
                offsets = np.where(latest >= 0, tick_bar_ids - tick_bar_ids[rows[latest.clip(0)]] + 1, 0)
                active = (offsets >= 1) & (offsets <= PULLBACK_WINDOW_BARS)
                parents = np.where(active, np.asarray(ids, dtype=object)[latest.clip(0)], "")
                offsets = np.where(active, offsets, 0)

            per_tick_state[f"{prefix}:parent"] = parents
            per_tick_state[f"{prefix}:offset"] = offsets
            per_tick_state["pullback_active"] |= offsets > 0
            per_tick_state["pullback_bar_offset"] = np.maximum(per_tick_state["pullback_bar_offset"], offsets)
    return per_tick_state


@profile_it
def _register_breakout(
    ticks: pt.DataFrame[VectorizedTick],
    signals: NDArray[np.object_],
    windows: NDArray[np.object_],
    counts: NDArray[np.int64],
    latest_windows: dict[tuple[int, XauDirection], int],
    opened_windows: dict[tuple[int, XauDirection], list[tuple[int, str]]],
    tick_bar_ids: NDArray[np.int64],
    prices: NDArray[np.float64],
    sequence: int,
    row: int,
    zone: XauZone,
    zone_number: int,
    direction: XauDirection,
) -> None:
    """Emit a breakout candidate and open its pullback window when outside the cooldown."""
    close_row = row - 1
    breakout_id = f"BO{sequence}"

    candidate = _create_breakout_candidate(ticks, row, close_row, zone, direction, sequence, prices)
    signals[row] += (candidate,)
    counts[row] += 1

    key = (zone_number, direction)
    previous_bar = latest_windows.get(key)

    if previous_bar is not None and tick_bar_ids[close_row] - previous_bar <= PULLBACK_WINDOW_BARS:
        return

    pullback_window_state = XauPullbackWindowState()
    create_pullback_window(pullback_window_state, breakout_id, zone, direction)
    pullback_window_state.bar_offset = 1
    windows[row] += (pullback_window_state,)
    latest_windows[key] = tick_bar_ids[close_row]
    opened_windows.setdefault(key, []).append((row, breakout_id))


@profile_it
@pandera_validate
def generate_breakout_signals(
    ticks: pt.DataFrame[VectorizedTick],
    per_tick_state: pt.DataFrame[PerTickState],
    zones: list[XauZone],
) -> pt.DataFrame[PerTickState]:
    """Emit closed-bar candidates at the next observed bar, with per-zone lineage."""
    size = len(per_tick_state)
    signals: NDArray[np.object_] = np.empty(size, dtype=object)
    windows: NDArray[np.object_] = np.empty(size, dtype=object)
    signals.fill(())
    windows.fill(())
    per_tick_state["breakout_sequence"] = 0

    if not size:
        per_tick_state["breakout_signals"] = signals
        per_tick_state["pullback_windows_opened"] = windows
        return per_tick_state

    starts, closes, tick_bar_ids = _find_bar_boundaries(ticks)
    prices = ticks["bid"].to_numpy()

    records = _detect_zone_breakouts(ticks, per_tick_state, zones, starts, closes)

    latest_windows: dict[tuple[int, XauDirection], int] = {}
    opened_windows: dict[tuple[int, XauDirection], list[tuple[int, str]]] = {}
    counts = np.zeros(size, dtype=np.int64)

    for sequence, (row, zone_number, direction) in enumerate(records, start=1):
        _register_breakout(
            ticks,
            signals,
            windows,
            counts,
            latest_windows,
            opened_windows,
            tick_bar_ids,
            prices,
            sequence,
            row,
            zones[zone_number],
            zone_number,
            direction,
        )

    _update_pullback_columns(per_tick_state, zones, opened_windows, tick_bar_ids, size)

    per_tick_state["breakout_sequence"] = counts.cumsum()
    per_tick_state["breakout_signals"] = signals
    per_tick_state["pullback_windows_opened"] = windows

    # has_breakout_sequence = per_tick_state["breakout_signals"] != ()
    # t = per_tick_state[has_breakout_sequence]

    return per_tick_state


@profile_it
@pandera_validate
def generate_reversal_signals(
    ticks: pt.DataFrame[VectorizedTick],
    per_tick_state: pt.DataFrame[PerTickState],
    zones: list[XauZone],
) -> pt.DataFrame[PerTickState]:
    """Generate reversal signals on zone touches against trend.

    SELL reversal: trend == UP and previous_bid < zone.low and current_bid >= zone.low
    BUY reversal: trend == DOWN and previous_bid > zone.high and current_bid <= zone.high
    """
    signals = np.empty(len(per_tick_state), dtype=object)
    signals.fill(())
    per_tick_state["reversal_signals"] = signals
    if not zones or per_tick_state.empty:
        return per_tick_state

    bar_changed = ticks["bar_time"].ne(ticks["bar_time"].shift())
    previous_bid = np.where(bar_changed, ticks["bid"], ticks["bid"].shift())
    current_bid = ticks["bid"]
    current_trend = per_tick_state["trend"]
    multi_zone_gap = per_tick_state["multi_zone_tick_gap"]
    bar_id = ticks["bar_time"].astype(str).tolist()

    seen_keys: set[str] = set()
    tick_times = (
        per_tick_state.index.get_level_values("precise_time") if "precise_time" in per_tick_state.index.names else None
    )

    for zone in zones:
        _process_zone_reversals(
            per_tick_state=per_tick_state,
            zone=zone,
            signals=signals,
            seen_keys=seen_keys,
            bar_id=bar_id,
            tick_times=tick_times,
            current_bid=current_bid,
            current_trend=current_trend,
            multi_zone_gap=multi_zone_gap,
            previous_bid=previous_bid,
        )

    per_tick_state["reversal_signals"] = signals

    # t = per_tick_state[per_tick_state["reversal_signals"] != ()]

    return per_tick_state


def _pullback_candidate(
    window: XauPullbackWindowState,
    bid: float,
    bar_id: datetime,
    tick_time: datetime,
    daily_fills: int,
) -> XauSignalCandidate | None:
    valid, candidate_id, entry_price = evaluate_pullback_price(window, daily_fills, bid)
    if not valid:
        return None
    return XauSignalCandidate(
        candidate_id=candidate_id,
        parent_breakout_id=window.parent_breakout_id,
        bar_id=str(bar_id),
        zone_id=window.zone.id,
        family=XauSignalFamily.PULLBACK,
        direction=window.direction,
        order_type=XauOrderType.PENDING_STOP,
        signal_time=tick_time,
        entry_price=entry_price,
    )


@profile_it
@pandera_validate
def generate_pullback_signals(
    ticks: pt.DataFrame[VectorizedTick], per_tick_state: pt.DataFrame[PerTickState]
) -> pt.DataFrame[PerTickState]:
    """Replay windows and optional execution feedback; absent feedback means no fills/acceptances.

    Emit retry candidates at the broken edge after 0.20 penetration. Only execution
    feedback consumes daily usage, marks pending orders, or resets penetration on fills.
    """
    size = len(per_tick_state)
    signals = np.empty(size, dtype=object)
    signals.fill(())
    latched = np.zeros(size, dtype=bool)
    sequence = np.zeros(size, dtype=np.int64)
    streams: dict[tuple[str, str], PullbackStream] = {}
    feedback_rows = per_tick_state.get("pullback_feedback", [()] * size)
    brokers = per_tick_state.index.get_level_values("broker")
    symbols = per_tick_state.index.get_level_values("symbol")
    times = per_tick_state.index.get_level_values("precise_time")
    rows = zip(
        brokers,
        symbols,
        times,
        ticks["broker_day"],
        ticks["bar_time"],
        ticks["bid"],
        per_tick_state["pullback_windows_opened"],
        feedback_rows,
        strict=True,
    )
    for row, (broker, symbol, time, day, bar, bid, openings, feedback) in enumerate(rows):
        stream = streams.setdefault((broker, symbol), {"day": None, "bar": None, "windows": {}, "fills": {}})
        if day != stream["day"]:
            stream.update({"day": day, "bar": None, "windows": {}, "fills": {}})
        windows, fills = stream["windows"], stream["fills"]
        if bar != stream["bar"]:
            for window in windows.values():
                window.bar_offset += 1
            windows = {key: window for key, window in windows.items() if window.bar_offset <= PULLBACK_WINDOW_BARS}
            stream.update({"bar": bar, "windows": windows})
        for opening in openings:
            key = (opening.zone.id, opening.direction)
            if opening.active and 1 <= opening.bar_offset <= PULLBACK_WINDOW_BARS and key not in windows:
                windows[key] = deepcopy(opening)
        for update in feedback:
            if update.daily_fills < 0 or update.daily_fills < fills.get(update.zone_id, 0):
                log_e("Pullback daily fill count must be nonnegative and nondecreasing within a broker day")
                raise ValueError("Invalid pullback daily fill count")
            fills[update.zone_id] = update.daily_fills
            feedback_window = windows.get((update.zone_id, update.direction))
            if feedback_window is not None:
                feedback_window.pending_active = update.pending_active
                if update.filled:
                    feedback_window.penetration_latched = False
        for window in windows.values():
            candidate = _pullback_candidate(window, bid, bar, time, fills.get(window.zone.id, 0))
            if candidate is not None:
                signals[row] += (candidate,)
            latched[row] |= window.penetration_latched
            sequence[row] += window.sequence
    per_tick_state["pullback_signals"] = signals
    per_tick_state["pullback_penetration_latched"] = latched
    per_tick_state["pullback_sequence"] = sequence

    # todo: revise too much pullback_signals 414489/902975
    # t = per_tick_state[per_tick_state["pullback_signals"] != ()]

    return per_tick_state
