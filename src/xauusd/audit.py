"""Immutable strategy audit events and leader-facing marker payloads."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

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
    MODIFY = "modify"
    MODIFY_REJECT = "modify_reject"
    CANCEL = "cancel"
    CANCEL_REJECT = "cancel_reject"


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
    close_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    order_type: OrderType | None
    parent_breakout_id: str | None
    execution_request_id: str | None
    reason: str | None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AuditEvent:
        """Decode one durable event without coercing malformed identity fields."""
        try:
            event_id = payload["event_id"]
            rule_ids_value = payload["rule_ids"]
            zone_id = payload["zone_id"]
            if not isinstance(event_id, str) or not isinstance(zone_id, str):
                raise TypeError("event_id and zone_id must be strings")
            if not isinstance(rule_ids_value, list) or not all(
                isinstance(item, str) for item in rule_ids_value
            ):
                raise TypeError("rule_ids must be a string list")

            def optional_string(field: str) -> str | None:
                value = payload.get(field)
                if value is not None and not isinstance(value, str):
                    raise TypeError(f"{field} must be a string or null")
                return value

            def optional_price(field: str) -> Decimal | None:
                value = payload.get(field)
                return price(value) if value is not None else None

            return cls(
                event_id=event_id,
                rule_ids=tuple(rule_ids_value),
                kind=AuditEventKind(payload["kind"]),
                broker_time=datetime.fromisoformat(payload["broker_time"]),
                zone_id=zone_id,
                signal_family=SignalFamily(payload["signal_family"]),
                direction=TradeDirection(payload["direction"]),
                entry=optional_price("entry"),
                close_price=optional_price("close_price"),
                stop_loss=optional_price("stop_loss"),
                take_profit=optional_price("take_profit"),
                order_type=(
                    OrderType(payload["order_type"])
                    if payload.get("order_type") is not None
                    else None
                ),
                parent_breakout_id=optional_string("parent_breakout_id"),
                execution_request_id=optional_string("execution_request_id"),
                reason=optional_string("reason"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AuditPersistenceError("Invalid durable audit event payload") from exc

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["broker_time"] = self.broker_time.isoformat()
        for field in ("entry", "close_price", "stop_loss", "take_profit"):
            value = payload[field]
            payload[field] = str(value) if value is not None else None
        payload["kind"] = self.kind.value
        payload["signal_family"] = self.signal_family.value
        payload["direction"] = self.direction.value
        payload["order_type"] = self.order_type.value if self.order_type is not None else None
        return payload


class AuditPersistenceError(RuntimeError):
    """Raised when durable audit state cannot be trusted."""


class AuditStore(Protocol):
    def last_sequence(self, broker_day: date) -> int: ...

    def append(self, event: AuditEvent) -> None: ...


class JsonlAuditStore:
    """Durable single-writer JSONL store that fails closed on malformed history."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def last_sequence(self, broker_day: date) -> int:
        if not self.path.exists():
            return 0
        sequences: set[int] = set()
        try:
            with self.path.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.strip():
                        raise AuditPersistenceError(f"Blank audit record at line {line_number}")
                    payload = json.loads(line)
                    event_id = payload.get("event_id")
                    if not isinstance(event_id, str):
                        raise AuditPersistenceError(f"Missing audit Event ID at line {line_number}")
                    event_parts = event_id.rsplit(":E", maxsplit=1)
                    if len(event_parts) != 2:
                        raise AuditPersistenceError(f"Invalid audit Event ID at line {line_number}")
                    event_day, suffix = event_parts
                    try:
                        parsed_day = date.fromisoformat(event_day)
                    except ValueError as exc:
                        raise AuditPersistenceError(
                            f"Invalid audit Event ID at line {line_number}"
                        ) from exc
                    if len(suffix) != 6 or not suffix.isdigit() or int(suffix) < 1:
                        raise AuditPersistenceError(f"Invalid audit Event ID at line {line_number}")
                    if parsed_day != broker_day:
                        continue
                    sequence = int(suffix)
                    if sequence in sequences:
                        raise AuditPersistenceError(
                            f"Duplicate audit Event ID at line {line_number}"
                        )
                    sequences.add(sequence)
        except (OSError, json.JSONDecodeError) as exc:
            raise AuditPersistenceError(f"Cannot recover audit journal: {self.path}") from exc
        if sequences and sequences != set(range(1, max(sequences) + 1)):
            raise AuditPersistenceError(f"Non-contiguous audit sequence: {broker_day.isoformat()}")
        return max(sequences, default=0)

    def append(self, event: AuditEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            event.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        try:
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise AuditPersistenceError(f"Cannot append audit journal: {self.path}") from exc

    def events_for_day(self, broker_day: date) -> tuple[AuditEvent, ...]:
        """Read typed events for lifecycle recovery; any malformed record fails closed."""
        if not self.path.exists():
            return ()
        self.last_sequence(broker_day)
        events: list[AuditEvent] = []
        try:
            with self.path.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.strip():
                        raise AuditPersistenceError(f"Blank audit record at line {line_number}")
                    event = AuditEvent.from_dict(json.loads(line))
                    event_day = event.event_id.rsplit(":E", maxsplit=1)[0]
                    if event.broker_time.date().isoformat() != event_day:
                        raise AuditPersistenceError(
                            f"Audit Event day mismatch at line {line_number}"
                        )
                    if event.broker_time.date() == broker_day:
                        events.append(event)
        except (OSError, json.JSONDecodeError) as exc:
            raise AuditPersistenceError(f"Cannot recover audit journal: {self.path}") from exc
        return tuple(events)


class AuditJournal:
    """Append-only in-memory journal with deterministic Broker-Day Event IDs."""

    def __init__(self, store: AuditStore | None = None) -> None:
        self._broker_day: date | None = None
        self._sequence = 0
        self._events: list[AuditEvent] = []
        self._store = store

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def begin_day(self, broker_day: date) -> None:
        if broker_day != self._broker_day:
            sequence = self._store.last_sequence(broker_day) if self._store else 0
            self._broker_day = broker_day
            self._sequence = sequence

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
        close_price: Decimal | str | int | float | None = None,
        stop_loss: Decimal | str | int | float | None = None,
        take_profit: Decimal | str | int | float | None = None,
        order_type: OrderType | None = None,
        parent_breakout_id: str | None = None,
        execution_request_id: str | None = None,
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
        if (
            kind
            in {
                AuditEventKind.REJECT,
                AuditEventKind.BLOCK,
                AuditEventKind.MODIFY_REJECT,
                AuditEventKind.CANCEL,
                AuditEventKind.CANCEL_REJECT,
            }
            and not reason
        ):
            raise ValueError("Reject/Block/Cancel events require a reason")

        next_sequence = self._sequence + 1
        event = AuditEvent(
            event_id=f"{self._broker_day.isoformat()}:E{next_sequence:06d}",
            rule_ids=rule_ids,
            kind=kind,
            broker_time=broker_time,
            zone_id=zone_id,
            signal_family=signal_family,
            direction=direction,
            entry=price(entry) if entry is not None else None,
            close_price=price(close_price) if close_price is not None else None,
            stop_loss=price(stop_loss) if stop_loss is not None else None,
            take_profit=price(take_profit) if take_profit is not None else None,
            order_type=order_type,
            parent_breakout_id=parent_breakout_id,
            execution_request_id=execution_request_id,
            reason=reason,
        )
        if self._store:
            self._store.append(event)
        self._sequence = next_sequence
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
