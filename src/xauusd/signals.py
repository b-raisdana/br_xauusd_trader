"""Breakout and Reversal signal contracts plus shared entry-attempt state."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from xauusd.trend import TrendState
from xauusd.zones import Zone, ZonePriority, price

BREAKOUT_BUFFER_USD = Decimal("1.00")


class TradeDirection(StrEnum):
    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> TradeDirection:
        return TradeDirection.SELL if self is TradeDirection.BUY else TradeDirection.BUY


class OrderType(StrEnum):
    MARKET = "market"


@dataclass(frozen=True, slots=True)
class BreakoutSignal:
    breakout_id: str
    broker_day: date
    bar_id: str
    zone_id: str
    direction: TradeDirection
    close: Decimal

    @property
    def opposite_reversal_direction(self) -> TradeDirection:
        """Direction of an open Reversal invalidated by this Breakout."""
        return self.direction.opposite


class BreakoutTracker:
    """Qualify strict-buffer Breakouts and assign daily BO lineage IDs."""

    def __init__(self) -> None:
        self._broker_day: date | None = None
        self._sequence = 0

    def begin_day(self, broker_day: date) -> None:
        if broker_day != self._broker_day:
            self._broker_day = broker_day
            self._sequence = 0

    def evaluate_closed_bar(
        self,
        *,
        zone: Zone,
        bar_id: str,
        close: Decimal | str | int | float,
        trend: TrendState,
        buy_engaged: bool,
        sell_engaged: bool,
    ) -> BreakoutSignal | None:
        if self._broker_day is None:
            self.begin_day(zone.broker_day)
        if zone.broker_day != self._broker_day:
            raise ValueError("Zone belongs to a different Broker Day")

        close_price = price(close)
        direction: TradeDirection | None = None
        if buy_engaged and trend is TrendState.UP and close_price > zone.high + BREAKOUT_BUFFER_USD:
            direction = TradeDirection.BUY
        elif (
            sell_engaged
            and trend is TrendState.DOWN
            and close_price < zone.low - BREAKOUT_BUFFER_USD
        ):
            direction = TradeDirection.SELL

        if direction is None:
            return None

        self._sequence += 1
        return BreakoutSignal(
            breakout_id=f"BO{self._sequence}",
            broker_day=zone.broker_day,
            bar_id=bar_id,
            zone_id=zone.zone_id,
            direction=direction,
            close=close_price,
        )


@dataclass(frozen=True, slots=True)
class ReversalCandidate:
    broker_day: date
    bar_id: str
    zone_id: str
    zone_priority: ZonePriority
    direction: TradeDirection
    touch_price: Decimal
    order_type: OrderType = OrderType.MARKET


@dataclass(frozen=True, slots=True)
class OrderAttemptResult:
    sent: bool
    broker_accepted: bool | None
    rejection_reason: str | None = None


class OrderAttemptLedger:
    """Enforce ONE_NEW_ORDER_PER_CANDLE across all future signal families."""

    def __init__(self) -> None:
        self._broker_day: date | None = None
        self._attempted_bars: set[str] = set()

    def begin_day(self, broker_day: date) -> None:
        if broker_day != self._broker_day:
            self._broker_day = broker_day
            self._attempted_bars.clear()

    def can_attempt(self, broker_day: date, bar_id: str) -> bool:
        return broker_day == self._broker_day and bar_id not in self._attempted_bars

    def record_attempt(self, broker_day: date, bar_id: str) -> bool:
        if not self.can_attempt(broker_day, bar_id):
            return False
        self._attempted_bars.add(bar_id)
        return True


class ReversalTracker:
    """Detect tick-real Reversals and account for sent Market requests."""

    def __init__(self, order_attempts: OrderAttemptLedger | None = None) -> None:
        self.order_attempts = order_attempts or OrderAttemptLedger()
        self._broker_day: date | None = None
        self._duplicate_keys: set[tuple[str, str, TradeDirection]] = set()
        self._detected_candidates: set[ReversalCandidate] = set()
        self._daily_usage: dict[str, int] = {}

    def begin_day(self, broker_day: date) -> None:
        if broker_day != self._broker_day:
            self._broker_day = broker_day
            self._duplicate_keys.clear()
            self._detected_candidates.clear()
            self._daily_usage.clear()
        self.order_attempts.begin_day(broker_day)

    def daily_usage(self, zone_id: str) -> int:
        return self._daily_usage.get(zone_id, 0)

    def detect(
        self,
        *,
        previous_bid: Decimal | str | int | float,
        bid: Decimal | str | int | float,
        trend: TrendState,
        zones: Iterable[Zone],
        bar_id: str,
        multi_zone_tick_gap: bool,
    ) -> tuple[ReversalCandidate, ...]:
        if self._broker_day is None:
            raise RuntimeError("Reversal day has not been initialized")
        if multi_zone_tick_gap:
            return ()

        previous = price(previous_bid)
        current = price(bid)
        candidates: list[ReversalCandidate] = []
        for zone in zones:
            if zone.broker_day != self._broker_day:
                raise ValueError("Zone belongs to a different Broker Day")

            direction: TradeDirection | None = None
            if trend is TrendState.UP and previous < zone.low <= current:
                direction = TradeDirection.SELL
            elif trend is TrendState.DOWN and previous > zone.high >= current:
                direction = TradeDirection.BUY
            if direction is None:
                continue

            duplicate_key = (bar_id, zone.zone_id, direction)
            if duplicate_key in self._duplicate_keys:
                continue
            self._duplicate_keys.add(duplicate_key)
            candidate = ReversalCandidate(
                broker_day=zone.broker_day,
                bar_id=bar_id,
                zone_id=zone.zone_id,
                zone_priority=zone.priority,
                direction=direction,
                touch_price=current,
            )
            self._detected_candidates.add(candidate)
            candidates.append(candidate)
        return tuple(candidates)

    def record_market_order_attempt(
        self,
        candidate: ReversalCandidate,
        *,
        broker_accepted: bool,
    ) -> OrderAttemptResult:
        """Record a request sent now; rejected requests consume both capacities."""
        if candidate.broker_day != self._broker_day:
            return OrderAttemptResult(False, None, "different_broker_day")
        if candidate not in self._detected_candidates:
            return OrderAttemptResult(False, None, "unregistered_candidate")

        limit = 2 if candidate.zone_priority is ZonePriority.HIGH else 1
        if self.daily_usage(candidate.zone_id) >= limit:
            return OrderAttemptResult(False, None, "daily_reversal_limit")
        if not self.order_attempts.record_attempt(candidate.broker_day, candidate.bar_id):
            return OrderAttemptResult(False, None, "entry_attempt_already_used")

        self._daily_usage[candidate.zone_id] = self.daily_usage(candidate.zone_id) + 1
        return OrderAttemptResult(True, broker_accepted)
