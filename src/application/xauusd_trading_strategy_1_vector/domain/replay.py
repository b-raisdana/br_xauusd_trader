from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Protocol

from application.xauusd_trading_strategy_1.domain.models import XauPreZoneTriggerState, XauPullbackTpState
from domain.xau_usd.enums import XauDirection, XauExecutionStatus
from domain.xau_usd.models import XauSignalCandidate


class ReplayEconomics(Protocol):
    minimum_stop_distance: float

    def profit(self, direction: XauDirection, volume: float, entry: float, exit_price: float) -> float: ...
    def margin(self, volume: float, entry: float) -> float: ...
    def cost(self, volume: float, time: datetime, opening: bool) -> float: ...
    def session_end(self, time: datetime) -> datetime: ...
    def accepts(self, operation: str, request_id: str, time: datetime) -> bool: ...


@dataclass(frozen=True)
class LinearReplayEconomics:
    """Explicit account-currency assumptions for offline replay, not native MT5 accounting."""

    cash_per_price_unit_per_lot: float
    margin_per_lot: float
    entry_cost_per_lot: float
    exit_cost_per_lot: float
    minimum_stop_distance: float
    sessions: dict[str, datetime]

    def __post_init__(self):
        values = (
            self.cash_per_price_unit_per_lot,
            self.margin_per_lot,
            self.entry_cost_per_lot,
            self.exit_cost_per_lot,
            self.minimum_stop_distance,
        )
        if any(not isfinite(value) or value < 0 for value in values) or self.cash_per_price_unit_per_lot == 0:
            raise ValueError("Replay economics must be finite and nonnegative, with a positive cash multiplier")
        if any(value.tzinfo is None for value in self.sessions.values()):
            raise ValueError("Session ends must be timezone-aware")

    def profit(self, direction, volume, entry, exit_price):
        sign = 1 if direction == XauDirection.BUY else -1
        return sign * (exit_price - entry) * volume * self.cash_per_price_unit_per_lot

    def margin(self, volume, entry):
        return volume * self.margin_per_lot

    def cost(self, volume, time, opening):
        return volume * (self.entry_cost_per_lot if opening else self.exit_cost_per_lot)

    def session_end(self, time):
        return self.sessions[time.strftime("%Y-%m-%d")]

    def accepts(self, operation, request_id, time):
        return True


@dataclass(frozen=True)
class ReplayConfig:
    economics: ReplayEconomics
    strategy_capital: float = 200.0
    initial_balance: float = 200.0
    restart_days: frozenset[str] = frozenset()

    def __post_init__(self):
        if self.strategy_capital not in (200.0, 300.0):
            raise ValueError("Strategy capital must be 200 or 300")
        if not isfinite(self.initial_balance) or self.initial_balance <= 0:
            raise ValueError("Initial balance must be finite and positive")
        if not isfinite(self.economics.minimum_stop_distance) or self.economics.minimum_stop_distance < 0:
            raise ValueError("Minimum stop distance must be finite and nonnegative")


@dataclass
class ReplayOrder:
    request_id: str
    candidate: XauSignalCandidate
    volume: float
    stop_loss: float
    take_profit: float
    target_zone_id: str
    submitted_time: datetime
    status: XauExecutionStatus = XauExecutionStatus.SUBMITTED
    fill_price: float = 0.0
    fill_time: datetime | None = None
    close_price: float = 0.0
    close_time: datetime | None = None
    costs: float = 0.0
    realized_pnl: float = 0.0
    closed_directions: list[int] = field(default_factory=list)
    trigger: XauPreZoneTriggerState = field(default_factory=XauPreZoneTriggerState)
    tp: XauPullbackTpState = field(default_factory=XauPullbackTpState)

    @property
    def direction(self):
        return self.candidate.direction

    @property
    def position_id(self):
        return self.request_id.replace("REQ-", "POS-", 1) if self.fill_time is not None else None

    def mark(self, bid, ask):
        return bid if self.direction == XauDirection.BUY else ask
