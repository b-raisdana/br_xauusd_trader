from datetime import UTC, datetime

import pandas as pd
import pandera
import pytest

from domain.xau_usd.strategy_v1 import (
    daily_max_loss,
    estimated_worst_round_trip_cost_usd,
    per_order_riskable_money,
    remaining_consecutive_loss_budget,
    remaining_daily_loss_budget,
    size_order_by_risk,
)
from domain.xau_usd.strategy_v1.config import StrategyV1Config


def test_risk_budgets_follow_documented_equity_floors():
    assert per_order_riskable_money(400.0) == 20.0
    assert per_order_riskable_money(6000.0) == 60.0
    assert daily_max_loss(20.0) == 60.0
    assert daily_max_loss(60.0) == 180.0


def test_daily_budget_sums_net_losses_in_open_closed_24_hour_window_without_offsetting_wins():
    as_of = datetime(2026, 7, 30, 12, tzinfo=UTC)
    trades = pd.DataFrame(
        {"net_pnl_usd": [-10.0, 50.0, -15.0, -5.0]},
        index=pd.DatetimeIndex(
            ["2026-07-29 12:00Z", "2026-07-29 13:00Z", "2026-07-30 11:00Z", "2026-07-30 12:00Z"],
            name="date",
        ),
    )

    assert remaining_daily_loss_budget(trades, as_of, 20.0) == 40.0


def test_daily_budget_rejects_missing_pnl_column_and_unparseable_pnl():
    index = pd.DatetimeIndex(["2026-07-30T11:00Z"], name="date")
    with pytest.raises(pandera.errors.SchemaErrors):
        remaining_daily_loss_budget(pd.DataFrame(index=index), datetime(2026, 7, 30, 12, tzinfo=UTC), 20.0)
    with pytest.raises(pandera.errors.SchemaErrors):
        remaining_daily_loss_budget(
            pd.DataFrame({"net_pnl_usd": ["unknown"]}, index=index),
            datetime(2026, 7, 30, 12, tzinfo=UTC),
            20.0,
        )


def test_consecutive_loss_budget_tracks_loss_total_and_resets_after_pnl_above_minus_one():
    trade_times = pd.date_range("2026-07-29T10:00Z", periods=5, freq="1h", name="date")
    losses = pd.DataFrame({"net_pnl_usd": [-8.0, -10.0]}, index=trade_times[:2])
    reset = pd.DataFrame({"net_pnl_usd": [-8.0, -10.0, -0.5, -12.0]}, index=trade_times[:4])
    exhausted = pd.DataFrame({"net_pnl_usd": [-8.0, -10.0, 2.0, -12.0, -35.0]}, index=trade_times)

    assert remaining_consecutive_loss_budget(losses, 20.0) == 22.0
    assert remaining_consecutive_loss_budget(reset, 20.0) == 28.0
    assert remaining_consecutive_loss_budget(exhausted, 20.0) == 0.0


def test_cost_estimate_applies_highest_published_opo_commission_swap_spread_and_slippage_stress():
    cost = estimated_worst_round_trip_cost_usd(
        1.0,
        point_size=0.01,
        tick_size=0.01,
        tick_value_usd=1.0,
        observed_spread_points=30.0,
        swap_rollovers=1,
        config=StrategyV1Config(),
    )

    assert cost == pytest.approx(233.632)


def test_cost_estimate_uses_opo_average_spread_floor_and_no_swap_when_not_held_over_rollover():
    cost = estimated_worst_round_trip_cost_usd(
        0.5,
        point_size=0.01,
        tick_size=0.01,
        tick_value_usd=1.0,
        observed_spread_points=10.0,
        swap_rollovers=0,
        config=StrategyV1Config(),
    )

    assert cost == pytest.approx(36.0)


def test_size_order_rounds_down_and_rejects_risk_above_remaining_budget():
    inputs = {
        "equity_usd": 1000.0,
        "importance": 0.9,
        "profit_at_sl_per_lot_usd": -600.0,
        "estimated_cost_per_lot_usd": 20.0,
        "volume_min_lots": 0.01,
        "volume_max_lots": 100.0,
        "volume_step_lots": 0.01,
        "free_margin_usd": 10000.0,
        "margin_per_lot_usd": 100.0,
        "per_order_budget_usd": 20.0,
        "remaining_daily_budget_usd": 18.5,
        "remaining_consecutive_budget_usd": 40.0,
        "config": StrategyV1Config(),
    }

    decision = size_order_by_risk(**inputs)

    assert not decision.accepted
    assert decision.reason == "risk_budget_exceeded"
    assert decision.volume_lots == pytest.approx(0.03)
    assert decision.estimated_risk_usd == pytest.approx(18.6)


def test_size_order_observes_importance_floor_broker_minimum_and_margin_limit():
    inputs = {
        "equity_usd": 6000.0,
        "importance": 0.2,
        "profit_at_sl_per_lot_usd": -600.0,
        "estimated_cost_per_lot_usd": 0.0,
        "volume_min_lots": 0.01,
        "volume_max_lots": 10.0,
        "volume_step_lots": 0.01,
        "free_margin_usd": 100.0,
        "margin_per_lot_usd": 100000.0,
        "per_order_budget_usd": 60.0,
        "remaining_daily_budget_usd": 100.0,
        "remaining_consecutive_budget_usd": 100.0,
        "config": StrategyV1Config(),
    }

    decision = size_order_by_risk(**inputs)

    assert not decision.accepted
    assert decision.reason == "volume_below_broker_minimum"
    assert decision.volume_lots == 0.0
    assert decision.volume_budget_usd == 20.0
