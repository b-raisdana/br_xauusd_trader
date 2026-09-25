from __future__ import annotations

from .constants import BREAKOUT_BUFFER_USD
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
