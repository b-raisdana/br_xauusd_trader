"""Shared market-state sequencing used before future signal evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from xauusd.pullback import PullbackExpiry, PullbackOrderCandidate, PullbackTracker
from xauusd.signals import (
    BreakoutSignal,
    BreakoutTracker,
    OrderAttemptLedger,
    ReversalCandidate,
    ReversalTracker,
)
from xauusd.trend import Candle, DailyTrendTracker, TrendUpdate
from xauusd.zones import BreakoutSide, EngagementUpdate, Zone, ZoneEngagementTracker, price


@dataclass(frozen=True, slots=True)
class MarketTickUpdate:
    """Post-update snapshot that downstream signal evaluation must consume."""

    trend: TrendUpdate
    engagement: EngagementUpdate
    reversal_candidates: tuple[ReversalCandidate, ...]
    pullback_candidates: tuple[PullbackOrderCandidate, ...]


@dataclass(frozen=True, slots=True)
class MarketBarCloseUpdate:
    """Breakouts qualified from final tick state before the candle becomes history."""

    bar_id: str
    breakouts: tuple[BreakoutSignal, ...]


class MarketState:
    """Enforce TICK_EVENT_ORDER: trend, directional touch state, then signals."""

    def __init__(self) -> None:
        self.trend = DailyTrendTracker()
        self.engagement = ZoneEngagementTracker(())
        self.order_attempts = OrderAttemptLedger()
        self.reversals = ReversalTracker(self.order_attempts)
        self.pullbacks = PullbackTracker(self.order_attempts)
        self.breakouts = BreakoutTracker()
        self._zones: tuple[Zone, ...] = ()
        self._bar_id: str | None = None
        self._last_bid: Decimal | None = None

    def begin_day(self, broker_day: date, zones: Iterable[Zone]) -> tuple[PullbackExpiry, ...]:
        daily_zones = tuple(zones)
        if any(zone.broker_day != broker_day for zone in daily_zones):
            raise ValueError("All zones must belong to the active Broker Day")
        self.trend.begin_day(broker_day)
        self.engagement = ZoneEngagementTracker(daily_zones)
        self.reversals.begin_day(broker_day)
        pullback_expiries = self.pullbacks.begin_day(broker_day)
        self.breakouts.begin_day(broker_day)
        self._zones = daily_zones
        self._bar_id = None
        self._last_bid = None
        return pullback_expiries

    def record_closed_candle(self, candle: Candle) -> None:
        self.trend.record_closed_candle(candle)

    def begin_bar(
        self, open_bid: Decimal | str | int | float, *, bar_id: str
    ) -> tuple[PullbackExpiry, ...]:
        parsed_open = price(open_bid)
        self.engagement.begin_bar(parsed_open)
        self._bar_id = bar_id
        self._last_bid = parsed_open
        return self.pullbacks.begin_bar(bar_id)

    def process_tick(
        self,
        previous_bid: Decimal | str | int | float,
        bid: Decimal | str | int | float,
    ) -> MarketTickUpdate:
        if self._bar_id is None:
            raise RuntimeError("M15 bar has not been initialized")
        previous = price(previous_bid)
        current = price(bid)
        if previous != self._last_bid:
            raise ValueError("Previous Bid does not match the last processed price")
        trend_update = self.trend.update(current)
        engagement_update = self.engagement.update(previous, current)
        reversal_candidates = self.reversals.detect(
            previous_bid=previous,
            bid=current,
            trend=trend_update.current,
            zones=self._zones,
            bar_id=self._bar_id,
            multi_zone_tick_gap=engagement_update.multi_zone_tick_gap,
        )
        pullback_candidates = self.pullbacks.evaluate_price(current)
        self._last_bid = current
        return MarketTickUpdate(
            trend=trend_update,
            engagement=engagement_update,
            reversal_candidates=reversal_candidates,
            pullback_candidates=pullback_candidates,
        )

    def close_bar(self, candle: Candle) -> MarketBarCloseUpdate:
        """Evaluate the close using current tick state, then roll the trend reference."""
        if self._bar_id is None:
            raise RuntimeError("M15 bar has not been initialized")
        if candle.broker_day != self.trend.broker_day:
            raise ValueError("Closed candle belongs to a different Broker Day")
        if candle.close != self._last_bid:
            raise ValueError("Candle Close does not match the last processed price")

        bar_id = self._bar_id
        breakouts: list[BreakoutSignal] = []
        for zone in self._zones:
            signal = self.breakouts.evaluate_closed_bar(
                zone=zone,
                bar_id=bar_id,
                close=candle.close,
                trend=self.trend.state,
                buy_engaged=self.engagement.is_engaged(zone.zone_id, BreakoutSide.BUY),
                sell_engaged=self.engagement.is_engaged(zone.zone_id, BreakoutSide.SELL),
            )
            if signal is not None:
                breakouts.append(signal)
                self.pullbacks.create_window(signal, zone)

        self.trend.record_closed_candle(candle)
        self._bar_id = None
        self._last_bid = None
        return MarketBarCloseUpdate(bar_id=bar_id, breakouts=tuple(breakouts))
