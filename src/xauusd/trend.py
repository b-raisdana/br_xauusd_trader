"""Daily trend bootstrap and live threshold contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from xauusd.zones import price


class CandleDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    DOJI = "doji"


class TrendState(StrEnum):
    NONE = "none"
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class Candle:
    broker_day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    @classmethod
    def from_values(
        cls,
        *,
        broker_day: date,
        open: Decimal | str | int | float,
        high: Decimal | str | int | float,
        low: Decimal | str | int | float,
        close: Decimal | str | int | float,
    ) -> Candle:
        candle = cls(
            broker_day=broker_day,
            open=price(open),
            high=price(high),
            low=price(low),
            close=price(close),
        )
        if candle.high < max(candle.open, candle.close):
            raise ValueError("Candle high cannot be below open or close")
        if candle.low > min(candle.open, candle.close):
            raise ValueError("Candle low cannot be above open or close")
        return candle

    @property
    def direction(self) -> CandleDirection:
        if self.close > self.open:
            return CandleDirection.BULLISH
        if self.close < self.open:
            return CandleDirection.BEARISH
        return CandleDirection.DOJI


@dataclass(frozen=True, slots=True)
class TrendUpdate:
    previous: TrendState
    current: TrendState
    reference_count: int
    reference_high: Decimal | None
    reference_low: Decimal | None

    @property
    def changed(self) -> bool:
        return self.previous is not self.current


class DailyTrendTracker:
    """Implement DAY_START_TREND_BOOTSTRAP and TREND_DIRECTION."""

    def __init__(self) -> None:
        self._broker_day: date | None = None
        self._state = TrendState.NONE
        self._closed_candles: list[Candle] = []

    @property
    def broker_day(self) -> date | None:
        return self._broker_day

    @property
    def state(self) -> TrendState:
        return self._state

    @property
    def reference_count(self) -> int:
        return len(self._closed_candles)

    @property
    def reference_high(self) -> Decimal | None:
        if not self._closed_candles:
            return None
        return max(candle.high for candle in self._closed_candles)

    @property
    def reference_low(self) -> Decimal | None:
        if not self._closed_candles:
            return None
        return min(candle.low for candle in self._closed_candles)

    def begin_day(self, broker_day: date) -> None:
        if broker_day == self._broker_day:
            return
        self._broker_day = broker_day
        self._state = TrendState.NONE
        self._closed_candles.clear()

    def record_closed_candle(self, candle: Candle) -> None:
        if self._broker_day is None:
            self.begin_day(candle.broker_day)
        if candle.broker_day != self._broker_day:
            raise ValueError("Closed candle belongs to a different Broker Day")
        self._closed_candles.append(candle)
        del self._closed_candles[:-3]

    def update(self, bid: Decimal | str | int | float) -> TrendUpdate:
        previous = self._state
        reference_high = self.reference_high
        reference_low = self.reference_low

        if reference_high is not None and reference_low is not None:
            current_bid = price(bid)
            if current_bid > reference_high:
                self._state = TrendState.UP
            elif current_bid < reference_low:
                self._state = TrendState.DOWN

        return TrendUpdate(
            previous=previous,
            current=self._state,
            reference_count=self.reference_count,
            reference_high=reference_high,
            reference_low=reference_low,
        )
