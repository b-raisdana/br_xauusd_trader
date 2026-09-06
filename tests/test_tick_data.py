from datetime import timedelta

import pytest

from xauusd.audit import AuditJournal
from xauusd.market_state import MarketState
from xauusd.replay import ReplayDay, ReplayRunner
from xauusd.tick_data import load_mt5_tick_bars


def test_mt5_ticks_normalize_to_explicit_broker_m15_and_replay(tmp_path) -> None:
    source = tmp_path / "ticks.csv"
    source.write_text(
        "time_msc,bid\n1787911200030,100\n1787911200030,101\n1787911250000,100.5\n",
        encoding="utf-8",
    )
    bars = load_mt5_tick_bars(source, broker_utc_offset=timedelta(hours=3, minutes=30))

    assert len(bars) == 1
    assert bars[0].open_time.hour == 13
    assert bars[0].open_time.minute == 30
    assert bars[0].candle.open == 100
    assert bars[0].candle.high == 101
    assert bars[0].candle.close == pytest.approx(100.5)
    result = ReplayRunner(MarketState(), AuditJournal()).run_day(
        ReplayDay(bars[0].candle.broker_day, (), (), bars)
    )
    assert result.events == ()


def test_mt5_tick_normalization_rejects_backward_time_and_invalid_offset(tmp_path) -> None:
    source = tmp_path / "ticks.csv"
    source.write_text("time_msc,bid\n2,100\n1,101\n", encoding="utf-8")
    with pytest.raises(ValueError, match="backward"):
        load_mt5_tick_bars(source, broker_utc_offset=timedelta(0))
    with pytest.raises(ValueError, match="whole minutes"):
        load_mt5_tick_bars(source, broker_utc_offset=timedelta(seconds=1))
