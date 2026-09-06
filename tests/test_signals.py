from datetime import date

from xauusd.signals import (
    BreakoutTracker,
    OrderAttemptLedger,
    OrderType,
    ReversalTracker,
    TradeDirection,
)
from xauusd.trend import TrendState
from xauusd.zones import RawZone, Zone, build_daily_zones


def make_zone(
    *,
    day: date = date(2026, 9, 6),
    low: str = "100",
    high: str = "101",
    priority: str = "normal",
    source_row: int = 1,
) -> Zone:
    return build_daily_zones(
        [
            RawZone.from_values(
                broker_day=day,
                low=low,
                high=high,
                priority=priority,
                source_row=source_row,
            )
        ]
    )[day][0]


def test_breakout_buffer_is_strict_and_requires_matching_trend_and_engagement() -> None:
    zone = make_zone()
    tracker = BreakoutTracker()
    tracker.begin_day(zone.broker_day)

    assert (
        tracker.evaluate_closed_bar(
            zone=zone,
            bar_id="b1",
            close="102.00",
            trend=TrendState.UP,
            buy_engaged=True,
            sell_engaged=False,
        )
        is None
    )
    assert (
        tracker.evaluate_closed_bar(
            zone=zone,
            bar_id="b1",
            close="102.01",
            trend=TrendState.DOWN,
            buy_engaged=True,
            sell_engaged=False,
        )
        is None
    )
    assert (
        tracker.evaluate_closed_bar(
            zone=zone,
            bar_id="b1",
            close="102.01",
            trend=TrendState.UP,
            buy_engaged=False,
            sell_engaged=False,
        )
        is None
    )

    signal = tracker.evaluate_closed_bar(
        zone=zone,
        bar_id="b1",
        close="102.01",
        trend=TrendState.UP,
        buy_engaged=True,
        sell_engaged=False,
    )

    assert signal is not None
    assert signal.breakout_id == "BO1"
    assert signal.direction is TradeDirection.BUY
    assert signal.opposite_reversal_direction is TradeDirection.SELL


def test_sell_breakout_and_daily_lineage_reset() -> None:
    first_day = date(2026, 9, 6)
    second_day = date(2026, 9, 7)
    tracker = BreakoutTracker()
    first = make_zone(day=first_day)
    second = make_zone(day=second_day)

    tracker.begin_day(first_day)
    assert (
        tracker.evaluate_closed_bar(
            zone=first,
            bar_id="b0",
            close="99.00",
            trend=TrendState.DOWN,
            buy_engaged=False,
            sell_engaged=True,
        )
        is None
    )
    signal = tracker.evaluate_closed_bar(
        zone=first,
        bar_id="b1",
        close="98.99",
        trend=TrendState.DOWN,
        buy_engaged=False,
        sell_engaged=True,
    )
    assert signal is not None
    assert signal.breakout_id == "BO1"
    assert signal.direction is TradeDirection.SELL

    tracker.begin_day(second_day)
    next_signal = tracker.evaluate_closed_bar(
        zone=second,
        bar_id="b2",
        close="102.01",
        trend=TrendState.UP,
        buy_engaged=True,
        sell_engaged=False,
    )
    assert next_signal is not None
    assert next_signal.breakout_id == "BO1"


def test_reversal_is_tick_directional_market_only_and_duplicate_guarded() -> None:
    zone = make_zone()
    tracker = ReversalTracker()
    tracker.begin_day(zone.broker_day)

    first = tracker.detect(
        previous_bid="99",
        bid="100.5",
        trend=TrendState.UP,
        zones=[zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )
    assert len(first) == 1
    assert first[0].direction is TradeDirection.SELL
    assert first[0].order_type is OrderType.MARKET

    tracker.detect(
        previous_bid="100.5",
        bid="99",
        trend=TrendState.UP,
        zones=[zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )
    duplicate = tracker.detect(
        previous_bid="99",
        bid="100",
        trend=TrendState.UP,
        zones=[zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )
    assert duplicate == ()


def test_single_zone_wick_penetration_does_not_invalidate_reversal() -> None:
    zone = make_zone()
    tracker = ReversalTracker()
    tracker.begin_day(zone.broker_day)

    candidate = tracker.detect(
        previous_bid="99",
        bid="102",
        trend=TrendState.UP,
        zones=[zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )

    assert len(candidate) == 1
    assert candidate[0].direction is TradeDirection.SELL


def test_downtrend_touch_builds_buy_and_multi_zone_gap_builds_no_path() -> None:
    day = date(2026, 9, 6)
    zone = make_zone(day=day)
    tracker = ReversalTracker()
    tracker.begin_day(day)

    buy = tracker.detect(
        previous_bid="102",
        bid="100.5",
        trend=TrendState.DOWN,
        zones=[zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )
    assert [candidate.direction for candidate in buy] == [TradeDirection.BUY]

    assert (
        tracker.detect(
            previous_bid="99",
            bid="105",
            trend=TrendState.UP,
            zones=[zone],
            bar_id="b2",
            multi_zone_tick_gap=True,
        )
        == ()
    )


def test_signal_alone_does_not_consume_usage_and_failed_request_does() -> None:
    zone = make_zone()
    tracker = ReversalTracker()
    tracker.begin_day(zone.broker_day)
    candidate = tracker.detect(
        previous_bid="99",
        bid="100",
        trend=TrendState.UP,
        zones=[zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )[0]

    assert tracker.daily_usage(zone.zone_id) == 0
    attempt = tracker.record_market_order_attempt(candidate, broker_accepted=False)
    assert attempt.sent
    assert attempt.broker_accepted is False
    assert tracker.daily_usage(zone.zone_id) == 1

    later = tracker.detect(
        previous_bid="102",
        bid="101",
        trend=TrendState.DOWN,
        zones=[zone],
        bar_id="b2",
        multi_zone_tick_gap=False,
    )[0]
    blocked = tracker.record_market_order_attempt(later, broker_accepted=True)
    assert not blocked.sent
    assert blocked.rejection_reason == "daily_reversal_limit"


def test_high_zone_allows_two_sent_requests_shared_across_directions() -> None:
    zone = make_zone(priority="high")
    tracker = ReversalTracker()
    tracker.begin_day(zone.broker_day)
    sell = tracker.detect(
        previous_bid="99",
        bid="100",
        trend=TrendState.UP,
        zones=[zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )[0]
    buy = tracker.detect(
        previous_bid="102",
        bid="101",
        trend=TrendState.DOWN,
        zones=[zone],
        bar_id="b2",
        multi_zone_tick_gap=False,
    )[0]
    third = tracker.detect(
        previous_bid="99",
        bid="100",
        trend=TrendState.UP,
        zones=[zone],
        bar_id="b3",
        multi_zone_tick_gap=False,
    )[0]

    assert tracker.record_market_order_attempt(sell, broker_accepted=True).sent
    assert tracker.record_market_order_attempt(buy, broker_accepted=False).sent
    blocked = tracker.record_market_order_attempt(third, broker_accepted=True)
    assert tracker.daily_usage(zone.zone_id) == 2
    assert not blocked.sent
    assert blocked.rejection_reason == "daily_reversal_limit"


def test_first_request_consumes_shared_bar_slot_even_when_broker_rejects() -> None:
    day = date(2026, 9, 6)
    attempts = OrderAttemptLedger()
    attempts.begin_day(day)
    high_zone = make_zone(day=day, priority="high")
    tracker = ReversalTracker(attempts)
    tracker.begin_day(day)
    sell = tracker.detect(
        previous_bid="99",
        bid="100",
        trend=TrendState.UP,
        zones=[high_zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )[0]
    buy = tracker.detect(
        previous_bid="102",
        bid="101",
        trend=TrendState.DOWN,
        zones=[high_zone],
        bar_id="b1",
        multi_zone_tick_gap=False,
    )[0]

    assert tracker.record_market_order_attempt(sell, broker_accepted=False).sent
    blocked = tracker.record_market_order_attempt(buy, broker_accepted=True)
    assert not blocked.sent
    assert blocked.rejection_reason == "entry_attempt_already_used"
    assert tracker.daily_usage(high_zone.zone_id) == 1
