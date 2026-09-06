"""Daily realized-loss and gross portfolio-risk safety contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from xauusd.zones import price

DAILY_REALIZED_LOSS_FRACTION = Decimal("0.20")
GROSS_DAILY_RISK_FRACTION = Decimal("0.15")
SESSION_PRE_CLOSE = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class DailyGuardState:
    locked: bool
    block_new_entries: bool
    cancel_pending_orders: bool
    force_close_positions: bool


class DailyRealizedLossGuard:
    """Latch the sub-300 USD daily net-realized loss gate until next day."""

    def __init__(self, strategy_capital: Decimal | str | int | float) -> None:
        self.strategy_capital = price(strategy_capital)
        if self.strategy_capital <= 0:
            raise ValueError("Strategy capital must be positive")
        self._broker_day: date | None = None
        self._locked = False

    @property
    def threshold_cash(self) -> Decimal | None:
        if self.strategy_capital >= Decimal("300"):
            return None
        return self.strategy_capital * DAILY_REALIZED_LOSS_FRACTION

    def begin_day(self, broker_day: date) -> None:
        if broker_day != self._broker_day:
            self._broker_day = broker_day
            self._locked = False

    def update(self, net_realized_pnl: Decimal | str | int | float) -> DailyGuardState:
        if self._broker_day is None:
            raise RuntimeError("Daily guard day has not been initialized")
        threshold = self.threshold_cash
        if threshold is not None and price(net_realized_pnl) <= -threshold:
            self._locked = True
        return DailyGuardState(
            locked=self._locked,
            block_new_entries=self._locked,
            cancel_pending_orders=self._locked,
            force_close_positions=False,
        )


@dataclass(frozen=True, slots=True)
class PortfolioRiskSnapshot:
    budget_cash: Decimal
    realized_gross_loss: Decimal
    open_position_risk: Decimal
    pending_order_risk: Decimal
    proposed_order_risk: Decimal

    @property
    def used_before_proposed(self) -> Decimal:
        return self.realized_gross_loss + self.open_position_risk + self.pending_order_risk

    @property
    def used_with_proposed(self) -> Decimal:
        return self.used_before_proposed + self.proposed_order_risk

    @property
    def remaining_before_proposed(self) -> Decimal:
        return self.budget_cash - self.used_before_proposed

    @property
    def allows_proposed(self) -> bool:
        return self.used_with_proposed <= self.budget_cash


def evaluate_portfolio_risk(
    *,
    strategy_capital: Decimal | str | int | float,
    realized_gross_loss: Decimal | str | int | float,
    open_position_risk: Decimal | str | int | float,
    pending_order_risk: Decimal | str | int | float,
    proposed_order_risk: Decimal | str | int | float,
) -> PortfolioRiskSnapshot:
    capital = price(strategy_capital)
    if capital <= 0:
        raise ValueError("Strategy capital must be positive")
    components = tuple(
        price(value)
        for value in (
            realized_gross_loss,
            open_position_risk,
            pending_order_risk,
            proposed_order_risk,
        )
    )
    if any(component < 0 for component in components):
        raise ValueError("Risk components must be non-negative native cash values")
    return PortfolioRiskSnapshot(
        budget_cash=capital * GROSS_DAILY_RISK_FRACTION,
        realized_gross_loss=components[0],
        open_position_risk=components[1],
        pending_order_risk=components[2],
        proposed_order_risk=components[3],
    )


@dataclass(frozen=True, slots=True)
class EntrySafetyDecision:
    allowed: bool
    rejection_reason: str | None
    daily_guard: DailyGuardState
    portfolio: PortfolioRiskSnapshot


def evaluate_entry_safety(
    *, daily_guard: DailyGuardState, portfolio: PortfolioRiskSnapshot
) -> EntrySafetyDecision:
    if daily_guard.block_new_entries:
        return EntrySafetyDecision(False, "daily_realized_loss_guard", daily_guard, portfolio)
    if not portfolio.allows_proposed:
        return EntrySafetyDecision(False, "gross_portfolio_risk_budget", daily_guard, portfolio)
    return EntrySafetyDecision(True, None, daily_guard, portfolio)


@dataclass(frozen=True, slots=True)
class OperationalSafetyActions:
    locked: bool
    block_new_entries: bool
    cancel_pending_orders: bool
    cancel_pullback_cycles: bool
    close_ea_positions: bool
    reason: str | None = None


def session_end_actions(
    *, broker_now: datetime, broker_session_end: datetime
) -> OperationalSafetyActions:
    """Evaluate the adapter-supplied Broker session boundary without local hours."""
    now_is_aware = broker_now.utcoffset() is not None
    end_is_aware = broker_session_end.utcoffset() is not None
    if now_is_aware != end_is_aware:
        raise ValueError("Broker time and session end must use the same timezone basis")
    active = broker_now >= broker_session_end - SESSION_PRE_CLOSE
    return OperationalSafetyActions(
        locked=active,
        block_new_entries=active,
        cancel_pending_orders=active,
        cancel_pullback_cycles=active,
        close_ea_positions=active,
        reason="session_end_flatten" if active else None,
    )


class RestartFailClosedGuard:
    """Lock a same-Broker-Day restart and release only on a later Broker Day."""

    def __init__(self) -> None:
        self._broker_day: date | None = None
        self._locked = False

    def attach(
        self, *, broker_day: date, persisted_last_activation_day: date | None
    ) -> OperationalSafetyActions:
        self._broker_day = broker_day
        self._locked = persisted_last_activation_day == broker_day
        return self.state

    def begin_day(self, broker_day: date) -> OperationalSafetyActions:
        if self._broker_day is None:
            raise RuntimeError("Restart guard has not been attached")
        if broker_day != self._broker_day:
            self._broker_day = broker_day
            self._locked = False
        return self.state

    @property
    def state(self) -> OperationalSafetyActions:
        return OperationalSafetyActions(
            locked=self._locked,
            block_new_entries=self._locked,
            cancel_pending_orders=self._locked,
            cancel_pullback_cycles=self._locked,
            close_ea_positions=self._locked,
            reason="same_day_restart_fail_closed" if self._locked else None,
        )

    @property
    def activation_day_to_persist(self) -> date:
        if self._broker_day is None:
            raise RuntimeError("Restart guard has not been attached")
        return self._broker_day
