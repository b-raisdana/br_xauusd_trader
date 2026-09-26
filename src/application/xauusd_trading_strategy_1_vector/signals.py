"""Breakout, reversal and pullback candidates; order execution is handled separately."""

from __future__ import annotations

from copy import deepcopy
from typing import List, Tuple

import numpy as np
from br_py_log_n_profile import log_e, profile_it

from application.xauusd_trading_strategy_1.domain.state import evaluate_pullback_price
from application.xauusd_trading_strategy_1_vector.config.strategy_config import StrategyConfig
from application.xauusd_trading_strategy_1_vector.domain.schema import (
    PerTickBaseState,
    PullbackResult,
    PullbackWindowsTuple,
    ReversalInput,
    ReversalResult,
    SignalCandidatesTuple,
    XauPullbackWindowState,
)
from application.xauusd_trading_strategy_1_vector.pullback_utils import create_pullback_window
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily, XauTrend
from domain.xau_usd.models import XauSignalCandidate, XauZone
from helper.importer import pt
from helper.pandera import pandera_validate

PULLBACK_WINDOW_BARS = 5


@profile_it
def _create_reversal_candidate(
    bar_id: str,
    zone: XauZone,
    direction: XauDirection,
    tick_time,
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
    per_tick_state: pt.DataFrame[ReversalInput],
    zone: XauZone,
    signals: np.ndarray,
    seen_keys: set,
    bar_id: np.ndarray,
    tick_times,
    current_bid: np.ndarray,
    current_trend: np.ndarray,
    multi_zone_gap: np.ndarray,
    previous_bid: np.ndarray,
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


def _find_bar_boundaries(per_tick_state: pt.DataFrame[PerTickBaseState]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Find bar change boundaries."""

    changed = per_tick_state["bar_time"].ne(per_tick_state["bar_time"].shift()).to_numpy()
    starts = np.flatnonzero(changed)[1:]
    closes = starts - 1
    tick_bar_ids = changed.cumsum() - 1
    return starts, closes, tick_bar_ids


def _detect_zone_breakouts(
    per_tick_state: pt.DataFrame[PerTickBaseState],
    zones: List[XauZone],
    starts: np.ndarray,
    closes: np.ndarray,
) -> List[Tuple[int, int, XauDirection]]:
    """Detect valid breakout events per zone and direction."""
    prices = per_tick_state["bid"].to_numpy()
    trends = per_tick_state["trend"].to_numpy()
    breakout_buffer = StrategyConfig.current().breakout_buffer_usd
    records = []

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
    per_tick_state: pt.DataFrame[PerTickBaseState],
    row: int,
    close_row: int,
    zone: XauZone,
    direction: XauDirection,
    sequence: int,
    prices: np.ndarray,
) -> XauSignalCandidate:
    """Create a breakout signal candidate."""
    breakout_id = f"BO{sequence}"
    return XauSignalCandidate(
        candidate_id=breakout_id,
        bar_id=str(per_tick_state["bar_time"].iloc[close_row]),
        zone_id=zone.id,
        family=XauSignalFamily.BREAKOUT,
        direction=direction,
        order_type=XauOrderType.MARKET,
        signal_time=per_tick_state["bar_time"].iloc[row].to_pydatetime(),
        entry_price=float(prices[close_row]),
    )


def _update_pullback_columns(
    per_tick_state: pt.DataFrame[PerTickBaseState],
    zones: List[XauZone],
    opened_windows: dict,
    tick_bar_ids: np.ndarray,
    size: int,
) -> None:
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
                rows, ids = zip(*openings, strict=True)
                rows = np.asarray(rows)
                latest = np.searchsorted(rows, np.arange(size), side="right") - 1
                offsets = np.where(latest >= 0, tick_bar_ids - tick_bar_ids[rows[latest.clip(0)]] + 1, 0)
                active = (offsets >= 1) & (offsets <= PULLBACK_WINDOW_BARS)
                parents = np.where(active, np.asarray(ids, dtype=object)[latest.clip(0)], "")
                offsets = np.where(active, offsets, 0)

            per_tick_state[f"{prefix}:parent"] = parents
            per_tick_state[f"{prefix}:offset"] = offsets
            per_tick_state["pullback_active"] |= offsets > 0
            per_tick_state["pullback_bar_offset"] = np.maximum(per_tick_state["pullback_bar_offset"], offsets)


@profile_it
def _register_breakout(
    per_tick_state: pt.DataFrame[PerTickBaseState],
    signals: np.ndarray[SignalCandidatesTuple],
    windows: np.ndarray[PullbackWindowsTuple],
    counts: np.ndarray,
    latest_windows: dict,
    opened_windows: dict,
    tick_bar_ids: np.ndarray,
    prices: np.ndarray,
    sequence: int,
    row: int,
    zone: XauZone,
    zone_number: int,
    direction: XauDirection,
) -> None:
    """Emit a breakout candidate and open its pullback window when outside the cooldown."""
    close_row = row - 1
    breakout_id = f"BO{sequence}"

    candidate = _create_breakout_candidate(per_tick_state, row, close_row, zone, direction, sequence, prices)
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
@pandera_validate(allow_pandas_dataframe=True)
def generate_breakout_signals(
    per_tick_state: pt.DataFrame[PerTickBaseState],
    zones: List[XauZone],
) -> pt.DataFrame[PerTickBaseState]:
    """Emit closed-bar candidates at the next observed bar, with per-zone lineage."""
    size = len(per_tick_state)
    signals: np.ndarray[SignalCandidatesTuple] = np.empty(size, dtype=object)
    windows: np.ndarray[PullbackWindowsTuple] = np.empty(size, dtype=object)
    signals.fill(())
    windows.fill(())
    per_tick_state["breakout_sequence"] = 0

    if not size:
        per_tick_state["breakout_signals"] = signals
        per_tick_state["pullback_windows_opened"] = windows
        return per_tick_state

    starts, closes, tick_bar_ids = _find_bar_boundaries(per_tick_state)
    prices = per_tick_state["bid"].to_numpy()

    records = _detect_zone_breakouts(per_tick_state, zones, starts, closes)

    latest_windows = {}
    opened_windows = {}
    counts = np.zeros(size, dtype=np.int64)

    for sequence, (row, zone_number, direction) in enumerate(records, start=1):
        _register_breakout(
            per_tick_state,
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
    per_tick_state: pt.DataFrame[ReversalInput],
    zones: List[XauZone],
) -> pt.DataFrame[ReversalResult]:
    """Generate reversal signals on zone touches against trend.

    SELL reversal: trend == UP and previous_bid < zone.low and current_bid >= zone.low
    BUY reversal: trend == DOWN and previous_bid > zone.high and current_bid <= zone.high
    """
    signals = np.empty(len(per_tick_state), dtype=object)
    signals.fill(())
    per_tick_state["reversal_signals"] = signals
    if not zones or per_tick_state.empty:
        return per_tick_state

    bar_changed = per_tick_state["bar_time"].ne(per_tick_state["bar_time"].shift())
    previous_bid = np.where(bar_changed, per_tick_state["bid"], per_tick_state["bid"].shift())
    current_bid = per_tick_state["bid"]
    current_trend = per_tick_state["trend"]
    multi_zone_gap = per_tick_state["multi_zone_tick_gap"]
    bar_id = per_tick_state["bar_time"].astype(str).to_numpy()

    seen_keys = set()
    tick_times = per_tick_state.index.get_level_values("datetime") if "datetime" in per_tick_state.index.names else None

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


def _pullback_candidate(window, bid, bar_id, tick_time, daily_fills):
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
        signal_time=tick_time.to_pydatetime(),
        entry_price=entry_price,
    )


@profile_it
@pandera_validate
def generate_pullback_signals(per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PullbackResult]:
    """Replay windows and optional execution feedback; absent feedback means no fills/acceptances.

    Emit retry candidates at the broken edge after 0.20 penetration. Only execution
    feedback consumes daily usage, marks pending orders, or resets penetration on fills.
    """
    size = len(per_tick_state)
    signals = np.empty(size, dtype=object)
    signals.fill(())
    latched = np.zeros(size, dtype=bool)
    sequence = np.zeros(size, dtype=np.int64)
    streams = {}
    feedback_rows = per_tick_state.get("pullback_feedback", [()] * size)
    brokers = per_tick_state.index.get_level_values("broker")
    symbols = per_tick_state.index.get_level_values("symbol")
    times = per_tick_state.index.get_level_values("datetime")
    rows = zip(
        brokers,
        symbols,
        times,
        per_tick_state["broker_day"],
        per_tick_state["bar_time"],
        per_tick_state["bid"],
        per_tick_state["pullback_windows_opened"],
        feedback_rows,
        strict=True,
    )
    for row, (broker, symbol, time, day, bar, bid, openings, feedback) in enumerate(rows):
        stream = streams.setdefault((broker, symbol), {"day": None, "bar": None, "windows": {}, "fills": {}})
        if day != stream["day"]:
            stream.update(day=day, bar=None, windows={}, fills={})
        windows, fills = stream["windows"], stream["fills"]
        if bar != stream["bar"]:
            for window in windows.values():
                window.bar_offset += 1
            windows = {key: window for key, window in windows.items() if window.bar_offset <= PULLBACK_WINDOW_BARS}
            stream.update(bar=bar, windows=windows)
        for opening in openings:
            key = (opening.zone.id, opening.direction)
            if opening.active and 1 <= opening.bar_offset <= PULLBACK_WINDOW_BARS and key not in windows:
                windows[key] = deepcopy(opening)
        for update in feedback:
            if update.daily_fills < 0 or update.daily_fills < fills.get(update.zone_id, 0):
                log_e("Pullback daily fill count must be nonnegative and nondecreasing within a broker day")
                raise ValueError("Invalid pullback daily fill count")
            fills[update.zone_id] = update.daily_fills
            window = windows.get((update.zone_id, update.direction))
            if window is not None:
                window.pending_active = update.pending_active
                if update.filled:
                    window.penetration_latched = False
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
