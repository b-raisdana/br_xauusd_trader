from dataclasses import FrozenInstanceError
from datetime import date, datetime
from decimal import Decimal

import pytest

from xauusd.audit import (
    AuditEventKind,
    AuditJournal,
    AuditPersistenceError,
    JsonlAuditStore,
    SignalFamily,
    chart_marker,
)
from xauusd.signals import OrderType, TradeDirection
from xauusd.zones import ZonePriority

DAY = date(2026, 9, 6)
NOW = datetime(2026, 9, 6, 10, 15)


def test_journal_assigns_stable_daily_ids_and_serializes_exact_prices() -> None:
    journal = AuditJournal()
    journal.begin_day(DAY)
    event = journal.record(
        rule_ids=("BREAKOUT_VALIDATION",),
        kind=AuditEventKind.SIGNAL,
        broker_time=NOW,
        zone_id="2026-09-06:R1",
        signal_family=SignalFamily.BREAKOUT,
        direction=TradeDirection.BUY,
        entry="3400.10",
        stop_loss="3396",
        take_profit="3408",
    )
    assert event.event_id == "2026-09-06:E000001"
    assert event.to_dict()["entry"] == "3400.10"
    assert event.to_dict()["close_price"] is None
    assert journal.events == (event,)
    with pytest.raises(FrozenInstanceError):
        event.reason = "changed"  # type: ignore[misc]

    journal.begin_day(date(2026, 9, 7))
    next_event = journal.record(
        rule_ids=("REVERSAL_DIRECTIONAL_TOUCH",),
        kind=AuditEventKind.SIGNAL,
        broker_time=datetime(2026, 9, 7, 9),
        zone_id="2026-09-07:R1",
        signal_family=SignalFamily.REVERSAL,
        direction=TradeDirection.SELL,
    )
    assert next_event.event_id == "2026-09-07:E000001"


def test_order_pullback_and_rejection_fields_are_enforced() -> None:
    journal = AuditJournal()
    journal.begin_day(DAY)
    with pytest.raises(ValueError, match="Order Type"):
        journal.record(
            rule_ids=("ORDER_PROTECTED_FROM_CREATION",),
            kind=AuditEventKind.ORDER,
            broker_time=NOW,
            zone_id="z1",
            signal_family=SignalFamily.REVERSAL,
            direction=TradeDirection.BUY,
        )
    with pytest.raises(ValueError, match="parent Breakout"):
        journal.record(
            rule_ids=("PULLBACK_MULTI_PER_BREAKOUT",),
            kind=AuditEventKind.FILL,
            broker_time=NOW,
            zone_id="z1",
            signal_family=SignalFamily.PULLBACK,
            direction=TradeDirection.BUY,
        )
    with pytest.raises(ValueError, match="reason"):
        journal.record(
            rule_ids=("FREE_SPACE_MINIMUM",),
            kind=AuditEventKind.REJECT,
            broker_time=NOW,
            zone_id="z1",
            signal_family=SignalFamily.REVERSAL,
            direction=TradeDirection.BUY,
        )

    event = journal.record(
        rule_ids=("PULLBACK_CONSERVATIVE_ENTRY", "ORDER_PROTECTED_FROM_CREATION"),
        kind=AuditEventKind.ORDER,
        broker_time=NOW,
        zone_id="z1",
        signal_family=SignalFamily.PULLBACK,
        direction=TradeDirection.BUY,
        entry="100",
        stop_loss="96",
        take_profit="108",
        order_type=OrderType.PENDING_STOP,
        parent_breakout_id="BO1",
    )
    assert event.parent_breakout_id == "BO1"


def test_chart_marker_has_rule_labels_priority_style_and_leader_tooltip() -> None:
    journal = AuditJournal()
    journal.begin_day(DAY)
    event = journal.record(
        rule_ids=("REVERSAL_DIRECTIONAL_TOUCH",),
        kind=AuditEventKind.FILL,
        broker_time=NOW,
        zone_id="z1",
        signal_family=SignalFamily.REVERSAL,
        direction=TradeDirection.SELL,
        entry=Decimal("100.5"),
        stop_loss="106",
        take_profit="90",
    )
    marker = chart_marker(event, ZonePriority.HIGH)
    assert marker.label == "R-S"
    assert marker.color_key == "zone_high"
    for expected in ("Time=", "Zone=z1", "Entry=100.5", "SL=106", "TP=90", "Event="):
        assert expected in marker.tooltip


def test_jsonl_journal_is_durable_and_resumes_daily_sequence(tmp_path) -> None:
    path = tmp_path / "audit" / "events.jsonl"
    first = AuditJournal(JsonlAuditStore(path))
    first.begin_day(DAY)
    first.record(
        rule_ids=("BREAKOUT_VALIDATION",),
        kind=AuditEventKind.SIGNAL,
        broker_time=NOW,
        zone_id="2026-09-06:R1",
        signal_family=SignalFamily.BREAKOUT,
        direction=TradeDirection.BUY,
        entry="3400.10",
    )

    resumed = AuditJournal(JsonlAuditStore(path))
    resumed.begin_day(DAY)
    event = resumed.record(
        rule_ids=("REVERSAL_DIRECTIONAL_TOUCH",),
        kind=AuditEventKind.SIGNAL,
        broker_time=datetime(2026, 9, 6, 10, 16),
        zone_id="2026-09-06:R2",
        signal_family=SignalFamily.REVERSAL,
        direction=TradeDirection.SELL,
        entry="3401.20",
    )

    assert event.event_id == "2026-09-06:E000002"
    records = path.read_text(encoding="utf-8").splitlines()
    assert len(records) == 2
    assert '"entry":"3400.10"' in records[0]


def test_jsonl_journal_fails_closed_on_corrupt_or_gapped_history(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.jsonl"
    corrupt.write_text('{"event_id":"2026-09-06:E000001"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(AuditPersistenceError, match="Cannot recover"):
        AuditJournal(JsonlAuditStore(corrupt)).begin_day(DAY)

    gapped = tmp_path / "gapped.jsonl"
    gapped.write_text(
        '{"event_id":"2026-09-06:E000001"}\n{"event_id":"2026-09-06:E000003"}\n',
        encoding="utf-8",
    )
    with pytest.raises(AuditPersistenceError, match="Non-contiguous"):
        AuditJournal(JsonlAuditStore(gapped)).begin_day(DAY)


def test_failed_durable_append_does_not_publish_or_consume_event_id() -> None:
    class FailingStore:
        def last_sequence(self, broker_day: date) -> int:
            return 0

        def append(self, event: object) -> None:
            raise AuditPersistenceError("disk unavailable")

    journal = AuditJournal(FailingStore())
    journal.begin_day(DAY)
    with pytest.raises(AuditPersistenceError, match="disk unavailable"):
        journal.record(
            rule_ids=("BREAKOUT_VALIDATION",),
            kind=AuditEventKind.SIGNAL,
            broker_time=NOW,
            zone_id="z1",
            signal_family=SignalFamily.BREAKOUT,
            direction=TradeDirection.BUY,
        )
    assert journal.events == ()
