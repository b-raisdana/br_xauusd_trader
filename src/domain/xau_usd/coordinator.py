from __future__ import annotations

from datetime import datetime

from domain.xau_usd.constants import PARITY_PRICE_TOLERANCE
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily
from domain.xau_usd.models import (
    XauMarketCoordinator,
    XauPullbackWindowState,
    XauSignalCandidate,
    XauZone,
)
from domain.xau_usd.state import (
    begin_pullback_bar,
    begin_signal_bar,
    begin_trend_day,
    create_pullback_window,
    evaluate_pullback_price,
    find_daily_zone_state,
    initialize_daily_zone_states,
    next_breakout_id,
    process_trend_tick,
    record_trend_candle,
    update_zone_engagement,
)
from domain.xau_usd.zone import breakout_valid, reversal_directional_touch


def append_signal_candidate(
    candidates: list[XauSignalCandidate],
    candidate_id: str,
    parent_breakout_id: str,
    bar_id: str,
    zone_id: str,
    family: XauSignalFamily,
    direction: XauDirection,
    order_type: XauOrderType,
    signal_time: datetime,
    entry_price: float,
) -> bool:
    if not candidate_id or not bar_id or not zone_id or signal_time is None or entry_price <= 0.0:
        return False

    candidates.append(
        XauSignalCandidate(
            candidate_id=candidate_id,
            parent_breakout_id=parent_breakout_id,
            bar_id=bar_id,
            zone_id=zone_id,
            family=family,
            direction=direction,
            order_type=order_type,
            signal_time=signal_time,
            entry_price=entry_price,
        )
    )
    return True


def record_unique_text(values: list[str], value: str) -> bool:
    if not value or value in values:
        return False
    values.append(value)
    return True


def find_coordinator_pullback(
    state: XauMarketCoordinator,
    zone_id: str,
    direction: XauDirection,
) -> int:
    for index, window in enumerate(state.pullbacks):
        if window.zone.id == zone_id and window.direction == direction:
            return index
    return -1


def begin_coordinator_day(state: XauMarketCoordinator, broker_day: str, zones: list[XauZone]) -> bool:
    if not broker_day or not zones:
        return False

    daily_states = initialize_daily_zone_states(zones)
    if daily_states is None:
        return False

    state.broker_day = broker_day
    state.bar_id = ""
    state.day_active = True
    state.bar_active = False
    state.bar_open = 0.0
    state.last_bid = 0.0
    state.last_ask = 0.0
    state.breakout_sequence = 0
    state.zones = daily_states
    state.pullbacks.clear()
    state.reversal_keys.clear()
    state.attempted_bars.clear()
    state.trend = begin_trend_day()
    return True


def begin_coordinator_bar(
    state: XauMarketCoordinator,
    bar_id: str,
    open_bid: float,
    open_ask: float,
) -> tuple[bool, int]:
    pending_cancellations = 0
    if not state.day_active or state.bar_active or not bar_id or open_bid <= 0.0 or open_ask < open_bid:
        return False, pending_cancellations

    for window in state.pullbacks:
        began, pending_must_cancel = begin_pullback_bar(window)
        if not began:
            return False, pending_cancellations
        if pending_must_cancel:
            pending_cancellations += 1

    begin_signal_bar(state.zones, open_bid)
    state.bar_id = bar_id
    state.bar_active = True
    state.bar_open = open_bid
    state.last_bid = open_bid
    state.last_ask = open_ask
    return True, pending_cancellations


def process_coordinator_tick(
    state: XauMarketCoordinator,
    tick_time: datetime,
    bid: float,
    ask: float,
) -> tuple[bool, list[XauSignalCandidate]]:
    candidates: list[XauSignalCandidate] = []
    if not state.bar_active or tick_time is None or bid <= 0.0 or ask < bid:
        return False, candidates

    previous_bid = state.last_bid
    process_trend_tick(state.trend, bid)
    engagement_ok, multi_zone_tick_gap = update_zone_engagement(state.zones, previous_bid, bid)
    if not engagement_ok:
        return False, candidates

    for zone_state in state.zones:
        for direction in (XauDirection.BUY, XauDirection.SELL):
            if not reversal_directional_touch(
                zone_state.zone,
                direction,
                state.trend.trend,
                previous_bid,
                bid,
                multi_zone_tick_gap,
            ):
                continue

            side = 0 if direction == XauDirection.BUY else 1
            key = f"{state.bar_id}:R:{zone_state.zone.id}:{side}"
            if not record_unique_text(state.reversal_keys, key):
                continue
            if not append_signal_candidate(
                candidates,
                key,
                "",
                state.bar_id,
                zone_state.zone.id,
                XauSignalFamily.REVERSAL,
                direction,
                XauOrderType.MARKET,
                tick_time,
                bid,
            ):
                return False, candidates

    for window in state.pullbacks:
        zone_index = find_daily_zone_state(state.zones, window.zone.id)
        if zone_index < 0:
            return False, candidates

        evaluated, candidate_id, entry_price = evaluate_pullback_price(
            window,
            state.zones[zone_index].pullback_fills,
            bid,
        )
        if evaluated and not append_signal_candidate(
            candidates,
            candidate_id,
            window.parent_breakout_id,
            state.bar_id,
            window.zone.id,
            XauSignalFamily.PULLBACK,
            window.direction,
            XauOrderType.PENDING_STOP,
            tick_time,
            entry_price,
        ):
            return False, candidates

    state.last_bid = bid
    state.last_ask = ask
    return True, candidates


def close_coordinator_bar(
    state: XauMarketCoordinator,
    close_time: datetime,
    high: float,
    low: float,
    close_bid: float,
) -> tuple[bool, list[XauSignalCandidate]]:
    breakouts: list[XauSignalCandidate] = []
    if (
        not state.bar_active
        or close_time is None
        or high < max(close_bid, low)
        or low > close_bid
        or abs(close_bid - state.last_bid) > PARITY_PRICE_TOLERANCE
    ):
        return False, breakouts

    for zone_state in state.zones:
        for direction in (XauDirection.BUY, XauDirection.SELL):
            engaged = zone_state.buy_engaged if direction == XauDirection.BUY else zone_state.sell_engaged
            if not breakout_valid(zone_state.zone, direction, state.trend.trend, close_bid, engaged):
                continue

            state.breakout_sequence, breakout_id = next_breakout_id(state.breakout_sequence)
            if not append_signal_candidate(
                breakouts,
                breakout_id,
                "",
                state.bar_id,
                zone_state.zone.id,
                XauSignalFamily.BREAKOUT,
                direction,
                XauOrderType.MARKET,
                close_time,
                close_bid,
            ):
                return False, breakouts

            window_index = find_coordinator_pullback(state, zone_state.zone.id, direction)
            if window_index >= 0 and state.pullbacks[window_index].active:
                continue

            if window_index < 0:
                window_index = len(state.pullbacks)
                state.pullbacks.append(XauPullbackWindowState())

            window = state.pullbacks[window_index]
            if window is None or not create_pullback_window(window, breakout_id, zone_state.zone, direction):
                return False, breakouts

    if not record_trend_candle(state.trend, high, low):
        return False, breakouts

    state.bar_active = False
    state.bar_id = ""
    return True, breakouts
