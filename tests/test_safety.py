from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from xauusd.safety import (
    DailyRealizedLossGuard,
    RestartFailClosedGuard,
    evaluate_entry_safety,
    evaluate_portfolio_risk,
    session_end_actions,
)

DAY = date(2026, 9, 6)


def test_daily_loss_guard_latches_at_twenty_percent_and_resets_next_day() -> None:
    guard = DailyRealizedLossGuard("200")
    guard.begin_day(DAY)
    assert guard.threshold_cash == Decimal("40.00")
    assert not guard.update("-39.99").locked
    locked = guard.update("-40")
    assert locked.block_new_entries
    assert locked.cancel_pending_orders
    assert not locked.force_close_positions
    assert guard.update("10").locked

    guard.begin_day(date(2026, 9, 7))
    assert not guard.update("0").locked


def test_daily_realized_guard_does_not_apply_at_300_profile() -> None:
    guard = DailyRealizedLossGuard("300")
    guard.begin_day(DAY)
    assert guard.threshold_cash is None
    assert not guard.update("-300").locked


def test_gross15_sums_all_native_cash_risk_components_inclusively() -> None:
    snapshot = evaluate_portfolio_risk(
        strategy_capital="200",
        realized_gross_loss="5",
        open_position_risk="10",
        pending_order_risk="7",
        proposed_order_risk="8",
    )
    assert snapshot.budget_cash == Decimal("30.00")
    assert snapshot.used_before_proposed == 22
    assert snapshot.remaining_before_proposed == 8
    assert snapshot.used_with_proposed == 30
    assert snapshot.allows_proposed

    blocked = evaluate_portfolio_risk(
        strategy_capital="200",
        realized_gross_loss="5",
        open_position_risk="10",
        pending_order_risk="7",
        proposed_order_risk="8.01",
    )
    assert not blocked.allows_proposed


def test_gross_loss_is_not_offset_by_realized_profit() -> None:
    snapshot = evaluate_portfolio_risk(
        strategy_capital="300",
        realized_gross_loss="30",
        open_position_risk="10",
        pending_order_risk="5",
        proposed_order_risk="0.01",
    )
    assert snapshot.budget_cash == Decimal("45.00")
    assert not snapshot.allows_proposed


def test_combined_entry_gate_reports_daily_before_portfolio() -> None:
    guard = DailyRealizedLossGuard("200")
    guard.begin_day(DAY)
    daily = guard.update("-40")
    portfolio = evaluate_portfolio_risk(
        strategy_capital="200",
        realized_gross_loss="30",
        open_position_risk="0",
        pending_order_risk="0",
        proposed_order_risk="1",
    )
    decision = evaluate_entry_safety(daily_guard=daily, portfolio=portfolio)
    assert not decision.allowed
    assert decision.rejection_reason == "daily_realized_loss_guard"

    fresh = DailyRealizedLossGuard("200")
    fresh.begin_day(DAY)
    decision = evaluate_entry_safety(
        daily_guard=fresh.update("0"),
        portfolio=portfolio,
    )
    assert not decision.allowed
    assert decision.rejection_reason == "gross_portfolio_risk_budget"


def test_negative_native_risk_component_fails_closed() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        evaluate_portfolio_risk(
            strategy_capital="200",
            realized_gross_loss="0",
            open_position_risk="-1",
            pending_order_risk="0",
            proposed_order_risk="0",
        )


def test_session_actions_start_exactly_five_minutes_before_broker_end() -> None:
    session_end = datetime(2026, 9, 6, 21, 0, tzinfo=UTC)
    before = session_end_actions(
        broker_now=datetime(2026, 9, 6, 20, 54, 59, tzinfo=UTC),
        broker_session_end=session_end,
    )
    assert not before.locked

    boundary = session_end_actions(
        broker_now=datetime(2026, 9, 6, 20, 55, tzinfo=UTC),
        broker_session_end=session_end,
    )
    assert boundary.block_new_entries
    assert boundary.cancel_pending_orders
    assert boundary.cancel_pullback_cycles
    assert boundary.close_ea_positions


def test_session_time_basis_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="timezone basis"):
        session_end_actions(
            broker_now=datetime(2026, 9, 6, 20, 55),
            broker_session_end=datetime(2026, 9, 6, 21, 0, tzinfo=UTC),
        )


def test_same_day_restart_flattens_and_locks_until_next_broker_day() -> None:
    guard = RestartFailClosedGuard()
    state = guard.attach(broker_day=DAY, persisted_last_activation_day=DAY)
    assert state.block_new_entries
    assert state.cancel_pending_orders
    assert state.cancel_pullback_cycles
    assert state.close_ea_positions
    assert guard.activation_day_to_persist == DAY
    assert guard.begin_day(DAY).locked

    next_day = date(2026, 9, 7)
    assert not guard.begin_day(next_day).locked
    assert guard.activation_day_to_persist == next_day


def test_first_attach_or_attach_after_prior_day_is_not_restart_locked() -> None:
    guard = RestartFailClosedGuard()
    assert not guard.attach(broker_day=DAY, persisted_last_activation_day=None).locked
    assert not guard.attach(
        broker_day=DAY,
        persisted_last_activation_day=date(2026, 9, 5),
    ).locked
