from __future__ import annotations

from domain.xau_usd.constants import PULLBACK_PENETRATION_USD
from domain.xau_usd.enums import XauDirection, XauTpFailureAction, XauTrend
from domain.xau_usd.models import (
    XauDailyZoneSignalState,
    XauPreZoneTriggerState,
    XauPullbackTpState,
    XauPullbackWindowState,
    XauTrendReferenceState,
    XauZone,
)
from domain.xau_usd.protection import pullback_tp_failure_action
from domain.xau_usd.zone import (
    breakout_valid,
    count_directional_crosses,
    pre_zone_crossed,
    pullback_usage_allowed,
    pullback_window_active,
    update_trend,
)


def pre_zone_cross_once(
    state: XauPreZoneTriggerState,
    position_id: str,
    direction: XauDirection,
    target_zone: XauZone,
    previous_price: float,
    current_price: float,
) -> bool:
    if not position_id or not target_zone.id:
        return False

    if state.position_id != position_id or state.target_zone_id != target_zone.id:
        state.position_id = position_id
        state.target_zone_id = target_zone.id
        state.triggered = False

    if state.triggered or not pre_zone_crossed(direction, target_zone, previous_price, current_price):
        return False

    state.triggered = True
    return True


def initialize_pullback_tp(
    state: XauPullbackTpState,
    position_id: str,
    direction: XauDirection,
    initial_target: XauZone,
) -> bool:
    if not position_id or not initial_target.id:
        return False

    target = initial_target.low if direction == XauDirection.BUY else initial_target.high
    state.position_id = position_id
    state.direction = direction
    state.initial_target_zone_id = initial_target.id
    state.initial_tp = target
    state.current_target_zone_id = initial_target.id
    state.current_tp = target
    state.extended = False
    return True


def propose_pullback_tp_extension(
    state: XauPullbackTpState,
    approached_zone: XauZone,
    next_zone: XauZone,
    has_next_zone: bool,
    strict_valid: bool,
) -> tuple[bool, float, str]:
    if state.extended or not strict_valid or not has_next_zone or approached_zone.id != state.initial_target_zone_id:
        return False, 0.0, ""

    requested_tp = next_zone.low if state.direction == XauDirection.BUY else next_zone.high
    return True, requested_tp, next_zone.id


def record_pullback_tp_extension(
    state: XauPullbackTpState,
    requested_tp: float,
    target_zone_id: str,
    broker_accepted: bool,
) -> bool:
    if requested_tp <= 0.0 or not target_zone_id:
        return False

    if broker_accepted:
        state.current_tp = requested_tp
        state.current_target_zone_id = target_zone_id
        state.extended = True
    return True


def evaluate_pullback_tp_failure(
    state: XauPullbackTpState,
    strict_valid: bool,
    current_bid: float,
    current_ask: float,
) -> tuple[XauTpFailureAction, float]:
    action = pullback_tp_failure_action(
        state.direction,
        state.extended,
        strict_valid,
        state.initial_tp,
        current_bid,
        current_ask,
    )
    return action, state.initial_tp if action == XauTpFailureAction.RESTORE else 0.0


def record_pullback_tp_restore(state: XauPullbackTpState, broker_accepted: bool) -> None:
    if not broker_accepted:
        return

    state.current_tp = state.initial_tp
    state.current_target_zone_id = state.initial_target_zone_id
    state.extended = False


def create_pullback_window(
    window: XauPullbackWindowState,
    parent_breakout_id: str,
    zone: XauZone,
    direction: XauDirection,
) -> bool:
    if not parent_breakout_id or not zone.id or zone.low > zone.high:
        return False

    window.parent_breakout_id = parent_breakout_id
    window.zone = zone
    window.direction = direction
    window.bar_offset = 0
    window.active = True
    window.penetration_latched = False
    window.pending_active = False
    window.sequence = 0
    return True


def begin_pullback_bar(window: XauPullbackWindowState) -> tuple[bool, bool]:
    pending_must_cancel = False
    if not window.active:
        return False, pending_must_cancel

    window.bar_offset += 1
    if not pullback_window_active(window.bar_offset):
        pending_must_cancel = window.pending_active
        window.pending_active = False
        window.active = False
    return True, pending_must_cancel


def evaluate_pullback_price(
    window: XauPullbackWindowState,
    daily_fills: int,
    bid: float,
) -> tuple[bool, str, float]:
    if (
        not window.active
        or not pullback_window_active(window.bar_offset)
        or window.pending_active
        or not pullback_usage_allowed(window.zone.priority, daily_fills)
    ):
        return False, "", 0.0

    if not window.penetration_latched:
        window.penetration_latched = (
            bid <= window.zone.high - PULLBACK_PENETRATION_USD
            if window.direction == XauDirection.BUY
            else bid >= window.zone.low + PULLBACK_PENETRATION_USD
        )

    if not window.penetration_latched:
        return False, "", 0.0

    window.sequence += 1
    candidate_id = f"{window.parent_breakout_id}:PB{window.sequence}"
    entry_price = window.zone.high if window.direction == XauDirection.BUY else window.zone.low
    return True, candidate_id, entry_price


def record_pullback_attempt(
    window: XauPullbackWindowState,
    attempted_bars: list[str],
    bar_id: str,
    broker_accepted: bool,
) -> bool:
    if not window.active or window.pending_active or not record_entry_attempt(attempted_bars, bar_id):
        return False

    if broker_accepted:
        window.pending_active = True
    return True


def record_pullback_fill(window: XauPullbackWindowState, zone_state: XauDailyZoneSignalState) -> bool:
    if not window.active or not window.pending_active or window.zone.id != zone_state.zone.id:
        return False

    zone_state.pullback_fills += 1
    window.pending_active = False
    window.penetration_latched = False
    return True


def record_pullback_pending_removed(window: XauPullbackWindowState) -> bool:
    if not window.active or not window.pending_active:
        return False

    window.pending_active = False
    return True


def initialize_daily_zone_states(zones: list[XauZone]) -> list[XauDailyZoneSignalState] | None:
    states: list[XauDailyZoneSignalState] = []
    for zone in zones:
        if not zone.id or zone.low > zone.high:
            return None
        states.append(XauDailyZoneSignalState(zone=zone))
    return states


def find_daily_zone_state(states: list[XauDailyZoneSignalState], zone_id: str) -> int:
    for index, state in enumerate(states):
        if state.zone.id == zone_id:
            return index
    return -1


def begin_signal_bar(states: list[XauDailyZoneSignalState], open_bid: float) -> None:
    for state in states:
        inside = state.zone.low <= open_bid <= state.zone.high
        state.buy_engaged = inside
        state.sell_engaged = inside


def update_zone_engagement(
    states: list[XauDailyZoneSignalState],
    previous_bid: float,
    current_bid: float,
) -> tuple[bool, bool]:
    zones = [state.zone for state in states]
    multi_zone_tick_gap = count_directional_crosses(zones, previous_bid, current_bid) > 1

    for state in states:
        if multi_zone_tick_gap:
            inside = state.zone.low <= current_bid <= state.zone.high
            if inside:
                state.buy_engaged = True
                state.sell_engaged = True
            continue

        if not state.buy_engaged and previous_bid < state.zone.low <= current_bid:
            state.buy_engaged = True
        if not state.sell_engaged and previous_bid > state.zone.high >= current_bid:
            state.sell_engaged = True

    return True, multi_zone_tick_gap


def next_breakout_id(daily_sequence: int) -> tuple[int, str]:
    daily_sequence += 1
    return daily_sequence, f"BO{daily_sequence}"


def consume_reversal_usage(state: XauDailyZoneSignalState) -> bool:
    limit = 2 if state.zone.priority == 1 else 1
    if state.reversal_usage >= limit:
        return False
    state.reversal_usage += 1
    return True


def record_entry_attempt(attempted_bars: list[str], bar_id: str) -> bool:
    if not bar_id or bar_id in attempted_bars:
        return False
    attempted_bars.append(bar_id)
    return True


def begin_trend_day() -> XauTrendReferenceState:
    return XauTrendReferenceState()


def record_trend_candle(state: XauTrendReferenceState, high: float, low: float) -> bool:
    if high < low:
        return False

    if state.count < 3:
        state.highs[state.count] = high
        state.lows[state.count] = low
        state.count += 1
        return True

    state.highs[0], state.highs[1], state.highs[2] = state.highs[1], state.highs[2], high
    state.lows[0], state.lows[1], state.lows[2] = state.lows[1], state.lows[2], low
    return True


def trend_references(state: XauTrendReferenceState) -> tuple[bool, float, float]:
    if state.count <= 0:
        return False, 0.0, 0.0

    reference_high = max(state.highs[: state.count])
    reference_low = min(state.lows[: state.count])
    return True, reference_high, reference_low


def process_trend_tick(state: XauTrendReferenceState, bid: float) -> XauTrend:
    has_references, reference_high, reference_low = trend_references(state)
    if has_references:
        state.trend = update_trend(state.trend, state.count, reference_high, reference_low, bid)
    return state.trend


def close_bar_breakout_before_roll(
    state: XauTrendReferenceState,
    zone: XauZone,
    direction: XauDirection,
    close_price: float,
    engaged: bool,
    candle_high: float,
    candle_low: float,
) -> tuple[bool, bool]:
    if candle_high < max(close_price, candle_low) or candle_low > close_price:
        return False, False

    breakout = breakout_valid(zone, direction, state.trend, close_price, engaged)
    return record_trend_candle(state, candle_high, candle_low), breakout
