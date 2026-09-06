"""Immutable strategy audit events and leader-facing marker payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from xauusd.signals import OrderType, TradeDirection
from xauusd.zones import ZonePriority, price


class SignalFamily(StrEnum):
    REVERSAL = "reversal"
    BREAKOUT = "breakout"
    PULLBACK = "pullback"


class AuditEventKind(StrEnum):
    SIGNAL = "signal"
    ORDER = "order"
    FILL = "fill"
    CLOSE = "close"
    REJECT = "reject"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    rule_ids: tuple[str, ...]
    kind: AuditEventKind
    broker_time: datetime
    zone_id: str
    signal_family: SignalFamily
    direction: TradeDirection
    entry: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    order_type: OrderType | None
    parent_breakout_id: str | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["broker_time"] = self.broker_time.isoformat()
        for field in ("entry", "stop_loss", "take_profit"):
            value = payload[field]
            payload[field] = str(value) if value is not None else None
        payload["kind"] = self.kind.value
        payload["signal_family"] = self.signal_family.value
        payload["direction"] = self.direction.value
        payload["order_type"] = self.order_type.value if self.order_type is not None else None
        return payload


class AuditJournal:
    """Append-only in-memory journal with deterministic Broker-Day Event IDs."""

    def __init__(self) -> None:
        self._broker_day: date | None = None
        self._sequence = 0
        self._events: list[AuditEvent] = []

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def begin_day(self, broker_day: date) -> None:
        if broker_day != self._broker_day:
            self._broker_day = broker_day
            self._sequence = 0

    def record(
        self,
        *,
        rule_ids: tuple[str, ...],
        kind: AuditEventKind,
        broker_time: datetime,
        zone_id: str,
        signal_family: SignalFamily,
        direction: TradeDirection,
        entry: Decimal | str | int | float | None = None,
        stop_loss: Decimal | str | int | float | None = None,
        take_profit: Decimal | str | int | float | None = None,
        order_type: OrderType | None = None,
        parent_breakout_id: str | None = None,
        reason: str | None = None,
    ) -> AuditEvent:
        if self._broker_day is None:
            raise RuntimeError("Audit Broker Day has not been initialized")
        if broker_time.date() != self._broker_day:
            raise ValueError("Audit time belongs to a different Broker Day")
        if not rule_ids or any(not rule_id.strip() for rule_id in rule_ids):
            raise ValueError("At least one non-empty Rule ID is required")
        if not zone_id.strip():
            raise ValueError("Zone ID is required")
        if kind is AuditEventKind.ORDER and order_type is None:
            raise ValueError("Order events require Order Type")
        if signal_family is SignalFamily.PULLBACK and not parent_breakout_id:
            raise ValueError("Pullback events require parent Breakout ID")
        if kind in {AuditEventKind.REJECT, AuditEventKind.BLOCK} and not reason:
            raise ValueError("Reject/Block events require a reason")

        self._sequence += 1
        event = AuditEvent(
            event_id=f"{self._broker_day.isoformat()}:E{self._sequence:06d}",
            rule_ids=rule_ids,
            kind=kind,
            broker_time=broker_time,
            zone_id=zone_id,
            signal_family=signal_family,
            direction=direction,
            entry=price(entry) if entry is not None else None,
            stop_loss=price(stop_loss) if stop_loss is not None else None,
            take_profit=price(take_profit) if take_profit is not None else None,
            order_type=order_type,
            parent_breakout_id=parent_breakout_id,
            reason=reason,
        )
        self._events.append(event)
        return event


@dataclass(frozen=True, slots=True)
class ChartMarker:
    label: str
    broker_time: datetime
    price: Decimal | None
    color_key: str
    tooltip: str


def chart_marker(event: AuditEvent, zone_priority: ZonePriority) -> ChartMarker:
    abbreviations = {
        (SignalFamily.REVERSAL, TradeDirection.BUY): "R-B",
        (SignalFamily.REVERSAL, TradeDirection.SELL): "R-S",
        (SignalFamily.BREAKOUT, TradeDirection.BUY): "BO-B",
        (SignalFamily.BREAKOUT, TradeDirection.SELL): "BO-S",
        (SignalFamily.PULLBACK, TradeDirection.BUY): "PB-B",
        (SignalFamily.PULLBACK, TradeDirection.SELL): "PB-S",
    }
    tooltip = (
        f"Time={event.broker_time.isoformat()} | Zone={event.zone_id} | "
        f"Entry={event.entry} | SL={event.stop_loss} | TP={event.take_profit} | "
        f"Event={event.event_id}"
    )
    return ChartMarker(
        label=abbreviations[(event.signal_family, event.direction)],
        broker_time=event.broker_time,
        price=event.entry,
        color_key=f"zone_{zone_priority.value}",
        tooltip=tooltip,
    )
