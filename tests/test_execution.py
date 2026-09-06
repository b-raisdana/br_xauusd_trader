from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from xauusd.audit import AuditEventKind, AuditJournal, SignalFamily
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
