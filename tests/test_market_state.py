from datetime import date

from xauusd.market_state import MarketState
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
    state.begin_bar("99")

    update = state.process_tick(previous_bid="99", bid="101")

    assert update.trend.current is TrendState.UP
    assert update.trend.changed
    assert [(event.zone_id, event.side) for event in update.engagement.events] == [
        (zone.zone_id, BreakoutSide.BUY)
    ]
