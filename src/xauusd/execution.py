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
    CLOSED = "closed"
    CANCELLED = "cancelled"


def execution_transition(
    status: ExecutionStatus, event_kind: AuditEventKind, order_type: OrderType
) -> ExecutionStatus | None:
    transitions = {
        (ExecutionStatus.SUBMITTED, AuditEventKind.FILL): ExecutionStatus.FILLED,
        (ExecutionStatus.SUBMITTED, AuditEventKind.REJECT): ExecutionStatus.REJECTED,
        (ExecutionStatus.FILLED, AuditEventKind.CLOSE): ExecutionStatus.CLOSED,
        (ExecutionStatus.FILLED, AuditEventKind.MODIFY): ExecutionStatus.FILLED,
        (ExecutionStatus.FILLED, AuditEventKind.MODIFY_REJECT): ExecutionStatus.FILLED,
        (ExecutionStatus.SUBMITTED, AuditEventKind.CANCEL_REJECT): ExecutionStatus.SUBMITTED,
    }
    if (
        status is ExecutionStatus.SUBMITTED
        and event_kind is AuditEventKind.CANCEL
        and order_type is OrderType.PENDING_STOP
    ):
        return ExecutionStatus.CANCELLED
    return transitions.get((status, event_kind))


def protection_modification_valid(
    *,
    direction: TradeDirection,
    entry: Decimal | str | int | float,
    current_stop: Decimal | str | int | float,
    proposed_stop: Decimal | str | int | float,
    proposed_tp: Decimal | str | int | float,
) -> bool:
    entry_price = price(entry)
    existing_stop = price(current_stop)
    stop = price(proposed_stop)
    target = price(proposed_tp)
    if direction is TradeDirection.BUY:
        return stop >= existing_stop and stop < target and target > entry_price
    return stop <= existing_stop and target < stop and target < entry_price


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
    transition_time: datetime
    current_stop_loss: Decimal
    current_take_profit: Decimal


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

    def recover(self, events: tuple[AuditEvent, ...]) -> None:
        """Atomically rebuild request state from ordered durable audit events."""
        if self._broker_day is None:
            raise RuntimeError("Execution Broker Day has not been initialized")
        recovered: dict[str, ExecutionRecord] = {}
        for event in events:
            if event.broker_time.date() != self._broker_day:
                raise ValueError("Recovered Execution event belongs to a different Broker Day")
            request_id = event.execution_request_id
            if request_id is None:
                continue
            if event.kind is AuditEventKind.ORDER:
                if request_id in recovered:
                    raise ValueError(f"Duplicate recovered Execution Request ID: {request_id}")
                if (
                    event.entry is None
                    or event.stop_loss is None
                    or event.take_profit is None
                    or event.order_type is None
                ):
                    raise ValueError("Recovered Order is missing protected order fields")
                request = ExecutionRequest.from_values(
                    request_id=request_id,
                    broker_time=event.broker_time,
                    zone_id=event.zone_id,
                    signal_family=event.signal_family,
                    direction=event.direction,
                    order_type=event.order_type,
                    entry=event.entry,
                    stop_loss=event.stop_loss,
                    take_profit=event.take_profit,
                    rule_ids=event.rule_ids,
                    parent_breakout_id=event.parent_breakout_id,
                )
                recovered[request_id] = ExecutionRecord(
                    request,
                    ExecutionStatus.SUBMITTED,
                    event.broker_time,
                    request.order.stop_loss,
                    request.order.take_profit,
                )
                continue
            try:
                record = recovered[request_id]
            except KeyError as exc:
                raise ValueError(f"Recovered outcome has no Order: {request_id}") from exc
            request = record.request
            if (
                event.zone_id != request.zone_id
                or event.signal_family is not request.signal_family
                or event.direction is not request.direction
                or event.parent_breakout_id != request.parent_breakout_id
            ):
                raise ValueError(f"Recovered outcome identity mismatch: {request_id}")
            if event.broker_time < record.transition_time:
                raise ValueError("Recovered Execution events are not chronological")
            if (
                event.kind is AuditEventKind.FILL
                and record.status is ExecutionStatus.SUBMITTED
                and event.entry is not None
            ):
                status = ExecutionStatus.FILLED
            elif (
                event.kind is AuditEventKind.REJECT
                and record.status is ExecutionStatus.SUBMITTED
                and event.reason is not None
            ):
                status = ExecutionStatus.REJECTED
            elif (
                event.kind is AuditEventKind.CLOSE
                and record.status is ExecutionStatus.FILLED
                and event.close_price is not None
                and event.reason is not None
            ):
                status = ExecutionStatus.CLOSED
            elif (
                event.kind is AuditEventKind.CANCEL
                and record.status is ExecutionStatus.SUBMITTED
                and record.request.order.order_type is OrderType.PENDING_STOP
                and event.reason is not None
            ):
                status = ExecutionStatus.CANCELLED
            elif (
                event.kind is AuditEventKind.CANCEL_REJECT
                and record.status is ExecutionStatus.SUBMITTED
                and event.reason is not None
            ):
                status = ExecutionStatus.SUBMITTED
            elif (
                event.kind is AuditEventKind.MODIFY
                and record.status is ExecutionStatus.FILLED
                and (event.stop_loss is not None or event.take_profit is not None)
            ):
                status = ExecutionStatus.FILLED
            elif (
                event.kind is AuditEventKind.MODIFY_REJECT
                and record.status is ExecutionStatus.FILLED
                and event.reason is not None
            ):
                status = ExecutionStatus.FILLED
            else:
                raise ValueError(f"Invalid recovered Execution transition: {request_id}")
            if event.kind is AuditEventKind.MODIFY:
                stop_loss, take_profit = self._validated_protection(
                    record, event.stop_loss, event.take_profit
                )
            else:
                stop_loss = record.current_stop_loss
                take_profit = record.current_take_profit
            recovered[request_id] = ExecutionRecord(
                record.request, status, event.broker_time, stop_loss, take_profit
            )
        self._records = recovered

    def submit(self, request: ExecutionRequest) -> AuditEvent:
        self._validate_time(request.broker_time)
        if request.request_id in self._records:
            raise ValueError(f"Duplicate Execution Request ID: {request.request_id}")
        event = self._write(request, AuditEventKind.ORDER, request.broker_time)
        self._records[request.request_id] = ExecutionRecord(
            request,
            ExecutionStatus.SUBMITTED,
            request.broker_time,
            request.order.stop_loss,
            request.order.take_profit,
        )
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
        self._records[request_id] = ExecutionRecord(
            record.request,
            ExecutionStatus.FILLED,
            broker_time,
            record.current_stop_loss,
            record.current_take_profit,
        )
        return event

    def reject(self, request_id: str, *, broker_time: datetime, reason: str) -> AuditEvent:
        if not reason.strip():
            raise ValueError("Execution rejection reason is required")
        record = self._pending(request_id, broker_time)
        event = self._write(record.request, AuditEventKind.REJECT, broker_time, reason=reason)
        self._records[request_id] = ExecutionRecord(
            record.request,
            ExecutionStatus.REJECTED,
            broker_time,
            record.current_stop_loss,
            record.current_take_profit,
        )
        return event

    def close(
        self,
        request_id: str,
        *,
        broker_time: datetime,
        close_price: Decimal | str | int | float,
        rule_ids: tuple[str, ...],
        reason: str,
    ) -> AuditEvent:
        self._validate_time(broker_time)
        record = self.record(request_id)
        if record.status is not ExecutionStatus.FILLED:
            raise ValueError(f"Execution Request has no open filled position: {request_id}")
        if broker_time < record.transition_time:
            raise ValueError("Position close precedes fill")
        if not rule_ids or any(not rule_id.strip() for rule_id in rule_ids):
            raise ValueError("Position close requires Rule IDs")
        if not reason.strip():
            raise ValueError("Position close reason is required")
        event = self._write(
            record.request,
            AuditEventKind.CLOSE,
            broker_time,
            close_price=close_price,
            reason=reason,
            extra_rule_ids=rule_ids,
        )
        self._records[request_id] = ExecutionRecord(
            record.request,
            ExecutionStatus.CLOSED,
            broker_time,
            record.current_stop_loss,
            record.current_take_profit,
        )
        return event

    def modify(
        self,
        request_id: str,
        *,
        broker_time: datetime,
        broker_accepted: bool,
        stop_loss: Decimal | str | int | float | None = None,
        take_profit: Decimal | str | int | float | None = None,
        rule_ids: tuple[str, ...],
        rejection_reason: str | None = None,
    ) -> AuditEvent:
        self._validate_time(broker_time)
        record = self.record(request_id)
        if record.status is not ExecutionStatus.FILLED:
            raise ValueError(f"Execution Request has no open filled position: {request_id}")
        if broker_time < record.transition_time:
            raise ValueError("Position modification precedes latest transition")
        if stop_loss is None and take_profit is None:
            raise ValueError("Position modification requires SL or TP")
        if not rule_ids or any(not rule_id.strip() for rule_id in rule_ids):
            raise ValueError("Position modification requires Rule IDs")
        if broker_accepted and rejection_reason is not None:
            raise ValueError("Accepted modification cannot have a rejection reason")
        if not broker_accepted and not rejection_reason:
            raise ValueError("Rejected modification requires a reason")
        proposed_stop, proposed_tp = self._validated_protection(record, stop_loss, take_profit)
        direction = record.request.direction
        kind = AuditEventKind.MODIFY if broker_accepted else AuditEventKind.MODIFY_REJECT
        event = self.journal.record(
            rule_ids=tuple(dict.fromkeys((*record.request.rule_ids, *rule_ids))),
            kind=kind,
            broker_time=broker_time,
            zone_id=record.request.zone_id,
            signal_family=record.request.signal_family,
            direction=direction,
            entry=record.request.order.entry,
            stop_loss=proposed_stop,
            take_profit=proposed_tp,
            order_type=record.request.order.order_type,
            parent_breakout_id=record.request.parent_breakout_id,
            execution_request_id=request_id,
            reason=rejection_reason,
        )
        self._records[request_id] = ExecutionRecord(
            record.request,
            ExecutionStatus.FILLED,
            broker_time,
            proposed_stop if broker_accepted else record.current_stop_loss,
            proposed_tp if broker_accepted else record.current_take_profit,
        )
        return event

    @staticmethod
    def _validated_protection(
        record: ExecutionRecord,
        stop_loss: Decimal | str | int | float | None,
        take_profit: Decimal | str | int | float | None,
    ) -> tuple[Decimal, Decimal]:
        proposed_stop = price(stop_loss) if stop_loss is not None else record.current_stop_loss
        proposed_tp = price(take_profit) if take_profit is not None else record.current_take_profit
        direction = record.request.direction
        if not protection_modification_valid(
            direction=direction,
            entry=record.request.order.entry,
            current_stop=record.current_stop_loss,
            proposed_stop=proposed_stop,
            proposed_tp=proposed_tp,
        ):
            raise ValueError("Position modification would loosen SL or invalidate protection")
        return proposed_stop, proposed_tp

    def cancel_pending(
        self,
        request_id: str,
        *,
        broker_time: datetime,
        broker_accepted: bool,
        rule_ids: tuple[str, ...],
        reason: str,
    ) -> AuditEvent:
        record = self._pending(request_id, broker_time)
        if record.request.order.order_type is not OrderType.PENDING_STOP:
            raise ValueError("Only a Pending order can be cancelled")
        if not rule_ids or any(not rule_id.strip() for rule_id in rule_ids):
            raise ValueError("Pending cancellation requires Rule IDs")
        if not reason.strip():
            raise ValueError("Pending cancellation reason is required")
        kind = AuditEventKind.CANCEL if broker_accepted else AuditEventKind.CANCEL_REJECT
        event = self._write(
            record.request,
            kind,
            broker_time,
            reason=reason,
            extra_rule_ids=rule_ids,
        )
        self._records[request_id] = ExecutionRecord(
            record.request,
            ExecutionStatus.CANCELLED if broker_accepted else ExecutionStatus.SUBMITTED,
            broker_time,
            record.current_stop_loss,
            record.current_take_profit,
        )
        return event

    def _pending(self, request_id: str, broker_time: datetime) -> ExecutionRecord:
        self._validate_time(broker_time)
        record = self.record(request_id)
        if record.status is not ExecutionStatus.SUBMITTED:
            raise ValueError(f"Execution Request already resolved: {request_id}")
        if broker_time < record.transition_time:
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
        close_price: Decimal | str | int | float | None = None,
        reason: str | None = None,
        extra_rule_ids: tuple[str, ...] = (),
    ) -> AuditEvent:
        order = request.order
        rule_ids = tuple(
            dict.fromkeys((*request.rule_ids, "ORDER_PROTECTED_FROM_CREATION", *extra_rule_ids))
        )
        return self.journal.record(
            rule_ids=rule_ids,
            kind=kind,
            broker_time=broker_time,
            zone_id=request.zone_id,
            signal_family=request.signal_family,
            direction=request.direction,
            entry=order.entry if entry is None else entry,
            close_price=close_price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            order_type=order.order_type,
            parent_breakout_id=request.parent_breakout_id,
            execution_request_id=request.request_id,
            reason=reason,
        )
