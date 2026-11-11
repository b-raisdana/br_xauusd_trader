from __future__ import annotations

from application.xauusd_trading_strategy_1_vector.domain.constants import (
    BASE_R_USD,
    GROSS_DAILY_RISK_FRACTION,
    MINIMUM_FREE_SPACE_USD,
    PARITY_PRICE_TOLERANCE,
)
from domain.xau_usd.enums import XauDirection, XauEntryRejection
from domain.xau_usd.models import XauZone


def initial_stop(
    direction: XauDirection,
    entry: float,
    zones: list[XauZone],
) -> tuple[bool, float | None, str | None]:
    found = False
    nearest = 0.0
    stop_zone_id: str | None = None

    for zone in zones:
        if direction == XauDirection.BUY and zone.high < entry and (not found or zone.high > nearest):
            found = True
            nearest = zone.high
            stop_zone_id = zone.id

        if direction == XauDirection.SELL and zone.low > entry and (not found or zone.low < nearest):
            found = True
            nearest = zone.low
            stop_zone_id = zone.id

    if not found:
        return False, None, None

    stop_loss = max(nearest, entry - BASE_R_USD) if direction == XauDirection.BUY else min(nearest, entry + BASE_R_USD)

    return True, stop_loss, stop_zone_id


def directional_free_space(
    zone_id: str,
    direction: XauDirection,
    zones: list[XauZone],
) -> tuple[bool, float]:
    index = next(
        (i for i, zone in enumerate(zones) if zone.id == zone_id),
        -1,
    )

    if index < 0:
        return False, 0.0

    if direction == XauDirection.BUY:
        if index + 1 >= len(zones):
            return False, 0.0

        return True, zones[index + 1].low - zones[index].high

    if index == 0:
        return False, 0.0

    return True, zones[index].low - zones[index - 1].high


def has_minimum_free_space(
    zone_id: str,
    direction: XauDirection,
    zones: list[XauZone],
) -> bool:
    found, free_space = directional_free_space(
        zone_id,
        direction,
        zones,
    )

    return found and free_space > MINIMUM_FREE_SPACE_USD


def initial_target(
    direction: XauDirection,
    entry: float,
    zones: list[XauZone],
) -> tuple[bool, float | None, str | None]:
    found = False
    nearest = 0.0
    target_zone_id: str | None = None

    for zone in zones:
        if (
            direction == XauDirection.BUY
            and zone.low > entry
            and zone.low - entry >= BASE_R_USD
            and (not found or zone.low < nearest)
        ):
            found = True
            nearest = zone.low
            target_zone_id = zone.id

        if (
            direction == XauDirection.SELL
            and zone.high < entry
            and entry - zone.high >= BASE_R_USD
            and (not found or zone.high > nearest)
        ):
            found = True
            nearest = zone.high
            target_zone_id = zone.id

    if not found:
        return False, None, None

    return True, nearest, target_zone_id


def portfolio_risk_allows(
    strategy_capital: float,
    realized_gross_loss: float,
    open_risk: float,
    pending_risk: float,
    proposed_risk: float,
) -> bool:
    if (
        strategy_capital <= 0.0
        or realized_gross_loss < 0.0
        or open_risk < 0.0
        or pending_risk < 0.0
        or proposed_risk < 0.0
    ):
        return False

    budget = strategy_capital * GROSS_DAILY_RISK_FRACTION

    return realized_gross_loss + open_risk + pending_risk + proposed_risk <= budget + 1e-9


def maximum_positions(strategy_capital: float) -> int:
    if abs(strategy_capital - 200.0) <= PARITY_PRICE_TOLERANCE:
        return 3

    if abs(strategy_capital - 300.0) <= PARITY_PRICE_TOLERANCE:
        return 5

    return -1


def concurrency_allows_entry(
    strategy_capital: float,
    open_positions: int,
) -> bool:
    maximum = maximum_positions(strategy_capital)

    return maximum >= 0 and open_positions >= 0 and open_positions < maximum


def native_margin_allows_entry(
    required_margin: float,
    free_margin: float,
) -> bool:
    return required_margin >= 0.0 and free_margin >= 0.0 and required_margin <= free_margin


def evaluate_protected_entry(
    daily_locked: bool,
    portfolio_allowed: bool,
    concurrency_allowed: bool,
    margin_allowed: bool,
    direction: XauDirection,
    entry: float,
    stop_loss: float,
    take_profit: float,
    volume_lots: float,
) -> XauEntryRejection:
    if daily_locked:
        return XauEntryRejection.DAILY_LOSS

    if not portfolio_allowed:
        return XauEntryRejection.GROSS_RISK

    if not concurrency_allowed:
        return XauEntryRejection.CONCURRENCY

    if not margin_allowed:
        return XauEntryRejection.MARGIN

    protected_order = (
        stop_loss < entry < take_profit if direction == XauDirection.BUY else take_profit < entry < stop_loss
    )

    if not protected_order or abs(volume_lots - 0.01) > PARITY_PRICE_TOLERANCE:
        return XauEntryRejection.INVALID_PROTECTION

    return XauEntryRejection.ALLOWED
