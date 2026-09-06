"""Zone input, normalization, merging, and per-bar engagement contracts."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path

MERGE_GAP_USD = Decimal("1.5")


def price(value: Decimal | str | int | float) -> Decimal:
    """Convert external price input without importing binary float artifacts."""
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid price: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"Price must be finite: {value!r}")
    return parsed


class ZonePriority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"

    @classmethod
    def parse(cls, value: str) -> ZonePriority:
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            raise ValueError(f"Invalid zone priority: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class RawZone:
    broker_day: date
    low: Decimal
    high: Decimal
    priority: ZonePriority
    source_row: int

    @classmethod
    def from_values(
        cls,
        *,
        broker_day: date,
        low: Decimal | str | int | float,
        high: Decimal | str | int | float,
        priority: ZonePriority | str,
        source_row: int,
    ) -> RawZone:
        low_price = price(low)
        high_price = price(high)
        parsed_priority = (
            priority if isinstance(priority, ZonePriority) else ZonePriority.parse(priority)
        )
        return cls(
            broker_day=broker_day,
            low=min(low_price, high_price),
            high=max(low_price, high_price),
            priority=parsed_priority,
            source_row=source_row,
        )


@dataclass(frozen=True, slots=True)
class Zone:
    zone_id: str
    broker_day: date
    low: Decimal
    high: Decimal
    priority: ZonePriority
    source_rows: tuple[int, ...]

    def contains(self, bid: Decimal | str | int | float) -> bool:
        value = price(bid)
        return self.low <= value <= self.high


def _parse_enabled(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid enabled value: {value!r}")


def _merge_one_day(day: date, raw_zones: Iterable[RawZone]) -> tuple[Zone, ...]:
    ordered = sorted(raw_zones, key=lambda zone: (zone.low, zone.high, zone.source_row))
    merged: list[tuple[Decimal, Decimal, ZonePriority, tuple[int, ...]]] = []

    for raw in ordered:
        if not merged or raw.low - merged[-1][1] >= MERGE_GAP_USD:
            merged.append((raw.low, raw.high, raw.priority, (raw.source_row,)))
            continue

        low, high, priority, rows = merged[-1]
        merged[-1] = (
            min(low, raw.low),
            max(high, raw.high),
            ZonePriority.HIGH
            if ZonePriority.HIGH in {priority, raw.priority}
            else ZonePriority.NORMAL,
            rows + (raw.source_row,),
        )

    return tuple(
        Zone(
            zone_id=f"{day.isoformat()}:R{index}",
            broker_day=day,
            low=low,
            high=high,
            priority=priority,
            source_rows=rows,
        )
        for index, (low, high, priority, rows) in enumerate(merged, start=1)
    )


def build_daily_zones(raw_zones: Iterable[RawZone]) -> dict[date, tuple[Zone, ...]]:
    """Normalize, sort, and chain-merge enabled raw zones by Broker Day."""
    grouped: dict[date, list[RawZone]] = defaultdict(list)
    for raw in raw_zones:
        grouped[raw.broker_day].append(raw)
    return {day: _merge_one_day(day, grouped[day]) for day in sorted(grouped)}


def load_zone_csv(path: Path) -> dict[date, tuple[Zone, ...]]:
    required = {"date", "lower", "upper", "priority", "enabled"}
    raw_zones: list[RawZone] = []

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = required - fields
        if missing:
            raise ValueError(f"Missing zone CSV columns: {', '.join(sorted(missing))}")

        for row_number, row in enumerate(reader, start=2):
            try:
                if not _parse_enabled(row["enabled"]):
                    continue
                broker_day = datetime.strptime(row["date"].strip(), "%Y.%m.%d").date()
                raw_zones.append(
                    RawZone.from_values(
                        broker_day=broker_day,
                        low=row["lower"],
                        high=row["upper"],
                        priority=row["priority"],
                        source_row=row_number,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid zone CSV row {row_number}: {exc}") from exc

    return build_daily_zones(raw_zones)


class BreakoutSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class EngagementEvent:
    zone_id: str
    side: BreakoutSide


@dataclass(frozen=True, slots=True)
class EngagementUpdate:
    multi_zone_tick_gap: bool
    events: tuple[EngagementEvent, ...]


@dataclass(slots=True)
class _Engagement:
    buy: bool = False
    sell: bool = False


class ZoneEngagementTracker:
    """Track ZONE_ENGAGEMENT state for one Broker Day and M15 bar."""

    def __init__(self, zones: Iterable[Zone]) -> None:
        self._zones = tuple(zones)
        self._state = {zone.zone_id: _Engagement() for zone in self._zones}

    def begin_bar(self, open_bid: Decimal | str | int | float) -> None:
        for zone in self._zones:
            inside = zone.contains(open_bid)
            self._state[zone.zone_id] = _Engagement(buy=inside, sell=inside)

    def is_engaged(self, zone_id: str, side: BreakoutSide) -> bool:
        state = self._state[zone_id]
        return state.buy if side is BreakoutSide.BUY else state.sell

    def count_directional_crosses(
        self,
        previous_bid: Decimal | str | int | float,
        bid: Decimal | str | int | float,
    ) -> int:
        previous = price(previous_bid)
        current = price(bid)
        return sum(
            1
            for zone in self._zones
            if (previous < zone.low <= current) or (previous > zone.high >= current)
        )

    def update(
        self,
        previous_bid: Decimal | str | int | float,
        bid: Decimal | str | int | float,
    ) -> EngagementUpdate:
        previous = price(previous_bid)
        current = price(bid)
        multi_zone_gap = self.count_directional_crosses(previous, current) > 1
        events: list[EngagementEvent] = []

        for zone in self._zones:
            state = self._state[zone.zone_id]
            if multi_zone_gap:
                if zone.contains(current):
                    if not state.buy:
                        state.buy = True
                        events.append(EngagementEvent(zone.zone_id, BreakoutSide.BUY))
                    if not state.sell:
                        state.sell = True
                        events.append(EngagementEvent(zone.zone_id, BreakoutSide.SELL))
                continue

            if not state.buy and previous < zone.low <= current:
                state.buy = True
                events.append(EngagementEvent(zone.zone_id, BreakoutSide.BUY))
            if not state.sell and previous > zone.high >= current:
                state.sell = True
                events.append(EngagementEvent(zone.zone_id, BreakoutSide.SELL))

        return EngagementUpdate(multi_zone_tick_gap=multi_zone_gap, events=tuple(events))
