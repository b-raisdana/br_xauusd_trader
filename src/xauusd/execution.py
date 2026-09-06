"""Deterministic order-request lifecycle projected into the durable audit stream."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from xauusd.audit import AuditEvent, AuditEventKind, AuditJournal, SignalFamily
from xauusd.risk import ProtectedOrder
from xauusd.signals import OrderType, TradeDirection
from xauusd.zones import price


class ExecutionStatus(StrEnum):
    SUBMITTED = "submitted"
    FILLED = "filled"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    request_id: str
    broker_time: datetime
    zone_id: str
    signal_family: SignalFamily
    direction: TradeDirection
    order: ProtectedOrder
    rule_ids: tuple[str, ...]
    parent_breakout_id: str | None = None

    @classmethod
    def from_values(
        cls,
        *,
        request_id: str,
        broker_time: datetime,
        zone_id: str,
        signal_family: SignalFamily,
        direction: TradeDirection,
        order_type: OrderType,
        entry: Decimal | str | int | float,
        stop_loss: Decimal | str | int | float,
        take_profit: Decimal | str | int | float,
        rule_ids: tuple[str, ...],
        parent_breakout_id: str | None = None,
    ) -> ExecutionRequest:
        if not request_id.strip():
            raise ValueError("Execution Request ID is required")
        if not zone_id.strip():
            raise ValueError("Zone ID is required")
        return cls(
            request_id=request_id,
            broker_time=broker_time,
            zone_id=zone_id,
            signal_family=signal_family,
            direction=direction,
            order=ProtectedOrder(
                direction=direction,
                order_type=order_type,
                entry=price(entry),
                stop_loss=price(stop_loss),
                take_profit=price(take_profit),
            ),
            rule_ids=rule_ids,
            parent_breakout_id=parent_breakout_id,
        )


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    request: ExecutionRequest
    status: ExecutionStatus


class ExecutionLedger:
    """Allow one terminal outcome per protected request; audit persistence commits first."""

    def __init__(self, journal: AuditJournal) -> None:
        self.journal = journal
        self._broker_day: date | None = None
        self._records: dict[str, ExecutionRecord] = {}

    def begin_day(self, broker_day: date) -> None:
        if broker_day != self._broker_day:
            self._broker_day = broker_day
            self._records.clear()
        self.journal.begin_day(broker_day)

    def record(self, request_id: str) -> ExecutionRecord:
        try:
            return self._records[request_id]
        except KeyError as exc:
            raise ValueError(f"Unknown Execution Request ID: {request_id}") from exc

    def submit(self, request: ExecutionRequest) -> AuditEvent:
        self._validate_time(request.broker_time)
        if request.request_id in self._records:
            raise ValueError(f"Duplicate Execution Request ID: {request.request_id}")
        event = self._write(request, AuditEventKind.ORDER, request.broker_time)
        self._records[request.request_id] = ExecutionRecord(request, ExecutionStatus.SUBMITTED)
        return event

    def fill(
        self,
        request_id: str,
        *,
        broker_time: datetime,
        fill_price: Decimal | str | int | float,
    ) -> AuditEvent:
        record = self._pending(request_id, broker_time)
        event = self._write(record.request, AuditEventKind.FILL, broker_time, entry=fill_price)
        self._records[request_id] = ExecutionRecord(record.request, ExecutionStatus.FILLED)
        return event

    def reject(self, request_id: str, *, broker_time: datetime, reason: str) -> AuditEvent:
        if not reason.strip():
            raise ValueError("Execution rejection reason is required")
        record = self._pending(request_id, broker_time)
        event = self._write(record.request, AuditEventKind.REJECT, broker_time, reason=reason)
        self._records[request_id] = ExecutionRecord(record.request, ExecutionStatus.REJECTED)
        return event

    def _pending(self, request_id: str, broker_time: datetime) -> ExecutionRecord:
        self._validate_time(broker_time)
        record = self.record(request_id)
        if record.status is not ExecutionStatus.SUBMITTED:
            raise ValueError(f"Execution Request already resolved: {request_id}")
        if broker_time < record.request.broker_time:
            raise ValueError("Execution outcome precedes request")
        return record

    def _validate_time(self, broker_time: datetime) -> None:
        if self._broker_day is None:
            raise RuntimeError("Execution Broker Day has not been initialized")
        if broker_time.date() != self._broker_day:
            raise ValueError("Execution time belongs to a different Broker Day")

    def _write(
        self,
        request: ExecutionRequest,
        kind: AuditEventKind,
        broker_time: datetime,
        *,
        entry: Decimal | str | int | float | None = None,
        reason: str | None = None,
    ) -> AuditEvent:
        order = request.order
        rule_ids = tuple(dict.fromkeys((*request.rule_ids, "ORDER_PROTECTED_FROM_CREATION")))
        return self.journal.record(
            rule_ids=rule_ids,
            kind=kind,
            broker_time=broker_time,
            zone_id=request.zone_id,
            signal_family=request.signal_family,
            direction=request.direction,
            entry=order.entry if entry is None else entry,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            order_type=order.order_type,
            parent_breakout_id=request.parent_breakout_id,
            execution_request_id=request.request_id,
            reason=reason,
        )
