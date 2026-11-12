from datetime import UTC, datetime
from typing import Literal

import pytest

from domain.xau_usd.strategy_v1 import (
    PositionEvent,
    PositionState,
    PositionStatus,
    apply_position_event,
    position_deadline_action,
    request_close_retry,
    request_limit_cancellation,
)
from domain.xau_usd.strategy_v1.config import StrategyV1Config


def _event(
    event_id: str,
    kind: Literal[
        "limit_submitted",
        "limit_canceled",
        "filled",
        "close_requested",
        "close_rejected",
        "close_unknown",
        "closed",
    ],
    **fields: str | float | None,
) -> PositionEvent:
    return PositionEvent(
        event_id=event_id,
        kind=kind,
        event_time=datetime(2026, 7, 29, 10, tzinfo=UTC),
        **fields,
    )


def test_position_lifecycle_keeps_attached_protection_and_computes_net_realized_pnl():
    pending = apply_position_event(
        PositionState(),
        _event(
            "limit-1",
            "limit_submitted",
            order_id="order-1",
            direction="buy",
            entry_reference=4000.0,
            stop_loss=3994.0,
            take_profit=4030.0,
        ),
    ).state
    opened = apply_position_event(
        pending,
        _event(
            "fill-1",
            "filled",
            order_id="order-1",
            position_id="position-1",
            fill_price=4000.0,
            volume_lots=0.03,
        ),
    ).state

    assert opened.status == PositionStatus.OPEN
    assert opened.stop_loss == 3994.0
    assert opened.take_profit == 4030.0

    close_request = apply_position_event(
        opened,
        _event("close-req-1", "close_requested", order_id="order-1", position_id="position-1", close_reason="reverse"),
    )
    assert close_request.action == "request_close"
    assert close_request.state.status == PositionStatus.CLOSE_REQUESTED

    closed = apply_position_event(
        close_request.state,
        _event(
            "close-ok-1",
            "closed",
            order_id="order-1",
            position_id="position-1",
            profit_before_charges_usd=30.0,
            commission_cost_usd=6.0,
            swap_pnl_usd=-2.0,
            fee_cost_usd=1.0,
            spread_slippage_cost_usd=3.0,
        ),
    )

    assert closed.state.status == PositionStatus.FLAT
    assert closed.realized_net_pnl_usd == 18.0
    assert closed.state.last_realized_net_pnl_usd == 18.0


def test_close_rejected_or_unknown_stays_single_position_and_retries_on_new_event():
    state = PositionState(
        status=PositionStatus.OPEN,
        order_id="order-1",
        position_id="position-1",
        direction="sell",
        entry_reference=4000.0,
        fill_price=4000.0,
        volume_lots=0.01,
        stop_loss=4006.0,
        take_profit=3970.0,
        opened_at=datetime(2026, 7, 29, 10, tzinfo=UTC),
    )
    requested = apply_position_event(
        state,
        _event("req", "close_requested", order_id="order-1", position_id="position-1"),
    ).state
    retried = apply_position_event(
        requested,
        _event("unknown-1", "close_unknown", order_id="order-1", position_id="position-1"),
    )

    assert retried.action == "retry_close"
    assert retried.state.status == PositionStatus.CLOSE_RETRY_REQUIRED
    assert retried.state.close_retry_count == 1
    assert request_close_retry(retried.state).action == "retry_close"
    with pytest.raises(ValueError, match="second order"):
        apply_position_event(
            retried.state,
            _event(
                "limit-2",
                "limit_submitted",
                order_id="order-2",
                direction="buy",
                entry_reference=3990.0,
                stop_loss=3984.0,
                take_profit=4020.0,
            ),
        )


def test_limit_cutoff_requests_cancel_and_waits_for_confirmation_before_flattening():
    pending = apply_position_event(
        PositionState(),
        _event(
            "limit-1",
            "limit_submitted",
            order_id="order-1",
            direction="buy",
            entry_reference=4000.0,
            stop_loss=3994.0,
            take_profit=4030.0,
        ),
    ).state

    cancel = request_limit_cancellation(pending)
    assert cancel.action == "cancel_limit"
    assert cancel.state.status == PositionStatus.LIMIT_PENDING

    canceled = apply_position_event(
        pending,
        _event("cancel-confirmed", "limit_canceled", order_id="order-1"),
    )
    assert canceled.state.status == PositionStatus.FLAT


def test_position_deadline_uses_earlier_of_six_hours_or_market_close_cutoff():
    state = PositionState(
        status=PositionStatus.OPEN,
        order_id="order-1",
        position_id="position-1",
        direction="buy",
        entry_reference=4000.0,
        fill_price=4000.0,
        volume_lots=0.01,
        stop_loss=3994.0,
        take_profit=4030.0,
        opened_at=datetime(2026, 7, 29, 10, tzinfo=UTC),
    )
    market_close_at = datetime(2026, 7, 29, 20, tzinfo=UTC)

    assert (
        position_deadline_action(
            state,
            datetime(2026, 7, 29, 15, 59, 59, tzinfo=UTC),
            market_close_at,
            StrategyV1Config(),
        )
        is None
    )
    assert (
        position_deadline_action(
            state,
            datetime(2026, 7, 29, 16, tzinfo=UTC),
            market_close_at,
            StrategyV1Config(),
        )
        == "request_close"
    )
    assert (
        position_deadline_action(
            state,
            datetime(2026, 7, 29, 19, 59, 50, tzinfo=UTC),
            market_close_at,
            StrategyV1Config(),
        )
        == "request_close"
    )
