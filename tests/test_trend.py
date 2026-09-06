from datetime import date, timedelta
from decimal import Decimal

import pytest

from xauusd.trend import Candle, CandleDirection, DailyTrendTracker, TrendState

DAY = date(2026, 9, 6)


def candle(
    open_price: str,
    high: str,
    low: str,
    close: str,
    *,
    day: date = DAY,
) -> Candle:
    return Candle.from_values(
        broker_day=day,
        open=open_price,
        high=high,
        low=low,
        close=close,
    )


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (candle("100", "102", "99", "101"), CandleDirection.BULLISH),
        (candle("101", "102", "99", "100"), CandleDirection.BEARISH),
        (candle("100", "102", "99", "100"), CandleDirection.DOJI),
    ],
)
def test_candle_direction(item: Candle, expected: CandleDirection) -> None:
    assert item.direction is expected


def test_trend_bootstrap_none_to_n1_n2_n3_with_strict_thresholds() -> None:
    tracker = DailyTrendTracker()
    tracker.begin_day(DAY)

    assert tracker.update("999").current is TrendState.NONE

    tracker.record_closed_candle(candle("100", "102", "99", "101"))
    assert tracker.reference_count == 1
    assert tracker.update("102").current is TrendState.NONE
    assert tracker.update("102.01").current is TrendState.UP

    tracker.record_closed_candle(candle("101", "103", "100", "102"))
    assert tracker.reference_count == 2
    assert tracker.update("100.5").current is TrendState.UP

    tracker.record_closed_candle(candle("102", "104", "98", "103"))
    assert tracker.reference_count == 3
    assert tracker.reference_high == Decimal("104")
    assert tracker.reference_low == Decimal("98")
    assert tracker.update("98").current is TrendState.UP
    assert tracker.update("97.99").current is TrendState.DOWN

    tracker.record_closed_candle(candle("103", "105", "97", "104"))
    assert tracker.reference_count == 3
    assert tracker.reference_high == Decimal("105")


def test_trend_does_not_carry_into_new_broker_day() -> None:
    tracker = DailyTrendTracker()
    tracker.begin_day(DAY)
    tracker.record_closed_candle(candle("100", "101", "99", "100.5"))
    assert tracker.update("102").current is TrendState.UP

    next_day = DAY + timedelta(days=1)
    tracker.begin_day(next_day)

    assert tracker.state is TrendState.NONE
    assert tracker.reference_count == 0
    assert tracker.update("1000").current is TrendState.NONE


def test_cross_day_candle_is_rejected_until_day_transition_is_explicit() -> None:
    tracker = DailyTrendTracker()
    tracker.begin_day(DAY)

    with pytest.raises(ValueError, match="different Broker Day"):
        tracker.record_closed_candle(candle("100", "101", "99", "100", day=DAY + timedelta(days=1)))
