from datetime import datetime
from typing import Any

from domain.xau_usd.enums import XauDirection, XauExecutionStatus, XauSignalFamily
from domain.xau_usd.models import XauMarketCoordinator

from .domain.replay import ReplayOrder
from .replay import ExecutionReplay


def timestamp(value: datetime | None) -> int:
    return int(value.timestamp()) if value else 0


def trade_type(order: ReplayOrder) -> str:
    if order.native_trade_type is not None:
        return order.native_trade_type
    return {XauSignalFamily.BREAKOUT: "B", XauSignalFamily.REVERSAL: "R", XauSignalFamily.PULLBACK: "P"}[
        order.candidate.family
    ]


def request_trace(order: ReplayOrder) -> dict[str, Any]:
    candidate = order.candidate
    return {
        "active": order.request_active,
        "comment": order.comment,
        "requested_price": candidate.entry_price,
        "sl": order.initial_sl,
        "tp": order.take_profit,
        "r0": order.r0,
        "target_zone_id": order.target_zone_id,
        "parent_breakout_id": candidate.parent_breakout_id,
        "reversal_ordinal": order.reversal_ordinal,
    }


def position_trace(order: ReplayOrder) -> dict[str, Any]:
    return {
        "active": order.status == XauExecutionStatus.FILLED,
        "position_id": order.native_position_id if order.native_position_id is not None else order.position_id,
        "position_ticket": order.native_position_ticket if order.native_position_id is not None else order.position_id,
        "day_key": order.broker_day.replace("-", "."),
        "zone_id": order.candidate.zone_id,
        "trade_type": trade_type(order),
        "buy": order.direction == XauDirection.BUY,
        "risk_anchor_entry": order.candidate.entry_price,
        "actual_fill": order.fill_price,
        "initial_sl": order.initial_sl,
        "tp": order.take_profit,
        "r0": order.r0,
        "r_stage": order.r_stage,
        "desired_sl": order.desired_sl,
        "sl_retry_logged": order.sl_retry_logged,
        "target_zone_id": order.target_zone_id,
        "parent_breakout_id": order.candidate.parent_breakout_id,
        "stacked_pullback": order.stacked_pullback,
        "reversal_ordinal": order.reversal_ordinal,
        "session_close_requested": order.session_close_requested,
        "session_close_reason": order.session_close_reason,
        "last_carry_audit_key": order.last_carry_audit_key,
    }


def shared_trace(state: XauMarketCoordinator, execution: ExecutionReplay | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "g_day_key": state.broker_day.replace("-", "."),
        "g_day_valid": bool(state.zones),
        "g_breakout_seq": state.breakout_sequence,
        "g_zones": [
            {
                "day_key": state.broker_day.replace("-", "."),
                "id": z.zone.id,
                "low": z.zone.low,
                "high": z.zone.high,
                "priority": "high" if z.zone.priority else "normal",
                "engaged_buy": z.buy_engaged,
                "engaged_sell": z.sell_engaged,
                "reversal_usage": z.reversal_usage,
                "reversal_fill_count": z.reversal_fill_count,
                "pullback_fill_count": z.pullback_fills,
                "last_reversal_buy_signal_bar": timestamp(z.last_reversal_buy_signal_bar),
                "last_reversal_sell_signal_bar": timestamp(z.last_reversal_sell_signal_bar),
            }
            for z in state.zones
        ],
        "g_cycles": [
            {
                "active": w.active,
                "buy": w.direction == XauDirection.BUY,
                "day_key": w.broker_day.replace("-", "."),
                "zone_id": w.zone.id,
                "zone_low": w.zone.low,
                "zone_high": w.zone.high,
                "breakout_bar_time": timestamp(w.breakout_bar_time),
                "valid_bar_no": w.bar_offset,
                "penetration_latched": w.penetration_latched,
                "order_ticket": (
                    execution.orders[w.order_ticket].native_order_ticket or w.order_ticket
                    if execution and w.order_ticket in execution.orders
                    else w.order_ticket or 0
                ),
                "waiting_logged": w.waiting_logged,
                "risk_waiting_logged": w.risk_waiting_logged,
                "parent_breakout_id": w.parent_breakout_id,
            }
            for w in state.pullbacks
        ],
    }
    if execution:
        result.update(
            {
                "g_initial_deposit": execution.config.initial_balance,
                "g_daily_realized_net": execution.net_realized,
                "g_daily_realized_gross_loss": execution.gross_loss,
                "g_daily_stop": execution.daily_locked,
                "g_daily_would_trigger_logged": execution.daily_would_trigger_logged,
                "g_session_preclose_active": execution.session_preclose,
                "g_restart_lock": execution.restart_locked,
                "g_last_new_order_bar": timestamp(datetime.fromisoformat(state.attempted_bars[-1]))
                if state.attempted_bars
                else 0,
                "g_session_cutoff_key": execution.session_cutoff_key,
                "g_session_active_window_key": execution.session_active_window_key,
                "g_session_active_from": timestamp(execution.session_active_from),
                "g_session_active_to": timestamp(execution.session_active_to),
                "g_requests": [request_trace(o) for o in execution.requests],
                "g_positions": [position_trace(o) for o in execution.orders.values() if o.fill_time is not None],
            }
        )
    return result


def first_difference(expected: Any, actual: Any, path: str = "$") -> str | None:
    """Strict comparison of normalized native/Python snapshots; no tolerance or ignored keys."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        if expected.keys() != actual.keys():
            missing = sorted(expected.keys() - actual.keys())
            extra = sorted(actual.keys() - expected.keys())
            return f"{path}: missing={missing}, extra={extra}"
        for key in expected:
            if difference := first_difference(expected[key], actual[key], f"{path}.{key}"):
                return difference
        return None
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return f"{path}: length {len(actual)} != {len(expected)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            if difference := first_difference(left, right, f"{path}[{index}]"):
                return difference
        return None
    return None if type(expected) is type(actual) and expected == actual else f"{path}: {actual!r} != {expected!r}"
