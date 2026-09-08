from datetime import date
from decimal import Decimal

import pytest

from xauusd.risk import (
    FIXED_VOLUME_LOTS,
    ProtectedOrder,
    build_initial_risk,
    concurrency_allows_entry,
    directional_free_space,
    has_minimum_free_space,
    initial_stop,
    initial_target,
    maximum_positions,
    native_margin_allows_entry,
    profit_protection_stop,
    risk_free_price,
)
from xauusd.signals import OrderType, TradeDirection
from xauusd.zones import RawZone, Zone, build_daily_zones

DAY = date(2026, 9, 6)


def make_zones(*bounds: tuple[str, str]) -> tuple[Zone, ...]:
    return build_daily_zones(
        RawZone.from_values(
            broker_day=DAY,
            low=low,
            high=high,
            priority="normal",
            source_row=index,
        )
        for index, (low, high) in enumerate(bounds, start=1)
    )[DAY]


def test_directional_free_space_uses_adjacent_zone_and_strict_minimum() -> None:
    zones = make_zones(("90", "91"), ("95", "96"), ("99", "100"))
    middle = zones[1]
    assert (
        directional_free_space(
            zone_id=middle.zone_id, direction=TradeDirection.BUY, zones=list(reversed(zones))
        )
        == 3
    )
    assert (
        directional_free_space(zone_id=middle.zone_id, direction=TradeDirection.SELL, zones=zones)
        == 4
    )
    assert not has_minimum_free_space(
        zone_id=middle.zone_id, direction=TradeDirection.BUY, zones=zones
    )
    assert has_minimum_free_space(
        zone_id=middle.zone_id, direction=TradeDirection.SELL, zones=zones
    )
    assert not has_minimum_free_space(
        zone_id=zones[0].zone_id, direction=TradeDirection.SELL, zones=zones
    )


def test_initial_stop_uses_nearest_structural_zone_with_six_dollar_cap() -> None:
    zones = make_zones(("85", "86"), ("97", "98"), ("110", "111"), ("120", "121"))
    assert initial_stop(direction=TradeDirection.BUY, entry="100", zones=zones) == (
        Decimal("98"),
        zones[1].zone_id,
    )
    assert initial_stop(direction=TradeDirection.BUY, entry="105", zones=zones) == (
        Decimal("99.00"),
        zones[1].zone_id,
    )
    assert initial_stop(direction=TradeDirection.SELL, entry="100", zones=zones) == (
        Decimal("106.00"),
        zones[2].zone_id,
    )
    assert initial_stop(direction=TradeDirection.BUY, entry="80", zones=zones) is None


def test_initial_target_skips_near_zone_and_rejects_when_missing() -> None:
    zones = make_zones(("90", "91"), ("96", "97"), ("104", "105"), ("108", "109"))
    assert initial_target(direction=TradeDirection.BUY, entry="100", zones=zones) == (
        Decimal("108"),
        zones[3].zone_id,
    )
    assert initial_target(direction=TradeDirection.SELL, entry="100", zones=zones) == (
        Decimal("91"),
        zones[0].zone_id,
    )
    assert initial_target(direction=TradeDirection.BUY, entry="110", zones=zones) is None
    assert build_initial_risk(direction=TradeDirection.BUY, entry="100", zones=zones) is not None


def test_risk_free_uses_native_cash_conversion_not_raw_entry() -> None:
    assert risk_free_price(
        direction=TradeDirection.BUY,
        entry="3400",
        native_cash_per_price_unit="1.00",
        native_cost_cash="0.75",
    ) == Decimal("3400.75")
    assert risk_free_price(
        direction=TradeDirection.SELL,
        entry="3400",
        native_cash_per_price_unit="2.00",
        native_cost_cash="0.50",
    ) == Decimal("3399.75")


def test_profit_protection_has_unlimited_steps_and_never_loosens_stop() -> None:
    assert profit_protection_stop(
        direction=TradeDirection.BUY,
        entry="100",
        risk_free="100.25",
        current_bid="124.1",
        current_ask="124.2",
        current_stop="112",
    ) == Decimal("118.25")
    assert (
        profit_protection_stop(
            direction=TradeDirection.BUY,
            entry="100",
            risk_free="100.25",
            current_bid="112",
            current_ask="112.1",
            current_stop="107",
        )
        is None
    )
    assert profit_protection_stop(
        direction=TradeDirection.SELL,
        entry="100",
        risk_free="99.75",
        current_bid="75.8",
        current_ask="75.9",
        current_stop="88",
    ) == Decimal("81.75")


def test_protected_order_requires_directional_sl_tp_and_fixed_volume() -> None:
    order = ProtectedOrder(
        direction=TradeDirection.BUY,
        order_type=OrderType.MARKET,
        entry=Decimal("100"),
        stop_loss=Decimal("96"),
        take_profit=Decimal("108"),
    )
    assert order.volume_lots == FIXED_VOLUME_LOTS
    with pytest.raises(ValueError, match="directional"):
        ProtectedOrder(
            direction=TradeDirection.BUY,
            order_type=OrderType.MARKET,
            entry=Decimal("100"),
            stop_loss=Decimal("100"),
            take_profit=Decimal("108"),
        )


def test_capital_profiles_and_native_margin_gate_are_strict() -> None:
    assert maximum_positions("200") == 3
    assert maximum_positions("300") == 5
    assert concurrency_allows_entry(strategy_capital="200", open_positions=2)
    assert not concurrency_allows_entry(strategy_capital="200", open_positions=3)
    assert native_margin_allows_entry(required_margin="25", free_margin="25")
    assert not native_margin_allows_entry(required_margin="25.01", free_margin="25")
    with pytest.raises(ValueError, match="confirmed"):
        maximum_positions("250")
