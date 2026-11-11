from __future__ import annotations

from domain.xau_usd.enums import XauDirection, XauTrend
from domain.xau_usd.models import XauZone

from .constants import (
    PRE_ZONE_TRIGGER_DISTANCE_USD,
    PULLBACK_PENETRATION_USD,
)


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
    from domain.xau_usd.zone import reversal_directional_touch, update_trend

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
