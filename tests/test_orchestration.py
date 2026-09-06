from datetime import date, datetime

from xauusd.audit import AuditJournal, JsonlAuditStore, SignalFamily
from xauusd.market_state import MarketState
from xauusd.orchestration import MarketAuditProjector
from xauusd.signals import OrderType
from xauusd.trend import Candle
from xauusd.zones import RawZone, build_daily_zones


def test_market_outputs_project_once_into_durable_audit_stream(tmp_path) -> None:
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
    journal = AuditJournal(JsonlAuditStore(tmp_path / "events.jsonl"))
    projector = MarketAuditProjector(journal)
    state.begin_day(day, [zone])
    projector.begin_day(day)
    state.record_closed_candle(
        Candle.from_values(broker_day=day, open="95", high="99", low="90", close="98")
    )

    state.begin_bar("99", bar_id="t")
    reversal_update = state.process_tick(previous_bid="99", bid="100")
    reversal_events = projector.record_tick(
        reversal_update, broker_time=datetime(2026, 9, 6, 10, 1)
    )
    assert projector.record_tick(reversal_update, broker_time=datetime(2026, 9, 6, 10, 1)) == ()
    state.process_tick(previous_bid="100", bid="102.01")
    close_update = state.close_bar(
        Candle.from_values(broker_day=day, open="99", high="103", low="99", close="102.01")
    )
    breakout_events = projector.record_bar_close(
        close_update, broker_time=datetime(2026, 9, 6, 10, 15)
    )

    state.begin_bar("102.01", bar_id="t+1")
    pullback_update = state.process_tick(previous_bid="102.01", bid="100.80")
    pullback_events = projector.record_tick(
        pullback_update, broker_time=datetime(2026, 9, 6, 10, 16)
    )

    assert [event.signal_family for event in journal.events] == [
        SignalFamily.REVERSAL,
        SignalFamily.BREAKOUT,
        SignalFamily.PULLBACK,
    ]
    assert reversal_events[0].order_type is OrderType.MARKET
    assert breakout_events[0].rule_ids == ("BREAKOUT_VALIDATION", "ZONE_ENGAGEMENT")
    assert pullback_events[0].order_type is OrderType.PENDING_STOP
    assert pullback_events[0].parent_breakout_id == "BO1"
    assert len((tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 3
