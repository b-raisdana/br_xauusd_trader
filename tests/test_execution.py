from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from xauusd.audit import (
    AuditEvent,
    AuditEventKind,
    AuditJournal,
    AuditPersistenceError,
    SignalFamily,
)
from xauusd.execution import ExecutionLedger, ExecutionRequest, ExecutionStatus
from xauusd.signals import OrderType, TradeDirection

DAY = date(2026, 9, 6)
NOW = datetime(2026, 9, 6, 10)


def request(*, family: SignalFamily = SignalFamily.REVERSAL) -> ExecutionRequest:
    return ExecutionRequest.from_values(
        request_id="REQ1",
        broker_time=NOW,
        zone_id="2026-09-06:R2",
        signal_family=family,
        direction=TradeDirection.BUY,
        order_type=OrderType.MARKET if family is SignalFamily.REVERSAL else OrderType.PENDING_STOP,
        entry="100",
        stop_loss="96",
        take_profit="108",
        rule_ids=("REVERSAL_DIRECTIONAL_TOUCH",),
        parent_breakout_id="BO1" if family is SignalFamily.PULLBACK else None,
    )


def test_protected_request_projects_order_then_fill_with_trace_id() -> None:
    journal = AuditJournal()
    ledger = ExecutionLedger(journal)
    ledger.begin_day(DAY)

    order = ledger.submit(request())
    fill = ledger.fill("REQ1", broker_time=NOW + timedelta(seconds=1), fill_price="100.1")

    assert [event.kind for event in journal.events] == [AuditEventKind.ORDER, AuditEventKind.FILL]
    assert order.execution_request_id == fill.execution_request_id == "REQ1"
    assert fill.entry == Decimal("100.1")
    assert fill.stop_loss == Decimal("96")
    assert fill.take_profit == Decimal("108")
    assert fill.to_dict()["execution_request_id"] == "REQ1"
    assert ledger.record("REQ1").status is ExecutionStatus.FILLED


def test_reject_is_terminal_and_preserves_pullback_lineage() -> None:
    journal = AuditJournal()
    ledger = ExecutionLedger(journal)
    ledger.begin_day(DAY)
    ledger.submit(request(family=SignalFamily.PULLBACK))

    rejected = ledger.reject("REQ1", broker_time=NOW, reason="native_reject")

    assert rejected.kind is AuditEventKind.REJECT
    assert rejected.parent_breakout_id == "BO1"
    assert rejected.reason == "native_reject"
    assert ledger.record("REQ1").status is ExecutionStatus.REJECTED
    with pytest.raises(ValueError, match="already resolved"):
        ledger.fill("REQ1", broker_time=NOW, fill_price="100")


def test_execution_lifecycle_rejects_duplicates_and_backward_outcomes() -> None:
    ledger = ExecutionLedger(AuditJournal())
    ledger.begin_day(DAY)
    ledger.submit(request())
    with pytest.raises(ValueError, match="Duplicate"):
        ledger.submit(request())
    with pytest.raises(ValueError, match="precedes"):
        ledger.reject("REQ1", broker_time=NOW - timedelta(seconds=1), reason="invalid")


def test_invalid_or_unprotected_request_fails_before_audit() -> None:
    with pytest.raises(ValueError, match="directional SL and TP"):
        ExecutionRequest.from_values(
            request_id="REQ1",
            broker_time=NOW,
            zone_id="z1",
            signal_family=SignalFamily.REVERSAL,
            direction=TradeDirection.BUY,
            order_type=OrderType.MARKET,
            entry="100",
            stop_loss="101",
            take_profit="108",
            rule_ids=("REVERSAL_DIRECTIONAL_TOUCH",),
        )


def test_failed_durable_audit_does_not_advance_execution_state() -> None:
    class FailingStore:
        def last_sequence(self, broker_day: date) -> int:
            return 0

        def append(self, event: object) -> None:
            raise OSError("disk unavailable")

    ledger = ExecutionLedger(AuditJournal(FailingStore()))
    ledger.begin_day(DAY)
    with pytest.raises(OSError, match="disk unavailable"):
        ledger.submit(request())
    with pytest.raises(ValueError, match="Unknown"):
        ledger.record("REQ1")


def test_filled_position_closes_once_with_rule_and_request_lineage() -> None:
    journal = AuditJournal()
    ledger = ExecutionLedger(journal)
    ledger.begin_day(DAY)
    ledger.submit(request(family=SignalFamily.PULLBACK))
    ledger.fill("REQ1", broker_time=NOW + timedelta(seconds=1), fill_price="100.1")

    closed = ledger.close(
        "REQ1",
        broker_time=NOW + timedelta(seconds=2),
        close_price="108.2",
        rule_ids=("EXTEND_PULLBACK_TP",),
        reason="strict_failed_after_initial_tp",
    )

    assert closed.kind is AuditEventKind.CLOSE
    assert closed.entry == Decimal("100")
    assert closed.close_price == Decimal("108.2")
    assert closed.execution_request_id == "REQ1"
    assert closed.parent_breakout_id == "BO1"
    assert "EXTEND_PULLBACK_TP" in closed.rule_ids
    assert ledger.record("REQ1").status is ExecutionStatus.CLOSED
    with pytest.raises(ValueError, match="no open filled position"):
        ledger.close(
            "REQ1",
            broker_time=NOW + timedelta(seconds=3),
            close_price="108.3",
            rule_ids=("EXTEND_PULLBACK_TP",),
            reason="duplicate",
        )


def test_close_requires_fill_and_cannot_precede_fill() -> None:
    ledger = ExecutionLedger(AuditJournal())
    ledger.begin_day(DAY)
    ledger.submit(request())
    with pytest.raises(ValueError, match="no open filled position"):
        ledger.close(
            "REQ1",
            broker_time=NOW,
            close_price="101",
            rule_ids=("BREAKOUT_VALIDATION",),
            reason="opposite_breakout",
        )
    ledger.fill("REQ1", broker_time=NOW + timedelta(seconds=2), fill_price="100")
    with pytest.raises(ValueError, match="precedes fill"):
        ledger.close(
            "REQ1",
            broker_time=NOW + timedelta(seconds=1),
            close_price="101",
            rule_ids=("BREAKOUT_VALIDATION",),
            reason="opposite_breakout",
        )


def test_failed_close_audit_keeps_filled_position_open() -> None:
    class FailCloseStore:
        def last_sequence(self, broker_day: date) -> int:
            return 0

        def append(self, event: AuditEvent) -> None:
            if event.kind is AuditEventKind.CLOSE:
                raise AuditPersistenceError("close audit unavailable")

    ledger = ExecutionLedger(AuditJournal(FailCloseStore()))
    ledger.begin_day(DAY)
    ledger.submit(request())
    ledger.fill("REQ1", broker_time=NOW, fill_price="100")
    with pytest.raises(AuditPersistenceError, match="close audit unavailable"):
        ledger.close(
            "REQ1",
            broker_time=NOW,
            close_price="101",
            rule_ids=("BREAKOUT_VALIDATION",),
            reason="opposite_breakout",
        )
    assert ledger.record("REQ1").status is ExecutionStatus.FILLED


def test_execution_state_recovers_atomically_from_typed_journal(tmp_path) -> None:
    from xauusd.audit import JsonlAuditStore

    store = JsonlAuditStore(tmp_path / "events.jsonl")
    original = ExecutionLedger(AuditJournal(store))
    original.begin_day(DAY)
    original.submit(request(family=SignalFamily.PULLBACK))
    original.fill("REQ1", broker_time=NOW, fill_price="100")
    original.close(
        "REQ1",
        broker_time=NOW,
        close_price="101",
        rule_ids=("EXTEND_PULLBACK_TP",),
        reason="strict_failed_after_initial_tp",
    )

    recovered = ExecutionLedger(AuditJournal(store))
    recovered.begin_day(DAY)
    recovered.recover(store.events_for_day(DAY))

    assert recovered.record("REQ1").status is ExecutionStatus.CLOSED
    assert recovered.record("REQ1").request.parent_breakout_id == "BO1"


def test_invalid_recovery_does_not_replace_existing_state() -> None:
    journal = AuditJournal()
    ledger = ExecutionLedger(journal)
    ledger.begin_day(DAY)
    ledger.submit(request())
    invalid_fill = journal.record(
        rule_ids=("ORDER_PROTECTED_FROM_CREATION",),
        kind=AuditEventKind.FILL,
        broker_time=NOW,
        zone_id="z2",
        signal_family=SignalFamily.REVERSAL,
        direction=TradeDirection.BUY,
        execution_request_id="UNKNOWN",
    )

    with pytest.raises(ValueError, match="has no Order"):
        ledger.recover((invalid_fill,))
    assert ledger.record("REQ1").status is ExecutionStatus.SUBMITTED


def test_modify_updates_protection_only_after_acceptance_and_never_loosens_stop() -> None:
    journal = AuditJournal()
    ledger = ExecutionLedger(journal)
    ledger.begin_day(DAY)
    ledger.submit(request())
    ledger.fill("REQ1", broker_time=NOW, fill_price="100")

    modified = ledger.modify(
        "REQ1",
        broker_time=NOW + timedelta(seconds=1),
        broker_accepted=True,
        stop_loss="97",
        rule_ids=("PROFIT_PROTECTION",),
    )
    assert modified.kind is AuditEventKind.MODIFY
    assert ledger.record("REQ1").current_stop_loss == Decimal("97")

    rejected = ledger.modify(
        "REQ1",
        broker_time=NOW + timedelta(seconds=2),
        broker_accepted=False,
        take_profit="110",
        rule_ids=("EXTEND_PULLBACK_TP",),
        rejection_reason="native_modify_reject",
    )
    assert rejected.kind is AuditEventKind.MODIFY_REJECT
    assert rejected.take_profit == Decimal("110")
    assert ledger.record("REQ1").current_take_profit == Decimal("108")

    with pytest.raises(ValueError, match="loosen SL"):
        ledger.modify(
            "REQ1",
            broker_time=NOW + timedelta(seconds=3),
            broker_accepted=True,
            stop_loss="96",
            rule_ids=("PROFIT_PROTECTION",),
        )


def test_pending_cancel_reject_preserves_order_and_acceptance_is_terminal() -> None:
    ledger = ExecutionLedger(AuditJournal())
    ledger.begin_day(DAY)
    ledger.submit(request(family=SignalFamily.PULLBACK))

    rejected = ledger.cancel_pending(
        "REQ1",
        broker_time=NOW,
        broker_accepted=False,
        rule_ids=("SESSION_END_FLATTEN",),
        reason="native_cancel_reject",
    )
    assert rejected.kind is AuditEventKind.CANCEL_REJECT
    assert ledger.record("REQ1").status is ExecutionStatus.SUBMITTED

    cancelled = ledger.cancel_pending(
        "REQ1",
        broker_time=NOW + timedelta(seconds=1),
        broker_accepted=True,
        rule_ids=("SESSION_END_FLATTEN",),
        reason="session_end",
    )
    assert cancelled.kind is AuditEventKind.CANCEL
    assert ledger.record("REQ1").status is ExecutionStatus.CANCELLED
    with pytest.raises(ValueError, match="already resolved"):
        ledger.cancel_pending(
            "REQ1",
            broker_time=NOW + timedelta(seconds=2),
            broker_accepted=True,
            rule_ids=("SESSION_END_FLATTEN",),
            reason="duplicate",
        )


def test_market_order_cannot_use_pending_cancel_lifecycle() -> None:
    ledger = ExecutionLedger(AuditJournal())
    ledger.begin_day(DAY)
    ledger.submit(request())
    with pytest.raises(ValueError, match="Only a Pending"):
        ledger.cancel_pending(
            "REQ1",
            broker_time=NOW,
            broker_accepted=True,
            rule_ids=("SESSION_END_FLATTEN",),
            reason="invalid",
        )


def test_modify_and_cancel_states_recover_from_durable_events(tmp_path) -> None:
    from xauusd.audit import JsonlAuditStore

    store = JsonlAuditStore(tmp_path / "events.jsonl")
    original = ExecutionLedger(AuditJournal(store))
    original.begin_day(DAY)
    original.submit(request())
    original.fill("REQ1", broker_time=NOW, fill_price="100")
    original.modify(
        "REQ1",
        broker_time=NOW,
        broker_accepted=True,
        stop_loss="97",
        rule_ids=("PROFIT_PROTECTION",),
    )
    pending = replace(request(family=SignalFamily.PULLBACK), request_id="REQ2")
    original.submit(pending)
    original.cancel_pending(
        "REQ2",
        broker_time=NOW,
        broker_accepted=True,
        rule_ids=("SESSION_END_FLATTEN",),
        reason="session_end",
    )

    recovered = ExecutionLedger(AuditJournal(store))
    recovered.begin_day(DAY)
    recovered.recover(store.events_for_day(DAY))

    assert recovered.record("REQ1").current_stop_loss == Decimal("97")
    assert recovered.record("REQ1").status is ExecutionStatus.FILLED
    assert recovered.record("REQ2").status is ExecutionStatus.CANCELLED


def test_recovery_rejects_audit_modify_that_loosens_stop() -> None:
    journal = AuditJournal()
    original = ExecutionLedger(journal)
    original.begin_day(DAY)
    original.submit(request())
    original.fill("REQ1", broker_time=NOW, fill_price="100")
    invalid_modify = replace(
        journal.events[-1],
        event_id="2026-09-06:E000003",
        kind=AuditEventKind.MODIFY,
        stop_loss=Decimal("95"),
        take_profit=Decimal("108"),
    )

    recovered = ExecutionLedger(AuditJournal())
    recovered.begin_day(DAY)
    with pytest.raises(ValueError, match="loosen SL"):
        recovered.recover((*journal.events, invalid_modify))
    with pytest.raises(ValueError, match="Unknown"):
        recovered.record("REQ1")
