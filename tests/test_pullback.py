from datetime import date
from decimal import Decimal

from xauusd.pullback import PullbackTracker
from xauusd.signals import (
    BreakoutSignal,
    OrderAttemptLedger,
    OrderType,
    ReversalTracker,
    TradeDirection,
)
from xauusd.trend import TrendState
from xauusd.zones import RawZone, Zone, build_daily_zones

DAY = date(2026, 9, 6)


def make_zone(priority: str = "normal") -> Zone:
    return build_daily_zones(
        [
            RawZone.from_values(
                broker_day=DAY,
                low="100",
                high="101",
                priority=priority,
                source_row=1,
            )
        ]
    )[DAY][0]


def make_breakout(zone: Zone, direction: TradeDirection = TradeDirection.BUY) -> BreakoutSignal:
    return BreakoutSignal(
        breakout_id="BO1",
        broker_day=DAY,
        bar_id="t",
        zone_id=zone.zone_id,
        direction=direction,
        close=Decimal("103"),
    )


def test_pullback_only_evaluates_t_plus_1_through_t_plus_5() -> None:
    zone = make_zone("high")
    tracker = PullbackTracker()
    tracker.begin_day(DAY)
    tracker.begin_bar("t")
    assert tracker.create_window(make_breakout(zone), zone)

    assert tracker.evaluate_price("100.80") == ()
    last_candidate = None
    for offset in range(1, 6):
        assert tracker.begin_bar(f"t+{offset}") == ()
        candidates = tracker.evaluate_price("100.80")
        assert len(candidates) == 1
        last_candidate = candidates[0]

    assert last_candidate is not None
    assert tracker.record_pending_order_attempt(last_candidate, broker_accepted=True).sent

    expiry = tracker.begin_bar("t+6")
    assert len(expiry) == 1
    assert expiry[0].reason == "start_of_t_plus_6"
    assert expiry[0].pending_order_must_cancel
    assert tracker.evaluate_price("100.80") == ()


def test_penetration_is_inclusive_unbounded_and_entry_stays_on_broken_edge() -> None:
    zone = make_zone()
    tracker = PullbackTracker()
    tracker.begin_day(DAY)
    tracker.create_window(make_breakout(zone), zone)
    tracker.begin_bar("t+1")

    assert tracker.evaluate_price("100.81") == ()
    at_threshold = tracker.evaluate_price("100.80")[0]
    deep = tracker.evaluate_price("90")[0]

    assert at_threshold.entry_price == zone.high
    assert deep.entry_price == zone.high
    assert at_threshold.order_type is OrderType.PENDING_STOP
    assert at_threshold.parent_breakout_id == "BO1"

    sell_tracker = PullbackTracker()
    sell_tracker.begin_day(DAY)
    sell_tracker.begin_bar("t")
    sell_tracker.create_window(make_breakout(zone, TradeDirection.SELL), zone)
    sell_tracker.begin_bar("t+1")
    assert sell_tracker.evaluate_price("100.19") == ()
    sell = sell_tracker.evaluate_price("100.20")[0]
    assert sell.entry_price == zone.low
    assert sell.direction is TradeDirection.SELL


def test_native_wait_does_not_consume_slot_and_failed_request_retries_next_bar() -> None:
    zone = make_zone("high")
    attempts = OrderAttemptLedger()
    tracker = PullbackTracker(attempts)
    tracker.begin_day(DAY)
    tracker.create_window(make_breakout(zone), zone)
    tracker.begin_bar("t+1")
    native_wait_candidate = tracker.evaluate_price("100.80")[0]

    assert attempts.can_attempt(DAY, "t+1")
    retry_same_tick = tracker.evaluate_price("100.70")[0]
    assert retry_same_tick.entry_price == native_wait_candidate.entry_price

    failed = tracker.record_pending_order_attempt(retry_same_tick, broker_accepted=False)
    assert failed.sent
    assert not attempts.can_attempt(DAY, "t+1")
    blocked = tracker.record_pending_order_attempt(native_wait_candidate, broker_accepted=True)
    assert not blocked.sent
    assert blocked.rejection_reason == "entry_attempt_already_used"

    tracker.begin_bar("t+2")
    next_bar = tracker.evaluate_price("100.70")[0]
    assert tracker.record_pending_order_attempt(next_bar, broker_accepted=True).sent


def test_first_high_fill_does_not_end_parent_and_rearms_penetration() -> None:
    zone = make_zone("high")
    tracker = PullbackTracker()
    tracker.begin_day(DAY)
    tracker.create_window(make_breakout(zone), zone)
    tracker.begin_bar("t+1")
    first = tracker.evaluate_price("100.80")[0]
    assert tracker.record_pending_order_attempt(first, broker_accepted=True).sent
    assert tracker.record_fill(first)

    assert tracker.active_parent(zone.zone_id, TradeDirection.BUY) == "BO1"
    assert tracker.daily_fills(zone.zone_id) == 1
    assert tracker.evaluate_price("100.90") == ()

    tracker.begin_bar("t+2")
    second = tracker.evaluate_price("100.70")[0]
    assert second.parent_breakout_id == "BO1"
    assert second.candidate_id != first.candidate_id
    assert tracker.record_pending_order_attempt(second, broker_accepted=True).sent
    assert tracker.record_fill(second)
    assert tracker.daily_fills(zone.zone_id) == 2


def test_normal_fill_limit_is_shared_by_direction_and_independent_of_reversal() -> None:
    zone = make_zone()
    attempts = OrderAttemptLedger()
    reversal = ReversalTracker(attempts)
    reversal.begin_day(DAY)
    reversal_candidate = reversal.detect(
        previous_bid="99",
        bid="100",
        trend=TrendState.UP,
        zones=[zone],
        bar_id="t",
        multi_zone_tick_gap=False,
    )[0]
    assert reversal.record_market_order_attempt(reversal_candidate, broker_accepted=True).sent

    tracker = PullbackTracker(attempts)
    tracker.begin_day(DAY)
    tracker.create_window(make_breakout(zone), zone)
    tracker.begin_bar("t+1")
    candidate = tracker.evaluate_price("100.80")[0]
    assert tracker.record_pending_order_attempt(candidate, broker_accepted=True).sent
    assert tracker.record_fill(candidate)

    sell_breakout = BreakoutSignal(
        breakout_id="BO2",
        broker_day=DAY,
        bar_id="t+1",
        zone_id=zone.zone_id,
        direction=TradeDirection.SELL,
        close=candidate.entry_price,
    )
    assert tracker.create_window(sell_breakout, zone)
    tracker.begin_bar("t+2")
    assert tracker.evaluate_price("100.20") == ()
    assert tracker.daily_fills(zone.zone_id) == 1


def test_only_one_active_zone_direction_window_and_day_change_cancels_pending() -> None:
    zone = make_zone("high")
    tracker = PullbackTracker()
    tracker.begin_day(DAY)
    breakout = make_breakout(zone)
    assert tracker.create_window(breakout, zone)
    assert not tracker.create_window(breakout, zone)
    tracker.begin_bar("t+1")
    pending = tracker.evaluate_price("100.80")[0]
    assert tracker.record_pending_order_attempt(pending, broker_accepted=True).sent

    expiry = tracker.begin_day(date(2026, 9, 7))
    assert len(expiry) == 1
    assert expiry[0].pending_order_must_cancel
    assert expiry[0].reason == "broker_day_changed"
    assert tracker.active_parent(zone.zone_id, TradeDirection.BUY) is None
