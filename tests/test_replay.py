from datetime import date, datetime

import pytest

from xauusd.audit import AuditJournal, SignalFamily
from xauusd.market_state import MarketState
from xauusd.replay import ReplayBar, ReplayDay, ReplayRunner, ReplayTick
from xauusd.trend import Candle
from xauusd.zones import RawZone, build_daily_zones


def test_replay_routes_causal_signals_to_audit() -> None:
    day = date(2026, 9, 6)
    zone = build_daily_zones(
        [
            RawZone.from_values(
                broker_day=day, low="100", high="101", priority="normal", source_row=1
            )
        ]
    )[day][0]
    seed = Candle.from_values(broker_day=day, open="95", high="99", low="90", close="98")
    bar = ReplayBar.from_values(
        bar_id="t",
        open_time=datetime(2026, 9, 6, 10),
        close_time=datetime(2026, 9, 6, 10, 15),
        open_bid="99",
        candle=Candle.from_values(broker_day=day, open="99", high="103", low="99", close="102.01"),
        ticks=(
            ReplayTick.from_values(broker_time=datetime(2026, 9, 6, 10, 1), bid="100"),
            ReplayTick.from_values(broker_time=datetime(2026, 9, 6, 10, 14), bid="102.01"),
        ),
    )
    result = ReplayRunner(MarketState(), AuditJournal()).run_day(
        ReplayDay(day, (zone,), (seed,), (bar,))
    )

    assert [event.signal_family for event in result.events] == [
        SignalFamily.REVERSAL,
        SignalFamily.BREAKOUT,
    ]
    assert result.pullback_expiries == ()


def test_replay_rejects_non_causal_time_and_close() -> None:
    day = date(2026, 9, 6)
    candle = Candle.from_values(broker_day=day, open="100", high="102", low="100", close="101")
    invalid = ReplayBar.from_values(
        bar_id="b1",
        open_time=datetime(2026, 9, 6, 10),
        close_time=datetime(2026, 9, 6, 10, 15),
        open_bid="100",
        candle=candle,
        ticks=(ReplayTick.from_values(broker_time=datetime(2026, 9, 6, 9, 59), bid="102"),),
    )
    with pytest.raises(ValueError, match="chronological"):
        ReplayRunner(MarketState(), AuditJournal()).run_day(ReplayDay(day, (), (), (invalid,)))

    mismatch = ReplayBar.from_values(
        bar_id="b1",
        open_time=datetime(2026, 9, 6, 10),
        close_time=datetime(2026, 9, 6, 10, 15),
        open_bid="100",
        candle=candle,
        ticks=(ReplayTick.from_values(broker_time=datetime(2026, 9, 6, 10, 1), bid="102"),),
    )
    with pytest.raises(ValueError, match="final Bid"):
        ReplayRunner(MarketState(), AuditJournal()).run_day(ReplayDay(day, (), (), (mismatch,)))
