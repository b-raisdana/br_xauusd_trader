from __future__ import annotations

from domain.xau_usd.enums import (
    XauDirection,
    XauExecutionEvent,
    XauExecutionStatus,
    XauOrderType,
)


def execution_transition(
    status: XauExecutionStatus,
    event_kind: XauExecutionEvent,
    order_type: XauOrderType,
) -> tuple[bool, XauExecutionStatus | None]:
    if status == XauExecutionStatus.SUBMITTED and event_kind == XauExecutionEvent.FILL:
        return True, XauExecutionStatus.FILLED

    if status == XauExecutionStatus.SUBMITTED and event_kind == XauExecutionEvent.REJECT:
        return True, XauExecutionStatus.REJECTED

    if status == XauExecutionStatus.FILLED and event_kind == XauExecutionEvent.CLOSE:
        return True, XauExecutionStatus.CLOSED

    if status == XauExecutionStatus.FILLED and event_kind in {
        XauExecutionEvent.MODIFY,
        XauExecutionEvent.MODIFY_REJECT,
    }:
        return True, XauExecutionStatus.FILLED

    if status == XauExecutionStatus.SUBMITTED and event_kind == XauExecutionEvent.CANCEL_REJECT:
        return True, XauExecutionStatus.SUBMITTED

    if (
        status == XauExecutionStatus.SUBMITTED
        and event_kind == XauExecutionEvent.CANCEL
        and order_type == XauOrderType.PENDING_STOP
    ):
        return True, XauExecutionStatus.CANCELLED

    return False, None


def protection_modification_valid(
    direction: XauDirection,
    entry: float,
    current_stop: float,
    proposed_stop: float,
    proposed_tp: float,
) -> bool:
    if direction == XauDirection.BUY:
        return proposed_stop >= current_stop and proposed_stop < proposed_tp and proposed_tp > entry

    return proposed_stop <= current_stop and proposed_tp < proposed_stop and proposed_tp < entry
