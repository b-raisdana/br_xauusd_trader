from datetime import date
from decimal import Decimal

from xauusd.momentum import (
    PreZoneTriggerTracker,
    PullbackTpState,
    TpActionType,
    blocks_opposite_reversal,
    pre_zone_trigger_price,
    strict_pullback_trend,
)
from xauusd.signals import TradeDirection
from xauusd.trend import Candle
from xauusd.zones import RawZone, Zone, build_daily_zones

DAY = date(2026, 9, 6)


def zones() -> tuple[Zone, ...]:
    return build_daily_zones(
        [
            RawZone.from_values(
                broker_day=DAY,
                low="100",
                high="101",
                priority="normal",
                source_row=1,
            ),
            RawZone.from_values(
                broker_day=DAY,
                low="110",
                high="111",
                priority="normal",
                source_row=2,
            ),
        ]
    )[DAY]


def candle(open_: str, close: str) -> Candle:
    open_price = Decimal(open_)
    close_price = Decimal(close)
    return Candle.from_values(
        broker_day=DAY,
        open=open_,
        high=max(open_price, close_price) + 1,
        low=min(open_price, close_price) - 1,
        close=close,
    )


def test_strict_trend_checks_closed_and_current_candle_including_same_bar() -> None:
    bullish = candle("100", "101")
    bearish = candle("101", "100")
    doji = candle("100", "100")

    assert strict_pullback_trend(
        direction=TradeDirection.BUY,
        closed_after_pullback=[],
        current_open="100",
        current_bid="100.01",
        current_ask="100.02",
    )
    assert not strict_pullback_trend(
        direction=TradeDirection.BUY,
        closed_after_pullback=[bullish, doji],
        current_open="100",
        current_bid="101",
        current_ask="101.01",
    )
    assert strict_pullback_trend(
        direction=TradeDirection.SELL,
        closed_after_pullback=[bearish],
        current_open="100",
        current_bid="98.99",
        current_ask="99",
    )
    assert not strict_pullback_trend(
        direction=TradeDirection.SELL,
        closed_after_pullback=[bearish],
        current_open="100",
        current_bid="100",
        current_ask="100",
    )


def test_pre_zone_trigger_uses_target_edge_first_crossing_and_accepts_gap() -> None:
    lower, upper = zones()
    tracker = PreZoneTriggerTracker()
    assert pre_zone_trigger_price(TradeDirection.BUY, upper) == 109
    assert tracker.crossed(
        position_id="p1",
        direction=TradeDirection.BUY,
        target_zone=upper,
        previous_price="108",
        current_price="110",
    )
    assert not tracker.crossed(
        position_id="p1",
        direction=TradeDirection.BUY,
        target_zone=upper,
        previous_price="108",
        current_price="109",
    )
    assert pre_zone_trigger_price(TradeDirection.SELL, lower) == 102
    assert tracker.crossed(
        position_id="p2",
        direction=TradeDirection.SELL,
        target_zone=lower,
        previous_price="103",
        current_price="101",
    )


def test_opposite_reversal_blocks_only_on_actual_touch_with_strict_trend() -> None:
    assert blocks_opposite_reversal(actual_zone_touch=True, strict_trend_valid=True)
    assert not blocks_opposite_reversal(actual_zone_touch=False, strict_trend_valid=True)
    assert not blocks_opposite_reversal(actual_zone_touch=True, strict_trend_valid=False)


def test_tp_extension_is_one_step_and_failed_modify_preserves_initial_tp() -> None:
    initial, next_zone = zones()
    state = PullbackTpState.create(
        position_id="p1",
        direction=TradeDirection.BUY,
        initial_target_zone=initial,
    )
    action = state.propose_extension(
        approached_zone=initial,
        next_zone=next_zone,
        strict_trend_valid=True,
    )
    assert action.action is TpActionType.MODIFY
    assert action.requested_tp == next_zone.low
    state.record_extension_result(action, broker_accepted=False)
    assert state.current_tp == initial.low
    assert not state.extended
    retry = state.propose_extension(
        approached_zone=initial,
        next_zone=next_zone,
        strict_trend_valid=True,
    )
    assert retry.action is TpActionType.MODIFY
    state.record_extension_result(retry, broker_accepted=True)
    assert state.current_tp == next_zone.low
    assert (
        state.propose_extension(
            approached_zone=next_zone,
            next_zone=None,
            strict_trend_valid=True,
        ).action
        is TpActionType.NONE
    )


def test_tp_restores_before_initial_target_and_market_closes_after_crossing() -> None:
    initial, next_zone = zones()
    state = PullbackTpState.create(
        position_id="p1",
        direction=TradeDirection.BUY,
        initial_target_zone=initial,
    )
    extension = state.propose_extension(
        approached_zone=initial,
        next_zone=next_zone,
        strict_trend_valid=True,
    )
    state.record_extension_result(extension, broker_accepted=True)
    restore = state.evaluate_strict_failure(
        strict_trend_valid=False,
        current_bid="99",
        current_ask="99.01",
    )
    assert restore.action is TpActionType.RESTORE
    state.record_restore_result(broker_accepted=False)
    assert state.current_tp == next_zone.low
    state.record_restore_result(broker_accepted=True)
    assert state.current_tp == initial.low

    second = PullbackTpState.create(
        position_id="p2",
        direction=TradeDirection.BUY,
        initial_target_zone=initial,
    )
    action = second.propose_extension(
        approached_zone=initial,
        next_zone=next_zone,
        strict_trend_valid=True,
    )
    second.record_extension_result(action, broker_accepted=True)
    close = second.evaluate_strict_failure(
        strict_trend_valid=False,
        current_bid="100",
        current_ask="100.01",
    )
    assert close.action is TpActionType.MARKET_CLOSE

    sell = PullbackTpState.create(
        position_id="p3",
        direction=TradeDirection.SELL,
        initial_target_zone=next_zone,
    )
    sell_extension = sell.propose_extension(
        approached_zone=next_zone,
        next_zone=initial,
        strict_trend_valid=True,
    )
    assert sell_extension.requested_tp == initial.high
    sell.record_extension_result(sell_extension, broker_accepted=True)
    assert (
        sell.evaluate_strict_failure(
            strict_trend_valid=False,
            current_bid="112",
            current_ask="112",
        ).action
        is TpActionType.RESTORE
    )
    assert (
        sell.evaluate_strict_failure(
            strict_trend_valid=False,
            current_bid="110",
            current_ask="111",
        ).action
        is TpActionType.MARKET_CLOSE
    )
