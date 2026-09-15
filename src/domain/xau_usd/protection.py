from __future__ import annotations

from datetime import datetime, timedelta

from .constants import BASE_R_USD, DAILY_REALIZED_LOSS_FRACTION
from .enums import XauDirection, XauTpFailureAction
from .models import XauOperationalSafety


def evaluate_operational_safety(
    session_active: bool,
    same_day_restart: bool,
) -> XauOperationalSafety:
    locked = session_active or same_day_restart

    return XauOperationalSafety(
        locked=locked,
        block_entries=locked,
        cancel_pending=locked,
        cancel_pullback_cycles=locked,
        close_positions=locked,
    )


def profit_protection_stop(
    direction: XauDirection,
    entry: float,
    risk_free: float,
    current_bid: float,
    current_ask: float,
    current_stop: float,
) -> tuple[bool, float | None]:
    favorable = current_bid - entry if direction == XauDirection.BUY else entry - current_ask

    step = int(favorable // BASE_R_USD)

    if step < 1:
        return False, None

    proposed_stop = (
        risk_free + (step - 1) * BASE_R_USD if direction == XauDirection.BUY else risk_free - (step - 1) * BASE_R_USD
    )

    valid = proposed_stop > current_stop if direction == XauDirection.BUY else proposed_stop < current_stop

    return valid, proposed_stop


def daily_loss_locked(
    strategy_capital: float,
    net_realized_pnl: float,
    previously_locked: bool,
) -> bool:
    if previously_locked:
        return True

    if strategy_capital <= 0.0 or strategy_capital >= 300.0:
        return False

    return net_realized_pnl <= (-strategy_capital * DAILY_REALIZED_LOSS_FRACTION)


def session_end_active(
    broker_now: datetime,
    broker_session_end: datetime,
) -> bool:
    return broker_now >= broker_session_end - timedelta(minutes=5)


def pullback_tp_failure_action(
    direction: XauDirection,
    extended: bool,
    strict_valid: bool,
    initial_tp: float,
    current_bid: float,
    current_ask: float,
) -> XauTpFailureAction:
    if not extended or strict_valid:
        return XauTpFailureAction.NONE

    crossed = current_bid >= initial_tp if direction == XauDirection.BUY else current_ask <= initial_tp

    return XauTpFailureAction.MARKET_CLOSE if crossed else XauTpFailureAction.RESTORE


def restart_same_day_locked(
    broker_day: str,
    persisted_last_activation_day: str,
) -> bool:
    return bool(broker_day and broker_day == persisted_last_activation_day)
