from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from math import isfinite
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Tick:
    time: datetime
    bid: float
    ask: float

    @property
    def is_valid(self) -> bool:
        return isfinite(self.bid) and isfinite(self.ask) and self.bid > 0.0 and self.ask > 0.0


@dataclass(frozen=True, slots=True)
class RuntimeEnvironment:
    is_tester: bool = False


class OnInitStatus(IntEnum):
    FAILED = -1
    SUCCEEDED = 0


@dataclass(frozen=True, slots=True)
class SmokeResult:
    name: str
    passed: bool
    error: str | None = None


class SmokeSuite(Protocol):
    def run_all(self) -> tuple[SmokeResult, ...]: ...


class EventLoop(Protocol):
    def process_tick(self, tick: Tick) -> bool: ...


@dataclass(frozen=True, slots=True)
class OnInitResult:
    status: OnInitStatus
    errors: tuple[str, ...] = ()
    smoke_results: tuple[SmokeResult, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.status == OnInitStatus.SUCCEEDED


@dataclass(frozen=True, slots=True)
class OnTickResult:
    handled: bool
    time_basis_probe_emitted: bool = False
    event_loop_failed: bool = False
