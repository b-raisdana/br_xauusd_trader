from __future__ import annotations

from .constants import BREAKOUT_BUFFER_USD, PRE_ZONE_TRIGGER_DISTANCE_USD, PULLBACK_PENETRATION_USD
from .enums import XauDirection, XauTrend
from .models import XauZone


def build_merged_zones(
    raw_zones: list[XauZone],
    broker_day: str,
) -> list[XauZone]:
    sorted_zones = []

    for zone in raw_zones:
        low = zone.low
        high = zone.high

        if low > high:
            low, high = high, low

        sorted_zones.append(
            XauZone(
                id=zone.id,
                low=low,
                high=high,
                priority=zone.priority,
            )
        )

    sorted_zones.sort(key=lambda zone: (zone.low, zone.high))

    merged: list[XauZone] = []

    for zone in sorted_zones:
        if not merged or zone.low - merged[-1].high >= 1.5:
            merged.append(
                XauZone(
                    id=f"{broker_day}:R{len(merged) + 1}",
                    low=zone.low,
                    high=zone.high,
                    priority=zone.priority,
                )
            )
        else:
            previous = merged[-1]
            previous.low = min(previous.low, zone.low)
            previous.high = max(previous.high, zone.high)
            previous.priority = max(previous.priority, zone.priority)

    return merged


def count_directional_crosses(
    zones: list[XauZone],
    previous_bid: float,
    current_bid: float,
) -> int:
    crosses = 0

    for zone in zones:
        if previous_bid < zone.low <= current_bid or previous_bid > zone.high >= current_bid:
            crosses += 1

    return crosses


def breakout_valid(
    zone: XauZone,
    direction: XauDirection,
    trend: XauTrend,
    close_price: float,
    engaged: bool,
) -> bool:
    if not engaged:
        return False

    if direction == XauDirection.BUY:
        return trend == XauTrend.UP and close_price > zone.high + BREAKOUT_BUFFER_USD

    return trend == XauTrend.DOWN and close_price < zone.low - BREAKOUT_BUFFER_USD


def reversal_directional_touch(
    zone: XauZone,
    direction: XauDirection,
    trend: XauTrend,
    previous_bid: float,
    current_bid: float,
    multi_zone_tick_gap: bool,
) -> bool:
    if multi_zone_tick_gap:
        return False

    if direction == XauDirection.SELL:
        return trend == XauTrend.UP and previous_bid < zone.low and current_bid >= zone.low

    return trend == XauTrend.DOWN and previous_bid > zone.high and current_bid <= zone.high


def causal_trend_then_reversal(
    zone: XauZone,
    direction: XauDirection,
    current_trend: XauTrend,
    reference_count: int,
    reference_high: float,
    reference_low: float,
    previous_bid: float,
    current_bid: float,
) -> tuple[bool, XauTrend]:
    updated_trend = update_trend(
        current_trend,
        reference_count,
        reference_high,
        reference_low,
        current_bid,
    )

    valid = reversal_directional_touch(
        zone,
        direction,
        updated_trend,
        previous_bid,
        current_bid,
        False,
    )

    return valid, updated_trend


def update_trend(
    current_state: XauTrend,
    reference_count: int,
    reference_high: float,
    reference_low: float,
    bid: float,
) -> XauTrend:
    if reference_count <= 0:
        return current_state

    if bid > reference_high:
        return XauTrend.UP

    if bid < reference_low:
        return XauTrend.DOWN

    return current_state


def pullback_penetrated(
    zone: XauZone,
    direction: XauDirection,
    bid: float,
) -> tuple[bool, float]:
    entry_price = zone.high if direction == XauDirection.BUY else zone.low

    if direction == XauDirection.BUY:
        penetrated = bid <= zone.high - PULLBACK_PENETRATION_USD
    else:
        penetrated = bid >= zone.low + PULLBACK_PENETRATION_USD

    return penetrated, entry_price


def pullback_window_active(bar_offset: int) -> bool:
    return 1 <= bar_offset <= 5


def pullback_usage_allowed(
    zone_priority: int,
    daily_fills: int,
) -> bool:
    if daily_fills < 0:
        return False

    return zone_priority == 1 or daily_fills < 1


def strict_pullback_trend(
    direction: XauDirection,
    closed_directions: list[int],
    current_open: float,
    current_bid: float,
    current_ask: float,
) -> bool:
    required = 1 if direction == XauDirection.BUY else -1

    if any(value != required for value in closed_directions):
        return False

    return current_bid > current_open if direction == XauDirection.BUY else current_ask < current_open


def pre_zone_trigger_price(
    direction: XauDirection,
    target_zone: XauZone,
) -> float:
    if direction == XauDirection.BUY:
        return target_zone.low - PRE_ZONE_TRIGGER_DISTANCE_USD

    return target_zone.high + PRE_ZONE_TRIGGER_DISTANCE_USD


def pre_zone_crossed(
    direction: XauDirection,
    target_zone: XauZone,
    previous_price: float,
    current_price: float,
) -> bool:
    trigger = pre_zone_trigger_price(direction, target_zone)

    if direction == XauDirection.BUY:
        return previous_price < trigger <= current_price

    return previous_price > trigger >= current_price


def blocks_opposite_reversal(
    actual_zone_touch: bool,
    strict_trend_valid: bool,
) -> bool:
    return actual_zone_touch and strict_trend_valid
