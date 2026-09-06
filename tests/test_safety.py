from datetime import date
from decimal import Decimal

import pytest

from xauusd.safety import (
    DailyRealizedLossGuard,
    evaluate_entry_safety,
    evaluate_portfolio_risk,
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
