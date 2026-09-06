from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from xauusd.zones import (
    BreakoutSide,
    RawZone,
    ZoneEngagementTracker,
    ZonePriority,
    build_daily_zones,
    load_zone_csv,
    price,
)

DAY = date(2026, 9, 6)


def raw(
    low: str,
    high: str,
    *,
    priority: ZonePriority = ZonePriority.NORMAL,
    row: int = 1,
) -> RawZone:
    return RawZone.from_values(
        broker_day=DAY,
        low=low,
        high=high,
        priority=priority,
        source_row=row,
    )


def test_zone_normalize_sort_chain_merge_and_priority() -> None:
    daily = build_daily_zones(
        [
            raw("105", "104", row=4),
            raw("100", "101", row=2),
            raw("102.4", "103", priority=ZonePriority.HIGH, row=3),
        ]
    )

    zones = daily[DAY]
    assert len(zones) == 1
    assert zones[0].low == Decimal("100")
    assert zones[0].high == Decimal("105")
    assert zones[0].priority is ZonePriority.HIGH
    assert zones[0].source_rows == (2, 3, 4)
    assert zones[0].zone_id == "2026-09-06:R1"


def test_zone_merge_gap_is_strict_and_line_zone_is_valid() -> None:
    zones = build_daily_zones([raw("100", "100", row=1), raw("101.5", "102", row=2)])[DAY]

    assert len(zones) == 2
    assert zones[0].low == zones[0].high == Decimal("100")


def test_zone_collection_has_no_hard_cap() -> None:
    inputs = [raw(str(index * 3), str(index * 3), row=index + 1) for index in range(128)]
    assert len(build_daily_zones(inputs)[DAY]) == 128


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_price_rejects_non_finite_values(value: str) -> None:
    with pytest.raises(ValueError, match="finite"):
        price(value)


def test_canonical_zone_csv_loads_all_days_and_rows_without_mutating_source() -> None:
    root = Path(__file__).resolve().parents[1]
    daily = load_zone_csv(root / "data" / "ranges.csv")

    assert len(daily) == 23
    assert sum(len(zone.source_rows) for zones in daily.values() for zone in zones) == 444
    assert all(zones == tuple(sorted(zones, key=lambda zone: zone.low)) for zones in daily.values())


def test_zone_csv_respects_disabled_rows(tmp_path: Path) -> None:
    zone_csv = tmp_path / "zones.csv"
    zone_csv.write_text(
        "date,lower,upper,priority,enabled,note\n"
        "2026.09.06,100,101,invalid,false,disabled before validation\n"
        "2026.09.06,110,111,high,true,enabled\n",
        encoding="utf-8",
    )

    zones = load_zone_csv(zone_csv)[DAY]

    assert len(zones) == 1
    assert zones[0].low == Decimal("110")
    assert zones[0].priority is ZonePriority.HIGH


def test_zone_csv_rejects_bad_priority_with_source_row(tmp_path: Path) -> None:
    zone_csv = tmp_path / "zones.csv"
    zone_csv.write_text(
        "date,lower,upper,priority,enabled,note\n2026.09.06,110,111,invalid,true,bad\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="row 2"):
        load_zone_csv(zone_csv)


def test_open_inside_zone_engages_both_sides_and_new_bar_resets() -> None:
    zone = build_daily_zones([raw("100", "102")])[DAY][0]
    tracker = ZoneEngagementTracker([zone])

    tracker.begin_bar("101")
    assert tracker.is_engaged(zone.zone_id, BreakoutSide.BUY)
    assert tracker.is_engaged(zone.zone_id, BreakoutSide.SELL)

    tracker.begin_bar("99")
    assert not tracker.is_engaged(zone.zone_id, BreakoutSide.BUY)
    assert not tracker.is_engaged(zone.zone_id, BreakoutSide.SELL)


def test_directional_crossing_engages_only_the_crossed_side() -> None:
    zone = build_daily_zones([raw("100", "102")])[DAY][0]
    tracker = ZoneEngagementTracker([zone])
    tracker.begin_bar("99")

    update = tracker.update("99", "100")

    assert [(event.zone_id, event.side) for event in update.events] == [
        (zone.zone_id, BreakoutSide.BUY)
    ]
    assert not tracker.is_engaged(zone.zone_id, BreakoutSide.SELL)

    tracker.begin_bar("103")
    update = tracker.update("103", "102")
    assert [(event.zone_id, event.side) for event in update.events] == [
        (zone.zone_id, BreakoutSide.SELL)
    ]
    assert not tracker.is_engaged(zone.zone_id, BreakoutSide.BUY)


def test_multi_zone_tick_gap_does_not_create_synthetic_engagements() -> None:
    zones = build_daily_zones(
        [raw("100", "101", row=1), raw("104", "105", row=2), raw("108", "109", row=3)]
    )[DAY]
    tracker = ZoneEngagementTracker(zones)
    tracker.begin_bar("99")

    outside = tracker.update("99", "110")
    assert outside.multi_zone_tick_gap
    assert outside.events == ()

    tracker.begin_bar("99")
    inside = tracker.update("99", "104.5")
    assert inside.multi_zone_tick_gap
    assert {(event.zone_id, event.side) for event in inside.events} == {
        (zones[1].zone_id, BreakoutSide.BUY),
        (zones[1].zone_id, BreakoutSide.SELL),
    }
    assert not tracker.is_engaged(zones[0].zone_id, BreakoutSide.BUY)
