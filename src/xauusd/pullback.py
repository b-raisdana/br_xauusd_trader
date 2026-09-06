"""Conservative Pullback window, penetration, retry, and fill contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from xauusd.signals import (
    BreakoutSignal,
    OrderAttemptLedger,
    OrderAttemptResult,
    OrderType,
    TradeDirection,
)
from xauusd.zones import Zone, ZonePriority, price

PULLBACK_PENETRATION_USD = Decimal("0.20")
PULLBACK_WINDOW_BARS = 5


def pullback_window_active(bar_offset: int) -> bool:
    return 1 <= bar_offset <= PULLBACK_WINDOW_BARS


def pullback_usage_allowed(priority: ZonePriority, daily_fills: int) -> bool:
    if daily_fills < 0:
        raise ValueError("Daily Pullback fills cannot be negative")
    return priority is ZonePriority.HIGH or daily_fills < 1


@dataclass(frozen=True, slots=True)
class PullbackOrderCandidate:
    candidate_id: str
    parent_breakout_id: str
    broker_day: date
    bar_id: str
    zone_id: str
    zone_priority: ZonePriority
    direction: TradeDirection
    entry_price: Decimal
    order_type: OrderType = OrderType.PENDING_STOP


@dataclass(frozen=True, slots=True)
class PullbackExpiry:
    parent_breakout_id: str
    zone_id: str
    direction: TradeDirection
    pending_order_must_cancel: bool
    reason: str


@dataclass(slots=True)
class _PullbackWindow:
    parent_breakout_id: str
    broker_day: date
    zone: Zone
    direction: TradeDirection
    bar_offset: int = 0
    active: bool = True
    penetration_latched: bool = False
    pending_candidate: PullbackOrderCandidate | None = None
    sequence: int = 0

    @property
    def key(self) -> tuple[str, TradeDirection]:
        return (self.zone.zone_id, self.direction)


class PullbackTracker:
    """Manage one active Pullback window per Zone+Direction."""

    def __init__(self, order_attempts: OrderAttemptLedger | None = None) -> None:
        self.order_attempts = order_attempts or OrderAttemptLedger()
        self._broker_day: date | None = None
        self._bar_id: str | None = None
        self._windows: dict[tuple[str, TradeDirection], _PullbackWindow] = {}
        self._daily_fills: dict[str, int] = {}
        self._issued_candidates: set[PullbackOrderCandidate] = set()
        self._attempted_candidates: set[PullbackOrderCandidate] = set()

    def begin_day(self, broker_day: date) -> tuple[PullbackExpiry, ...]:
        if broker_day == self._broker_day:
            return ()
        expired = tuple(
            self._expire(window, "broker_day_changed")
            for window in self._windows.values()
            if window.active
        )
        self._broker_day = broker_day
        self._bar_id = None
        self._windows.clear()
        self._daily_fills.clear()
        self._issued_candidates.clear()
        self._attempted_candidates.clear()
        self.order_attempts.begin_day(broker_day)
        return expired

    def begin_bar(self, bar_id: str) -> tuple[PullbackExpiry, ...]:
        if self._broker_day is None:
            raise RuntimeError("Pullback day has not been initialized")
        if bar_id == self._bar_id:
            return ()
        self._bar_id = bar_id
        expired: list[PullbackExpiry] = []
        for window in self._windows.values():
            if not window.active:
                continue
            window.bar_offset += 1
            if window.bar_offset > PULLBACK_WINDOW_BARS:
                expired.append(self._expire(window, "start_of_t_plus_6"))
        return tuple(expired)

    def create_window(self, breakout: BreakoutSignal, zone: Zone) -> bool:
        if self._broker_day is None:
            raise RuntimeError("Pullback day has not been initialized")
        if breakout.broker_day != self._broker_day or zone.broker_day != self._broker_day:
            raise ValueError("Breakout and Zone must belong to the active Broker Day")
        if breakout.zone_id != zone.zone_id:
            raise ValueError("Breakout and Zone identifiers do not match")
        key = (zone.zone_id, breakout.direction)
        existing = self._windows.get(key)
        if existing is not None and existing.active:
            return False
        self._windows[key] = _PullbackWindow(
            parent_breakout_id=breakout.breakout_id,
            broker_day=breakout.broker_day,
            zone=zone,
            direction=breakout.direction,
        )
        return True

    def active_parent(self, zone_id: str, direction: TradeDirection) -> str | None:
        window = self._windows.get((zone_id, direction))
        if window is None or not window.active:
            return None
        return window.parent_breakout_id

    def daily_fills(self, zone_id: str) -> int:
        return self._daily_fills.get(zone_id, 0)

    def evaluate_price(
        self,
        bid: Decimal | str | int | float,
    ) -> tuple[PullbackOrderCandidate, ...]:
        if self._bar_id is None:
            raise RuntimeError("M15 bar has not been initialized")
        current = price(bid)
        candidates: list[PullbackOrderCandidate] = []
        for window in self._windows.values():
            if not window.active or not pullback_window_active(window.bar_offset):
                continue
            if window.pending_candidate is not None:
                continue
            if not pullback_usage_allowed(
                window.zone.priority, self.daily_fills(window.zone.zone_id)
            ):
                continue

            if not window.penetration_latched:
                if window.direction is TradeDirection.BUY:
                    window.penetration_latched = (
                        current <= window.zone.high - PULLBACK_PENETRATION_USD
                    )
                else:
                    window.penetration_latched = (
                        current >= window.zone.low + PULLBACK_PENETRATION_USD
                    )
            if not window.penetration_latched:
                continue

            window.sequence += 1
            candidate = PullbackOrderCandidate(
                candidate_id=f"{window.parent_breakout_id}:PB{window.sequence}",
                parent_breakout_id=window.parent_breakout_id,
                broker_day=window.broker_day,
                bar_id=self._bar_id,
                zone_id=window.zone.zone_id,
                zone_priority=window.zone.priority,
                direction=window.direction,
                entry_price=(
                    window.zone.high if window.direction is TradeDirection.BUY else window.zone.low
                ),
            )
            self._issued_candidates.add(candidate)
            candidates.append(candidate)
        return tuple(candidates)

    def record_pending_order_attempt(
        self,
        candidate: PullbackOrderCandidate,
        *,
        broker_accepted: bool,
    ) -> OrderAttemptResult:
        """Record an actual pending request; native precheck waits never call this."""
        window = self._window_for(candidate)
        if window is None:
            return OrderAttemptResult(False, None, "inactive_pullback_window")
        if candidate not in self._issued_candidates:
            return OrderAttemptResult(False, None, "unregistered_candidate")
        if candidate in self._attempted_candidates:
            return OrderAttemptResult(False, None, "candidate_already_attempted")
        if candidate.bar_id != self._bar_id:
            return OrderAttemptResult(False, None, "candidate_from_different_bar")
        if window.pending_candidate is not None:
            return OrderAttemptResult(False, None, "pending_already_active")
        if not pullback_usage_allowed(window.zone.priority, self.daily_fills(window.zone.zone_id)):
            return OrderAttemptResult(False, None, "daily_pullback_fill_limit")
        if not self.order_attempts.record_attempt(candidate.broker_day, candidate.bar_id):
            return OrderAttemptResult(False, None, "entry_attempt_already_used")

        self._attempted_candidates.add(candidate)
        if broker_accepted:
            window.pending_candidate = candidate
        return OrderAttemptResult(True, broker_accepted)

    def record_pending_removed(self, candidate: PullbackOrderCandidate) -> bool:
        """Allow exact-price retry after an unfilled pending disappears."""
        window = self._window_for(candidate)
        if window is None or window.pending_candidate != candidate:
            return False
        window.pending_candidate = None
        return True

    def record_fill(self, candidate: PullbackOrderCandidate) -> bool:
        window = self._window_for(candidate)
        if window is None or window.pending_candidate != candidate:
            return False
        self._daily_fills[window.zone.zone_id] = self.daily_fills(window.zone.zone_id) + 1
        window.pending_candidate = None
        window.penetration_latched = False
        return True

    def _window_for(self, candidate: PullbackOrderCandidate) -> _PullbackWindow | None:
        if candidate.broker_day != self._broker_day:
            return None
        window = self._windows.get((candidate.zone_id, candidate.direction))
        if window is None or not window.active:
            return None
        if window.parent_breakout_id != candidate.parent_breakout_id:
            return None
        return window

    @staticmethod
    def _expire(window: _PullbackWindow, reason: str) -> PullbackExpiry:
        expiry = PullbackExpiry(
            parent_breakout_id=window.parent_breakout_id,
            zone_id=window.zone.zone_id,
            direction=window.direction,
            pending_order_must_cancel=window.pending_candidate is not None,
            reason=reason,
        )
        window.active = False
        window.pending_candidate = None
        return expiry
