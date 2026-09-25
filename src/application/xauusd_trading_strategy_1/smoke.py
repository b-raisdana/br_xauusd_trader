from __future__ import annotations

from application.xauusd_trading_strategy_1.domain.entry import initial_stop, initial_target, portfolio_risk_allows
from application.xauusd_trading_strategy_1.domain.execution import execution_transition, protection_modification_valid
from application.xauusd_trading_strategy_1.domain.protection import (
    daily_loss_locked,
    profit_protection_stop,
    pullback_tp_failure_action,
    session_end_active,
)
from application.xauusd_trading_strategy_1.domain.zone import (
    pre_zone_crossed,
    pre_zone_trigger_price,
    pullback_penetrated,
    pullback_usage_allowed,
    pullback_window_active,
    strict_pullback_trend,
)
from config.core_vectors import CoreVectors, core_vectors
from domain.xau_usd.enums import XauDirection, XauExecutionEvent, XauExecutionStatus, XauOrderType, XauTrend
from domain.xau_usd.models import XauZone
from domain.xau_usd.zone import (
    breakout_valid,
    build_merged_zones,
    count_directional_crosses,
    reversal_directional_touch,
    update_trend,
)

from .lifecycle import SmokeResult


def nearly_equal(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return abs(left - right) <= tolerance


def run_core_vector_smoke(vectors: CoreVectors = core_vectors) -> SmokeResult:
    try:
        breakout_zone = XauZone(id="2026-09-06:R1", low=vectors.vec_breakout_low, high=vectors.vec_breakout_high)
        if not breakout_valid(
            breakout_zone,
            XauDirection.BUY,
            XauTrend.UP,
            vectors.vec_breakout_close,
            True,
        ):
            return SmokeResult("core_vectors", False, "breakout")
        if not reversal_directional_touch(
            breakout_zone,
            XauDirection.SELL,
            XauTrend.UP,
            vectors.vec_reversal_previous,
            vectors.vec_reversal_current,
            False,
        ):
            return SmokeResult("core_vectors", False, "reversal")
        if (
            update_trend(
                XauTrend.NONE,
                1,
                vectors.vec_trend_reference_high,
                vectors.vec_trend_reference_low,
                vectors.vec_trend_bid,
            )
            != XauTrend.UP
        ):
            return SmokeResult("core_vectors", False, "trend")

        pullback_zone = XauZone(id="2026-09-06:R1", low=vectors.vec_pullback_low, high=vectors.vec_pullback_high)
        penetrated, pullback_entry = pullback_penetrated(
            pullback_zone,
            XauDirection.BUY,
            vectors.vec_pullback_bid,
        )
        if not penetrated or not nearly_equal(pullback_entry, vectors.vec_pullback_high):
            return SmokeResult("core_vectors", False, "pullback penetration")
        if not strict_pullback_trend(
            XauDirection.BUY,
            [1, 1],
            vectors.vec_strict_current_open,
            vectors.vec_strict_current_bid,
            vectors.vec_strict_current_ask,
        ):
            return SmokeResult("core_vectors", False, "strict pullback")

        trigger_zone = XauZone(
            id="2026-09-06:R2",
            low=vectors.vec_trigger_target_low,
            high=vectors.vec_trigger_target_high,
        )
        if not nearly_equal(
            pre_zone_trigger_price(XauDirection.BUY, trigger_zone), vectors.vec_trigger_target_low - 1.0
        ):
            return SmokeResult("core_vectors", False, "trigger price")
        if not pre_zone_crossed(
            XauDirection.BUY,
            trigger_zone,
            vectors.vec_trigger_previous,
            vectors.vec_trigger_current,
        ):
            return SmokeResult("core_vectors", False, "trigger cross")

        risk_zones = [
            XauZone(
                id=f"R{index}",
                low=getattr(vectors, f"vec_risk_zone_{index}_low"),
                high=getattr(vectors, f"vec_risk_zone_{index}_high"),
            )
            for index in range(1, 5)
        ]
        stop_found, stop_loss, stop_zone = initial_stop(XauDirection.BUY, vectors.vec_risk_entry, risk_zones)
        target_found, take_profit, target_zone = initial_target(XauDirection.BUY, vectors.vec_risk_entry, risk_zones)
        if (
            not stop_found
            or not target_found
            or not nearly_equal(stop_loss or 0.0, vectors.vec_risk_expected_sl)
            or not nearly_equal(take_profit or 0.0, vectors.vec_risk_expected_tp)
            or stop_zone != "R2"
            or target_zone != "R4"
        ):
            return SmokeResult("core_vectors", False, "initial risk")
        if not portfolio_risk_allows(
            vectors.vec_portfolio_capital,
            vectors.vec_portfolio_realized,
            vectors.vec_portfolio_open,
            vectors.vec_portfolio_pending,
            vectors.vec_portfolio_proposed,
        ):
            return SmokeResult("core_vectors", False, "portfolio risk")

        protection_valid, protected_stop = profit_protection_stop(
            XauDirection.BUY,
            vectors.vec_protection_entry,
            vectors.vec_protection_rf,
            vectors.vec_protection_bid,
            vectors.vec_protection_ask,
            vectors.vec_protection_current_sl,
        )
        if not protection_valid or not nearly_equal(protected_stop or 0.0, 118.25):
            return SmokeResult("core_vectors", False, "profit protection")
        if not daily_loss_locked(vectors.vec_daily_capital, vectors.vec_daily_net_pnl, False):
            return SmokeResult("core_vectors", False, "daily loss")
        if not session_end_active(vectors.vec_session_now, vectors.vec_session_end):
            return SmokeResult("core_vectors", False, "session end")

        merged = build_merged_zones(
            [
                XauZone(
                    id="",
                    low=vectors.vec_merge_zone_1_low,
                    high=vectors.vec_merge_zone_1_high,
                    priority=vectors.vec_merge_zone_1_priority,
                ),
                XauZone(
                    id="",
                    low=vectors.vec_merge_zone_2_low,
                    high=vectors.vec_merge_zone_2_high,
                    priority=vectors.vec_merge_zone_2_priority,
                ),
                XauZone(
                    id="",
                    low=vectors.vec_merge_zone_3_low,
                    high=vectors.vec_merge_zone_3_high,
                    priority=vectors.vec_merge_zone_3_priority,
                ),
                XauZone(
                    id="",
                    low=vectors.vec_merge_zone_4_low,
                    high=vectors.vec_merge_zone_4_high,
                    priority=vectors.vec_merge_zone_4_priority,
                ),
            ],
            vectors.vec_restart_day,
        )
        if (
            len(merged) != vectors.vec_merge_expected_count
            or merged[0].id != "2026-09-06:R1"
            or merged[1].id != "2026-09-06:R2"
        ):
            return SmokeResult("core_vectors", False, "zone merge")

        gap_zones = [
            XauZone(id="", low=vectors.vec_gap_zone_1_low, high=vectors.vec_gap_zone_1_high),
            XauZone(id="", low=vectors.vec_gap_zone_2_low, high=vectors.vec_gap_zone_2_high),
        ]
        if count_directional_crosses(gap_zones, vectors.vec_gap_previous, vectors.vec_gap_current) != 2:
            return SmokeResult("core_vectors", False, "gap count")
        if not pullback_window_active(vectors.vec_pullback_bar_offset) or not pullback_usage_allowed(
            1, vectors.vec_pullback_daily_fills
        ):
            return SmokeResult("core_vectors", False, "pullback usage")
        if (
            pullback_tp_failure_action(
                XauDirection.BUY,
                True,
                False,
                vectors.vec_tp_initial,
                vectors.vec_tp_current_bid,
                vectors.vec_tp_current_ask,
            ).name
            != "RESTORE"
        ):
            return SmokeResult("core_vectors", False, "TP failure")

        allowed, next_status = execution_transition(
            XauExecutionStatus(vectors.vec_execution_status),
            XauExecutionEvent(vectors.vec_execution_event),
            XauOrderType(vectors.vec_execution_order_type),
        )
        if not allowed or next_status != XauExecutionStatus(vectors.vec_execution_expected_status):
            return SmokeResult("core_vectors", False, "execution transition")

        causal_trend = update_trend(
            XauTrend.NONE,
            1,
            vectors.vec_causal_reference_high,
            vectors.vec_causal_reference_low,
            vectors.vec_causal_bid,
        )
        if causal_trend != XauTrend.UP:
            return SmokeResult("core_vectors", False, "causal trend")
        if not protection_modification_valid(
            XauDirection(vectors.vec_modification_direction),
            vectors.vec_modification_entry,
            vectors.vec_modification_current_sl,
            vectors.vec_modification_proposed_sl,
            vectors.vec_modification_proposed_tp,
        ):
            return SmokeResult("core_vectors", False, "modification")
        return SmokeResult("core_vectors", True)
    except Exception as exc:
        return SmokeResult("core_vectors", False, str(exc))
