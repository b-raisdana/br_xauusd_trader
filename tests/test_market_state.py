from datetime import date

import pytest

from xauusd.market_state import MarketState
from xauusd.signals import TradeDirection
from xauusd.trend import Candle, TrendState
from xauusd.zones import BreakoutSide, RawZone, build_daily_zones


def test_tick_snapshot_contains_new_trend_before_directional_touch_state() -> None:
    day = date(2026, 9, 6)
    zone = build_daily_zones(
        [
            RawZone.from_values(
                broker_day=day,
                low="101",
                high="102",
                priority="normal",
                source_row=1,
            )
        ]
    )[day][0]
    state = MarketState()
    state.begin_day(day, [zone])
    state.record_closed_candle(
        Candle.from_values(
            broker_day=day,
            open="95",
            high="100",
            low="90",
            close="99",
        )
    )
    state.begin_bar("99", bar_id="2026-09-06T10:00")

    update = state.process_tick(previous_bid="99", bid="101")

    assert update.trend.current is TrendState.UP
    assert update.trend.changed
    assert [(event.zone_id, event.side) for event in update.engagement.events] == [
        (zone.zone_id, BreakoutSide.BUY)
    ]
    assert len(update.reversal_candidates) == 1
    assert update.reversal_candidates[0].direction is TradeDirection.SELL


def test_bar_close_qualifies_breakout_before_rolling_reference_candle() -> None:
    day = date(2026, 9, 6)
    zone = build_daily_zones(
        [
            RawZone.from_values(
                broker_day=day,
                low="100",
                high="101",
                priority="normal",
                source_row=1,
            )
        ]
    )[day][0]
    state = MarketState()
    state.begin_day(day, [zone])
    state.record_closed_candle(
        Candle.from_values(broker_day=day, open="95", high="99", low="90", close="98")
    )
    state.begin_bar("99", bar_id="2026-09-06T10:00")
    state.process_tick(previous_bid="99", bid="100")
    state.process_tick(previous_bid="100", bid="102.01")

    update = state.close_bar(
        Candle.from_values(
            broker_day=day,
            open="99",
            high="103",
            low="99",
            close="102.01",
        )
    )

    assert update.bar_id == "2026-09-06T10:00"
    assert len(update.breakouts) == 1
    assert update.breakouts[0].breakout_id == "BO1"
    assert update.breakouts[0].direction is TradeDirection.BUY
    assert state.trend.reference_count == 2
    with pytest.raises(RuntimeError, match="initialized"):
        state.close_bar(
            Candle.from_values(
                broker_day=day,
                open="99",
                high="103",
                low="99",
                close="102.01",
            )
        )


def test_market_state_rejects_non_causal_tick_chain_and_close() -> None:
    day = date(2026, 9, 6)
    state = MarketState()
    state.begin_day(day, [])
    state.begin_bar("100", bar_id="b1")
    with pytest.raises(ValueError, match="Previous Bid"):
        state.process_tick(previous_bid="99", bid="101")
    state.process_tick(previous_bid="100", bid="101")
    with pytest.raises(ValueError, match="Candle Close"):
        state.close_bar(
            Candle.from_values(
                broker_day=day,
                open="100",
                high="102",
                low="100",
                close="102",
            )
        )


def test_breakout_arms_pullback_and_shares_entry_attempt_slot_with_reversal() -> None:
    day = date(2026, 9, 6)
    zone = build_daily_zones(
        [
            RawZone.from_values(
                broker_day=day,
                low="100",
                high="101",
                priority="normal",
                source_row=1,
            )
        ]
    )[day][0]
    state = MarketState()
    state.begin_day(day, [zone])
    state.record_closed_candle(
        Candle.from_values(broker_day=day, open="95", high="99", low="90", close="98")
    )
    state.begin_bar("99", bar_id="t")
    state.process_tick(previous_bid="99", bid="100")
    state.process_tick(previous_bid="100", bid="102.01")
    state.close_bar(
        Candle.from_values(broker_day=day, open="99", high="103", low="99", close="102.01")
    )

    assert state.begin_bar("102.01", bar_id="t+1") == ()
    pullback = state.process_tick(previous_bid="102.01", bid="100.80").pullback_candidates[0]
    assert pullback.parent_breakout_id == "BO1"
    assert pullback.entry_price == zone.high
    assert state.pullbacks.record_pending_order_attempt(pullback, broker_accepted=True).sent

    state.process_tick(previous_bid="100.80", bid="99")
    reversal = state.process_tick(previous_bid="99", bid="100").reversal_candidates[0]
    blocked = state.reversals.record_market_order_attempt(reversal, broker_accepted=True)
    assert not blocked.sent
    assert blocked.rejection_reason == "entry_attempt_already_used"

    expiries = state.begin_day(date(2026, 9, 7), [])
    assert len(expiries) == 1
    assert expiries[0].pending_order_must_cancel
    assert expiries[0].reason == "broker_day_changed"
