from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from application.xauusd_trading_strategy_1.domain.coordinator import (
    begin_coordinator_bar,
    begin_coordinator_day,
    close_coordinator_bar,
    process_coordinator_tick,
)
from application.xauusd_trading_strategy_1.domain.models import (
    XauPreparedEntry,
    XauRuntimeRequest,
)
from application.xauusd_trading_strategy_1.domain.state import record_trend_candle
from domain.xau_usd.enums import XauSignalFamily
from domain.xau_usd.models import XauSignalCandidate, XauZone
from domain.xau_usd.zone import build_merged_zones

from .global_state_variable import StrategyRuntimeState
from .lifecycle import Tick
from .settings import StrategySettings


@dataclass(frozen=True, slots=True)
class BarData:
    time: datetime
    open_bid: float
    high: float
    low: float
    close_bid: float
    ask: float


@dataclass(frozen=True, slots=True)
class SymbolSpecification:
    digits: int
    point: float
    contract_size: float
    tick_size: float
    tick_value: float
    volume_min: float
    volume_step: float
    session_from: datetime
    session_to: datetime


class EventLoopPorts(Protocol):
    def load_raw_zones(self, broker_day: str) -> list[XauZone] | None: ...
    def load_trend_history(self, day_start: datetime, bar_time: datetime) -> list[tuple[float, float]] | None: ...
    def current_bar(self, bar_time: datetime, tick: Tick) -> BarData | None: ...
    def previous_bar(self, bar_time: datetime) -> BarData | None: ...
    def symbol_specification(self, tick: Tick) -> SymbolSpecification | None: ...
    def execute_operational_safety(self, tick: Tick) -> bool: ...
    def manage_pullback_tp(self, tick: Tick) -> bool: ...
    def manage_profit_protection(self, tick: Tick) -> bool: ...
    def close_opposite_reversals(self, tick: Tick, breakouts: list[XauSignalCandidate]) -> bool: ...
    def process_candidates(self, tick: Tick, candidates: list[XauSignalCandidate]) -> bool: ...


class CurrentEventLoop:
    def __init__(
        self,
        settings: StrategySettings,
        runtime: StrategyRuntimeState,
        ports: EventLoopPorts,
        bar_time_provider: Callable[[Tick], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.runtime = runtime
        self.ports = ports
        self.bar_time_provider = bar_time_provider or (lambda tick: tick.time.replace(second=0, microsecond=0))

    def process_tick(self, tick: Tick) -> bool:
        return process_current_event_loop_tick(
            tick,
            self.bar_time_provider(tick),
            self.settings,
            self.runtime,
            self.ports,
        )


def initialize_current_event_loop(
    tick: Tick,
    bar_time: datetime,
    settings: StrategySettings,
    runtime: StrategyRuntimeState,
    ports: EventLoopPorts,
) -> bool:
    broker_day = tick.time.strftime("%Y.%m.%d")
    zone_day = broker_day.replace(".", "-")
    raw_zones = ports.load_raw_zones(broker_day)
    if raw_zones is None:
        return False

    merged_zones = build_merged_zones(raw_zones, zone_day)
    if not merged_zones or not begin_coordinator_day(runtime.market_state, zone_day, merged_zones):
        return False

    day_start = tick.time.replace(hour=0, minute=0, second=0, microsecond=0)
    history = ports.load_trend_history(day_start, bar_time)
    if history is None:
        return False
    for high, low in history:
        if not record_trend_candle(runtime.market_state.trend, high, low):
            return False

    bar = ports.current_bar(bar_time, tick)
    if bar is None or bar.open_bid <= 0.0:
        return False
    began, pending_cancellations = begin_coordinator_bar(
        runtime.market_state,
        bar.time.strftime("%Y-%m-%dT%H:%M"),
        bar.open_bid,
        bar.ask,
    )
    if not began or pending_cancellations < 0:
        return False

    runtime.current_bar_time = int(bar_time.timestamp())
    runtime.event_loop_ready = True
    runtime.daily_loss_locked = False
    runtime.operational_lock = False
    runtime.session_zero_exposure = False
    runtime.restart_lock = settings.simulate_same_day_restart
    return True


def append_runtime_request(
    runtime: StrategyRuntimeState,
    request_id: str,
    prepared: XauPreparedEntry,
) -> bool:
    if not request_id or prepared.candidate is None:
        return False
    runtime.runtime_requests.append(
        XauRuntimeRequest(
            request_id=request_id,
            candidate=prepared.candidate,
            target_zone_id=prepared.target_zone_id,
        )
    )
    return True


def find_runtime_request(runtime: StrategyRuntimeState, request_id: str) -> int:
    for index, request in enumerate(runtime.runtime_requests):
        if request.request_id == request_id:
            return index
    return -1


def attribution_index(family: XauSignalFamily, priority: int) -> int:
    family_offset = 0 if family == XauSignalFamily.BREAKOUT else 2 if family == XauSignalFamily.REVERSAL else 4
    return family_offset + (1 if priority == 1 else 0)


def process_current_event_loop_tick(
    tick: Tick,
    bar_time: datetime,
    settings: StrategySettings,
    runtime: StrategyRuntimeState,
    ports: EventLoopPorts,
) -> bool:
    if not runtime.event_loop_ready:
        if not initialize_current_event_loop(tick, bar_time, settings, runtime, ports):
            return False

    if ports.symbol_specification(tick) is None:
        return False

    if tick.time.strftime("%Y.%m.%d") != runtime.market_state.broker_day.replace("-", "."):
        runtime.event_loop_ready = False
        if not initialize_current_event_loop(tick, bar_time, settings, runtime, ports):
            return False

    close_breakouts: list[XauSignalCandidate] = []
    if bar_time.timestamp() != runtime.current_bar_time:
        previous = ports.previous_bar(bar_time)
        current = ports.current_bar(bar_time, tick)
        if previous is None or current is None:
            return False

        closed, close_breakouts = close_coordinator_bar(
            runtime.market_state,
            previous.time,
            previous.high,
            previous.low,
            previous.close_bid,
        )
        if not closed:
            return False

        began, pending_cancellations = begin_coordinator_bar(
            runtime.market_state,
            current.time.strftime("%Y-%m-%dT%H:%M"),
            current.open_bid,
            current.ask,
        )
        if not began:
            return False
        runtime.current_bar_time = int(current.time.timestamp())
        runtime.breakout_candidate_count += len(close_breakouts)

    if not ports.execute_operational_safety(tick):
        return False
    if not ports.manage_pullback_tp(tick):
        return False
    if not ports.manage_profit_protection(tick):
        return False
    if not ports.close_opposite_reversals(tick, close_breakouts):
        return False
    if not ports.process_candidates(tick, close_breakouts):
        return False

    ok, candidates = process_coordinator_tick(
        runtime.market_state,
        tick.time,
        tick.bid,
        tick.ask,
    )
    if not ok or not ports.process_candidates(tick, candidates):
        return False

    for candidate in candidates:
        if candidate.family == XauSignalFamily.REVERSAL:
            runtime.reversal_candidate_count += 1
        elif candidate.family == XauSignalFamily.PULLBACK:
            runtime.pullback_candidate_count += 1
    return True


__all__ = [
    "CurrentEventLoop",
    "BarData",
    "EventLoopPorts",
    "SymbolSpecification",
    "append_runtime_request",
    "attribution_index",
    "find_runtime_request",
    "initialize_current_event_loop",
    "process_current_event_loop_tick",
]
