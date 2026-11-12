from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import StrategyV1Config


class PositionStatus(StrEnum):
    FLAT = "flat"
    LIMIT_PENDING = "limit_pending"
    OPEN = "open"
    CLOSE_REQUESTED = "close_requested"
    CLOSE_RETRY_REQUIRED = "close_retry_required"


class PositionState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    status: PositionStatus = PositionStatus.FLAT
    order_id: str | None = None
    position_id: str | None = None
    direction: Literal["buy", "sell"] | None = None
    entry_reference: float | None = None
    fill_price: float | None = None
    volume_lots: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime | None = None
    close_reason: str | None = None
    close_retry_count: int = Field(default=0, ge=0)
    last_event_id: str | None = None
    last_realized_net_pnl_usd: float | None = None

    @model_validator(mode="after")
    def validate_lifecycle_fields(self) -> PositionState:
        if self.status == PositionStatus.FLAT:
            if self.order_id is not None or self.position_id is not None or self.direction is not None:
                raise ValueError("flat state must not retain active order or position identifiers")
        elif self.status == PositionStatus.LIMIT_PENDING:
            if self.order_id is None or self.direction is None or self.entry_reference is None:
                raise ValueError("pending LIMIT state requires its order, direction and fixed entry reference")
            if self.stop_loss is None or self.take_profit is None:
                raise ValueError("pending LIMIT state requires attached SL and TP")
        elif self.status in {
            PositionStatus.OPEN,
            PositionStatus.CLOSE_REQUESTED,
            PositionStatus.CLOSE_RETRY_REQUIRED,
        } and any(
            value is None
            for value in (
                self.position_id,
                self.order_id,
                self.direction,
                self.fill_price,
                self.volume_lots,
                self.stop_loss,
                self.take_profit,
                self.opened_at,
            )
        ):
            raise ValueError("open position state requires fill and attached protection details")
        if self.opened_at is not None and not _is_utc(self.opened_at):
            raise ValueError("opened_at must be UTC-aware")
        return self


class PositionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    event_id: str = Field(min_length=1)
    kind: Literal[
        "limit_submitted",
        "limit_canceled",
        "filled",
        "close_requested",
        "close_rejected",
        "close_unknown",
        "closed",
    ]
    event_time: datetime
    order_id: str | None = None
    position_id: str | None = None
    direction: Literal["buy", "sell"] | None = None
    entry_reference: float | None = None
    fill_price: float | None = None
    volume_lots: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    close_reason: str | None = None
    profit_before_charges_usd: float | None = None
    commission_cost_usd: float | None = None
    swap_pnl_usd: float | None = None
    fee_cost_usd: float | None = None
    spread_slippage_cost_usd: float | None = None

    @model_validator(mode="after")
    def validate_event(self) -> PositionEvent:
        if not _is_utc(self.event_time):
            raise ValueError("event_time must be UTC-aware")
        if self.kind == "limit_submitted" and any(
            value is None
            for value in (self.order_id, self.direction, self.entry_reference, self.stop_loss, self.take_profit)
        ):
            raise ValueError("LIMIT submission requires fixed reference and attached SL/TP")
        if self.kind == "filled" and any(
            value is None for value in (self.order_id, self.position_id, self.fill_price, self.volume_lots)
        ):
            raise ValueError("fill event requires order, position, fill price and volume")
        if self.kind in {"limit_canceled", "close_requested", "close_rejected", "close_unknown", "closed"} and (
            self.order_id is None
        ):
            raise ValueError("lifecycle event requires order_id")
        if self.kind in {"close_requested", "close_rejected", "close_unknown", "closed"} and self.position_id is None:
            raise ValueError("position lifecycle event requires position_id")
        if self.kind == "closed" and any(
            value is None
            for value in (
                self.profit_before_charges_usd,
                self.commission_cost_usd,
                self.swap_pnl_usd,
                self.fee_cost_usd,
                self.spread_slippage_cost_usd,
            )
        ):
            raise ValueError("close event requires every realized PnL and cost component")
        if (
            self.kind == "closed"
            and min(
                self.commission_cost_usd or 0.0,
                self.fee_cost_usd or 0.0,
                self.spread_slippage_cost_usd or 0.0,
            )
            < 0.0
        ):
            raise ValueError("realized charge costs must be non-negative")
        return self


class PositionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    state: PositionState
    action: Literal["none", "request_close", "retry_close", "cancel_limit"] = "none"
    realized_net_pnl_usd: float | None = None


def apply_position_event(state: PositionState, event: PositionEvent) -> PositionTransition:
    if state.last_event_id == event.event_id:
        return PositionTransition(state=state)

    if event.kind == "limit_submitted":
        if state.status != PositionStatus.FLAT:
            raise ValueError("a second order cannot be submitted while an order or position is active")
        next_state = PositionState(
            status=PositionStatus.LIMIT_PENDING,
            order_id=event.order_id,
            direction=event.direction,
            entry_reference=event.entry_reference,
            stop_loss=event.stop_loss,
            take_profit=event.take_profit,
            last_event_id=event.event_id,
            last_realized_net_pnl_usd=state.last_realized_net_pnl_usd,
        )
        return PositionTransition(state=next_state)

    if event.kind == "limit_canceled":
        _require_matching(state, event, PositionStatus.LIMIT_PENDING)
        return PositionTransition(
            state=PositionState(
                last_event_id=event.event_id, last_realized_net_pnl_usd=state.last_realized_net_pnl_usd
            ),
        )

    if event.kind == "filled":
        _require_matching(state, event, PositionStatus.LIMIT_PENDING)
        next_state = PositionState(
            status=PositionStatus.OPEN,
            order_id=state.order_id,
            position_id=event.position_id,
            direction=state.direction,
            entry_reference=state.entry_reference,
            fill_price=event.fill_price,
            volume_lots=event.volume_lots,
            stop_loss=state.stop_loss,
            take_profit=state.take_profit,
            opened_at=event.event_time,
            last_event_id=event.event_id,
            last_realized_net_pnl_usd=state.last_realized_net_pnl_usd,
        )
        return PositionTransition(state=next_state)

    if event.kind == "close_requested":
        _require_matching(state, event, PositionStatus.OPEN)
        return PositionTransition(
            state=state.model_copy(
                update={
                    "status": PositionStatus.CLOSE_REQUESTED,
                    "close_reason": event.close_reason,
                    "last_event_id": event.event_id,
                },
            ),
            action="request_close",
        )

    if event.kind in {"close_rejected", "close_unknown"}:
        _require_matching(
            state,
            event,
            {PositionStatus.CLOSE_REQUESTED, PositionStatus.CLOSE_RETRY_REQUIRED},
        )
        return PositionTransition(
            state=state.model_copy(
                update={
                    "status": PositionStatus.CLOSE_RETRY_REQUIRED,
                    "close_retry_count": state.close_retry_count + 1,
                    "last_event_id": event.event_id,
                },
            ),
            action="retry_close",
        )

    _require_matching(
        state,
        event,
        {
            PositionStatus.OPEN,
            PositionStatus.CLOSE_REQUESTED,
            PositionStatus.CLOSE_RETRY_REQUIRED,
        },
    )
    net_pnl = (
        float(event.profit_before_charges_usd)
        - float(event.commission_cost_usd)
        + float(event.swap_pnl_usd)
        - float(event.fee_cost_usd)
        - float(event.spread_slippage_cost_usd)
    )
    if not isfinite(net_pnl):
        raise ValueError("realized net PnL must be finite")
    next_state = PositionState(last_event_id=event.event_id, last_realized_net_pnl_usd=net_pnl)
    return PositionTransition(state=next_state, realized_net_pnl_usd=net_pnl)


def request_limit_cancellation(state: PositionState) -> PositionTransition:
    if state.status != PositionStatus.LIMIT_PENDING or state.order_id is None:
        return PositionTransition(state=state)
    return PositionTransition(state=state, action="cancel_limit")


def request_close_retry(state: PositionState) -> PositionTransition:
    if state.status != PositionStatus.CLOSE_RETRY_REQUIRED:
        return PositionTransition(state=state)
    return PositionTransition(state=state, action="retry_close")


def position_deadline_action(
    state: PositionState,
    as_of: datetime,
    market_close_at: datetime,
    config: StrategyV1Config,
) -> Literal["request_close", "cancel_limit"] | None:
    for value, name in ((as_of, "as_of"), (market_close_at, "market_close_at")):
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError(f"{name} must be UTC-aware")

    entry_cutoff = market_close_at - timedelta(seconds=config.market_close_entry_cutoff_seconds)
    if state.status == PositionStatus.LIMIT_PENDING and as_of >= entry_cutoff:
        return "cancel_limit"
    if state.status == PositionStatus.OPEN and state.opened_at is not None:
        duration_cutoff = state.opened_at + timedelta(minutes=config.max_position_duration_minutes)
        if as_of >= min(duration_cutoff, entry_cutoff):
            return "request_close"
    return None


def _require_matching(
    state: PositionState,
    event: PositionEvent,
    expected_status: PositionStatus | set[PositionStatus],
) -> None:
    statuses = {expected_status} if isinstance(expected_status, PositionStatus) else expected_status
    if state.status not in statuses:
        raise ValueError(f"event {event.kind} is invalid while position state is {state.status}")
    if state.order_id != event.order_id:
        raise ValueError("event order_id does not match active lifecycle")
    if event.position_id is not None and state.position_id is not None and state.position_id != event.position_id:
        raise ValueError("event position_id does not match active lifecycle")


def _is_utc(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == UTC.utcoffset(value)
