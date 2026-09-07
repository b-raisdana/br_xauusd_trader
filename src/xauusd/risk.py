"""Initial trade geometry, native break-even, and profit-protection contracts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from xauusd.signals import OrderType, TradeDirection
from xauusd.zones import Zone, price

BASE_R_USD = Decimal("6.00")
MINIMUM_FREE_SPACE_USD = Decimal("3.00")
FIXED_VOLUME_LOTS = Decimal("0.01")


def _ordered(zones: tuple[Zone, ...] | list[Zone]) -> tuple[Zone, ...]:
    return tuple(sorted(zones, key=lambda zone: (zone.low, zone.high, zone.zone_id)))


def directional_free_space(
    *, zone_id: str, direction: TradeDirection, zones: tuple[Zone, ...] | list[Zone]
) -> Decimal | None:
    ordered = _ordered(zones)
    index = next((i for i, zone in enumerate(ordered) if zone.zone_id == zone_id), None)
    if index is None:
        raise ValueError(f"Unknown Zone: {zone_id}")
    if direction is TradeDirection.BUY:
        if index + 1 >= len(ordered):
            return None
        return ordered[index + 1].low - ordered[index].high
    if index == 0:
        return None
    return ordered[index].low - ordered[index - 1].high


def has_minimum_free_space(
    *, zone_id: str, direction: TradeDirection, zones: tuple[Zone, ...] | list[Zone]
) -> bool:
    free_space = directional_free_space(zone_id=zone_id, direction=direction, zones=zones)
    return free_space is not None and free_space > MINIMUM_FREE_SPACE_USD


@dataclass(frozen=True, slots=True)
class InitialRisk:
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    stop_zone_id: str
    target_zone_id: str


def initial_stop(
    *,
    direction: TradeDirection,
    entry: Decimal | str | int | float,
    zones: tuple[Zone, ...] | list[Zone],
) -> tuple[Decimal, str] | None:
    entry_price = price(entry)
    ordered = _ordered(zones)
    if direction is TradeDirection.BUY:
        candidates = [zone for zone in ordered if zone.high < entry_price]
        if not candidates:
            return None
        stop_zone = candidates[-1]
        return max(stop_zone.high, entry_price - BASE_R_USD), stop_zone.zone_id
    candidates = [zone for zone in ordered if zone.low > entry_price]
    if not candidates:
        return None
    stop_zone = candidates[0]
    return min(stop_zone.low, entry_price + BASE_R_USD), stop_zone.zone_id


def initial_target(
    *,
    direction: TradeDirection,
    entry: Decimal | str | int | float,
    zones: tuple[Zone, ...] | list[Zone],
) -> tuple[Decimal, str] | None:
    entry_price = price(entry)
    ordered = _ordered(zones)
    if direction is TradeDirection.BUY:
        for zone in ordered:
            if zone.low > entry_price and zone.low - entry_price >= BASE_R_USD:
                return zone.low, zone.zone_id
        return None
    for zone in reversed(ordered):
        if zone.high < entry_price and entry_price - zone.high >= BASE_R_USD:
            return zone.high, zone.zone_id
    return None


def build_initial_risk(
    *,
    direction: TradeDirection,
    entry: Decimal | str | int | float,
    zones: tuple[Zone, ...] | list[Zone],
) -> InitialRisk | None:
    stop = initial_stop(direction=direction, entry=entry, zones=zones)
    target = initial_target(direction=direction, entry=entry, zones=zones)
    if stop is None or target is None:
        return None
    return InitialRisk(
        entry=price(entry),
        stop_loss=stop[0],
        take_profit=target[0],
        stop_zone_id=stop[1],
        target_zone_id=target[1],
    )


def risk_free_price(
    *,
    direction: TradeDirection,
    entry: Decimal | str | int | float,
    native_cash_per_price_unit: Decimal | str | int | float,
    native_cost_cash: Decimal | str | int | float,
) -> Decimal:
    """Convert native broker/tester costs to the close price producing net zero."""
    cash_per_unit = price(native_cash_per_price_unit)
    costs = price(native_cost_cash)
    if cash_per_unit <= 0:
        raise ValueError("Native cash per price unit must be positive")
    if costs < 0:
        raise ValueError("Native cost cash cannot be negative")
    offset = costs / cash_per_unit
    entry_price = price(entry)
    return entry_price + offset if direction is TradeDirection.BUY else entry_price - offset


def profit_protection_stop(
    *,
    direction: TradeDirection,
    entry: Decimal | str | int | float,
    risk_free: Decimal | str | int | float,
    current_bid: Decimal | str | int | float,
    current_ask: Decimal | str | int | float,
    current_stop: Decimal | str | int | float,
) -> Decimal | None:
    entry_price = price(entry)
    favorable_move = (
        price(current_bid) - entry_price
        if direction is TradeDirection.BUY
        else entry_price - price(current_ask)
    )
    step = int((favorable_move / BASE_R_USD).to_integral_value(rounding=ROUND_FLOOR))
    if step < 1:
        return None
    offset = BASE_R_USD * (step - 1)
    proposed = (
        price(risk_free) + offset if direction is TradeDirection.BUY else price(risk_free) - offset
    )
    existing = price(current_stop)
    improves = proposed > existing if direction is TradeDirection.BUY else proposed < existing
    return proposed if improves else None


@dataclass(frozen=True, slots=True)
class ProtectedOrder:
    direction: TradeDirection
    order_type: OrderType
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    volume_lots: Decimal = FIXED_VOLUME_LOTS

    def __post_init__(self) -> None:
        if self.direction is TradeDirection.BUY:
            valid = self.stop_loss < self.entry < self.take_profit
        else:
            valid = self.take_profit < self.entry < self.stop_loss
        if not valid:
            raise ValueError("Order must have directional SL and TP at creation")
        if self.volume_lots != FIXED_VOLUME_LOTS:
            raise ValueError("MVP volume must be exactly 0.01 lot")


def maximum_positions(strategy_capital: Decimal | str | int | float) -> int:
    capital = price(strategy_capital)
    if capital == Decimal("200"):
        return 3
    if capital == Decimal("300"):
        return 5
    raise ValueError("Only the confirmed 200 and 300 USD MVP profiles are supported")


def concurrency_allows_entry(
    *, strategy_capital: Decimal | str | int | float, open_positions: int
) -> bool:
    if open_positions < 0:
        raise ValueError("Open-position count cannot be negative")
    return open_positions < maximum_positions(strategy_capital)


def native_margin_allows_entry(
    *, required_margin: Decimal | str | int | float, free_margin: Decimal | str | int | float
) -> bool:
    required = price(required_margin)
    available = price(free_margin)
    if required < 0 or available < 0:
        raise ValueError("Native margin values cannot be negative")
    return required <= available
