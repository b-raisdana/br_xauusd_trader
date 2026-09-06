"""Shared market-state sequencing used before future signal evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from xauusd.signals import ReversalCandidate, ReversalTracker
from xauusd.trend import Candle, DailyTrendTracker, TrendUpdate
from xauusd.zones import EngagementUpdate, Zone, ZoneEngagementTracker


@dataclass(frozen=True, slots=True)
class MarketTickUpdate:
    """Post-update snapshot that downstream signal evaluation must consume."""

    trend: TrendUpdate
    engagement: EngagementUpdate
    reversal_candidates: tuple[ReversalCandidate, ...]


class MarketState:
    """Enforce TICK_EVENT_ORDER: trend, directional touch state, then signals."""

    def __init__(self) -> None:
        self.trend = DailyTrendTracker()
        self.engagement = ZoneEngagementTracker(())
        self.reversals = ReversalTracker()
        self._zones: tuple[Zone, ...] = ()
        self._bar_id: str | None = None

    def begin_day(self, broker_day: date, zones: Iterable[Zone]) -> None:
        daily_zones = tuple(zones)
        if any(zone.broker_day != broker_day for zone in daily_zones):
            raise ValueError("All zones must belong to the active Broker Day")
        self.trend.begin_day(broker_day)
        self.engagement = ZoneEngagementTracker(daily_zones)
        self.reversals.begin_day(broker_day)
        self._zones = daily_zones
        self._bar_id = None

    def record_closed_candle(self, candle: Candle) -> None:
        self.trend.record_closed_candle(candle)

    def begin_bar(self, open_bid: Decimal | str | int | float, *, bar_id: str) -> None:
        self.engagement.begin_bar(open_bid)
        self._bar_id = bar_id

    def process_tick(
        self,
        previous_bid: Decimal | str | int | float,
        bid: Decimal | str | int | float,
    ) -> MarketTickUpdate:
        if self._bar_id is None:
            raise RuntimeError("M15 bar has not been initialized")
        trend_update = self.trend.update(bid)
        engagement_update = self.engagement.update(previous_bid, bid)
        reversal_candidates = self.reversals.detect(
            previous_bid=previous_bid,
            bid=bid,
            trend=trend_update.current,
            zones=self._zones,
            bar_id=self._bar_id,
            multi_zone_tick_gap=engagement_update.multi_zone_tick_gap,
        )
        return MarketTickUpdate(
            trend=trend_update,
            engagement=engagement_update,
            reversal_candidates=reversal_candidates,
        )
