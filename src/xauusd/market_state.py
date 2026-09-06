"""Shared market-state sequencing used before future signal evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from xauusd.trend import Candle, DailyTrendTracker, TrendUpdate
from xauusd.zones import EngagementUpdate, Zone, ZoneEngagementTracker


@dataclass(frozen=True, slots=True)
class MarketTickUpdate:
    """Post-update snapshot that downstream signal evaluation must consume."""

    trend: TrendUpdate
    engagement: EngagementUpdate


class MarketState:
    """Enforce TICK_EVENT_ORDER: trend, directional touch state, then signals."""

    def __init__(self) -> None:
        self.trend = DailyTrendTracker()
        self.engagement = ZoneEngagementTracker(())

    def begin_day(self, broker_day: date, zones: Iterable[Zone]) -> None:
        daily_zones = tuple(zones)
        if any(zone.broker_day != broker_day for zone in daily_zones):
            raise ValueError("All zones must belong to the active Broker Day")
        self.trend.begin_day(broker_day)
        self.engagement = ZoneEngagementTracker(daily_zones)

    def record_closed_candle(self, candle: Candle) -> None:
        self.trend.record_closed_candle(candle)

    def begin_bar(self, open_bid: Decimal | str | int | float) -> None:
        self.engagement.begin_bar(open_bid)

    def process_tick(
        self,
        previous_bid: Decimal | str | int | float,
        bid: Decimal | str | int | float,
    ) -> MarketTickUpdate:
        trend_update = self.trend.update(bid)
        engagement_update = self.engagement.update(previous_bid, bid)
        return MarketTickUpdate(trend=trend_update, engagement=engagement_update)
