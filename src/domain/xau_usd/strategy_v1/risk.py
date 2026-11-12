from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from math import isfinite
from zoneinfo import ZoneInfo

import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.strategy_v1 import RealizedTradeRows
from helper.importer import pt

from ._time_index import utc_times
from .config import StrategyV1Config

LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


def stop_loss_distance_usd(as_of: datetime, config: StrategyV1Config) -> float:
    if as_of.tzinfo is None or as_of.utcoffset() is None or as_of.utcoffset() != UTC.utcoffset(as_of):
        raise ValueError("as_of must be UTC-aware")
    london_time = as_of.astimezone(LONDON)
    new_york_time = as_of.astimezone(NEW_YORK)
    london_open = config.london_session_start_hour <= london_time.hour < config.london_session_end_hour
    new_york_open = config.new_york_session_start_hour <= new_york_time.hour < config.new_york_session_end_hour
    if london_open and new_york_open:
        return config.sl_distance_usd_inside_session_overlap
    return config.sl_distance_usd_outside_session_overlap


@dataclass(frozen=True)
class RiskSizingDecision:
    accepted: bool
    reason: str
    volume_lots: float
    estimated_risk_usd: float
    volume_budget_usd: float


def size_order_by_risk(
    *,
    equity_usd: float,
    importance: float,
    profit_at_sl_per_lot_usd: float,
    estimated_cost_per_lot_usd: float,
    volume_min_lots: float,
    volume_max_lots: float,
    volume_step_lots: float,
    free_margin_usd: float,
    margin_per_lot_usd: float,
    per_order_budget_usd: float,
    remaining_daily_budget_usd: float,
    remaining_consecutive_budget_usd: float,
    config: StrategyV1Config,
) -> RiskSizingDecision:
    values = (
        equity_usd,
        importance,
        profit_at_sl_per_lot_usd,
        estimated_cost_per_lot_usd,
        volume_min_lots,
        volume_max_lots,
        volume_step_lots,
        free_margin_usd,
        margin_per_lot_usd,
        per_order_budget_usd,
        remaining_daily_budget_usd,
        remaining_consecutive_budget_usd,
    )
    if any(not isfinite(value) for value in values):
        raise ValueError("risk sizing inputs must be finite")
    if equity_usd <= 0.0 or not 0.0 <= importance <= 1.0:
        raise ValueError("equity must be positive and importance must be between zero and one")
    if min(volume_min_lots, volume_max_lots, volume_step_lots, margin_per_lot_usd) <= 0.0:
        raise ValueError("broker volume and margin metadata must be positive")
    if volume_max_lots < volume_min_lots or free_margin_usd < 0.0:
        raise ValueError("broker volume range or free margin is invalid")
    if (
        min(
            estimated_cost_per_lot_usd,
            per_order_budget_usd,
            remaining_daily_budget_usd,
            remaining_consecutive_budget_usd,
        )
        < 0.0
    ):
        raise ValueError("cost and loss budgets must be non-negative")

    importance_factor = (
        1.0 / 3.0 if importance < 0.3 else 2.0 / 3.0 if importance < config.high_importance_threshold else 1.0
    )
    volume_budget = max(20.0, importance_factor * 0.01 * equity_usd)
    loss_per_lot = max(0.0, -profit_at_sl_per_lot_usd) + estimated_cost_per_lot_usd
    if loss_per_lot <= 0.0:
        raise ValueError("loss at stop and estimated costs must produce positive per-lot risk")

    raw_volume = volume_budget / loss_per_lot
    step_capped_volume = min(raw_volume, volume_max_lots, free_margin_usd / margin_per_lot_usd)
    volume_steps = (Decimal(str(step_capped_volume)) / Decimal(str(volume_step_lots))).to_integral_value(
        rounding=ROUND_FLOOR,
    )
    stepped_volume = float(volume_steps * Decimal(str(volume_step_lots)))
    risk = stepped_volume * loss_per_lot
    if stepped_volume < volume_min_lots:
        return RiskSizingDecision(False, "volume_below_broker_minimum", 0.0, 0.0, volume_budget)
    if risk > min(volume_budget, per_order_budget_usd, remaining_daily_budget_usd, remaining_consecutive_budget_usd):
        return RiskSizingDecision(False, "risk_budget_exceeded", stepped_volume, risk, volume_budget)
    return RiskSizingDecision(True, "accepted", stepped_volume, risk, volume_budget)


def per_order_riskable_money(equity_usd: float) -> float:
    if not isfinite(equity_usd) or equity_usd <= 0.0:
        raise ValueError("equity_usd must be finite and positive")
    return max(20.0, 0.01 * equity_usd)


def daily_max_loss(per_order_budget_usd: float) -> float:
    if not isfinite(per_order_budget_usd) or per_order_budget_usd <= 0.0:
        raise ValueError("per_order_budget_usd must be finite and positive")
    return max(60.0, 3.0 * per_order_budget_usd)


@pandera_validate
def remaining_consecutive_loss_budget(
    realized_trades: pt.DataFrame[RealizedTradeRows],
    per_order_budget_usd: float,
) -> float:
    if not isfinite(per_order_budget_usd) or per_order_budget_usd <= 0.0:
        raise ValueError("per_order_budget_usd must be finite and positive")
    utc_times(realized_trades.index)
    initial_budget = max(40.0, 2.0 * per_order_budget_usd)
    net_pnl = realized_trades["net_pnl_usd"]
    after_latest_win = net_pnl.gt(-1.0).iloc[::-1].cummax().iloc[::-1]
    current_streak_losses = net_pnl.where(~after_latest_win, 0.0).clip(upper=0.0).abs().sum()
    return max(0.0, initial_budget - float(current_streak_losses))


def estimated_worst_round_trip_cost_usd(
    volume_lots: float,
    *,
    point_size: float,
    tick_size: float,
    tick_value_usd: float,
    observed_spread_points: float,
    swap_rollovers: int,
    config: StrategyV1Config,
) -> float:
    values = (volume_lots, point_size, tick_size, tick_value_usd, observed_spread_points)
    if any(not isfinite(value) for value in values) or volume_lots <= 0.0:
        raise ValueError("volume and broker price/cost metadata must be finite; volume must be positive")
    if min(point_size, tick_size, tick_value_usd) <= 0.0 or observed_spread_points < 0.0:
        raise ValueError("broker price/cost metadata must be non-negative and price units positive")
    if swap_rollovers < 0:
        raise ValueError("swap_rollovers must be non-negative")

    usd_per_point_per_lot = point_size * tick_value_usd / tick_size
    spread_points = max(observed_spread_points, config.opo_xauusd_average_spread_points)
    spread_cost = spread_points * usd_per_point_per_lot * volume_lots
    slippage_cost = 2.0 * config.cost_stress_slippage_points_per_execution * usd_per_point_per_lot * volume_lots
    commission = 2.0 * config.opo_worst_commission_per_lot_per_side_usd * volume_lots
    swap = (
        config.opo_worst_negative_swap_points
        * config.cost_stress_triple_swap_multiplier
        * swap_rollovers
        * usd_per_point_per_lot
        * volume_lots
    )
    return spread_cost + slippage_cost + commission + swap


@pandera_validate
def remaining_daily_loss_budget(
    realized_trades: pt.DataFrame[RealizedTradeRows],
    as_of: datetime,
    per_order_budget_usd: float,
) -> float:
    if as_of.tzinfo is None or as_of.utcoffset() is None or as_of.utcoffset() != UTC.utcoffset(as_of):
        raise ValueError("as_of must be UTC-aware")
    if not isfinite(per_order_budget_usd) or per_order_budget_usd <= 0.0:
        raise ValueError("per_order_budget_usd must be finite and positive")

    start = pd.Timestamp(as_of - timedelta(hours=24))
    end = pd.Timestamp(as_of)
    trade_times = realized_trades.index
    in_window = (trade_times > start) & (trade_times <= end)
    recorded_losses = realized_trades.loc[in_window, "net_pnl_usd"].clip(upper=0.0).abs().sum()
    return max(0.0, daily_max_loss(per_order_budget_usd) - float(recorded_losses))
