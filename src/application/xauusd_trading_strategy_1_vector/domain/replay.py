from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from domain.xau_usd.enums import XauDirection, XauExecutionStatus, XauSignalFamily
from domain.xau_usd.models import XauPreZoneTriggerState, XauPullbackTpState, XauSignalCandidate

from .robust import RobustInputs


class ReplayEconomics(Protocol):
    minimum_stop_distance: float

    def profit(self, direction: XauDirection, volume: float, entry: float, exit_price: float) -> float: ...
    def margin(self, volume: float, entry: float) -> float: ...
    def cost(self, volume: float, time: datetime, opening: bool) -> float: ...
    def session_end(self, time: datetime) -> datetime: ...
    def session_window(self, time: datetime) -> tuple[datetime, datetime] | None: ...
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
    session_windows: tuple[tuple[datetime, datetime], ...] = ()

    def __post_init__(self) -> None:
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
        if any(a.tzinfo is None or b.tzinfo is None or a >= b for a, b in self.session_windows):
            raise ValueError("Session windows require aware start < end")

    def profit(self, direction: XauDirection, volume: float, entry: float, exit_price: float) -> float:
        sign = 1 if direction == XauDirection.BUY else -1
        return sign * (exit_price - entry) * volume * self.cash_per_price_unit_per_lot

    def margin(self, volume: float, entry: float) -> float:
        return volume * self.margin_per_lot

    def cost(self, volume: float, time: datetime, opening: bool) -> float:
        return volume * (self.entry_cost_per_lot if opening else self.exit_cost_per_lot)

    def session_end(self, time: datetime) -> datetime:
        return self.sessions[time.strftime("%Y-%m-%d")]

    def session_window(self, time: datetime) -> tuple[datetime, datetime] | None:
        if self.session_windows:
            return next(((a, b) for a, b in self.session_windows if a <= time < b), None)
        end = self.session_end(time)
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        return (start, end) if start <= time < end else None

    def accepts(self, operation: str, request_id: str, time: datetime) -> bool:
        return True


@dataclass(frozen=True)
class ReplayConfig:
    economics: ReplayEconomics
    strategy_capital: float = 200.0
    initial_balance: float = 200.0
    restart_days: frozenset[str] = frozenset()
    inputs: RobustInputs = field(default_factory=RobustInputs)

    def __post_init__(self) -> None:
        if not isfinite(self.strategy_capital) or self.strategy_capital <= 0:
            raise ValueError("Strategy capital must be finite and positive")
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

    request_active: bool = True
    broker_day: str = ""
    initial_sl: float = 0.0
    r0: float = 0.0
    r_stage: int = 0
    desired_sl: float = 0.0
    sl_retry_logged: bool = False
    reversal_ordinal: int = 0
    stacked_pullback: bool = False
    session_close_requested: bool = False
    session_close_reason: str = ""
    last_carry_audit_key: str = ""
    native_order_ticket: int = 0
    native_position_id: int | None = None
    native_position_ticket: int = 0
    native_trade_type: str | None = None

    @property
    def comment(self) -> str:
        kind = (
            self.native_trade_type
            if self.native_trade_type is not None
            else {XauSignalFamily.REVERSAL: "R", XauSignalFamily.BREAKOUT: "B", XauSignalFamily.PULLBACK: "P"}[
                self.candidate.family
            ]
        )
        side = "B" if self.direction == XauDirection.BUY else "S"
        return f"{kind}|{self.broker_day.replace('-', '')}|{self.candidate.zone_id}|{side}"

    @property
    def direction(self) -> XauDirection:
        return self.candidate.direction

    @property
    def position_id(self) -> str | None:
        return self.request_id.replace("REQ-", "POS-", 1) if self.fill_time is not None else None

    def mark(self, bid: float, ask: float) -> float:
        return bid if self.direction == XauDirection.BUY else ask


class ReplayFileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    economics: LinearReplayEconomics
    initial_balance: float = Field(default=200, gt=0, allow_inf_nan=False)
    inputs: RobustInputs = Field(default_factory=RobustInputs)
    restart_days: frozenset[str] = frozenset()

    def replay_config(self) -> ReplayConfig:
        return ReplayConfig(
            self.economics, initial_balance=self.initial_balance, inputs=self.inputs, restart_days=self.restart_days
        )
