from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from xauusd.audit import AuditEventKind, AuditJournal, SignalFamily
from xauusd.market_state import MarketState
from xauusd.replay import (
    ReplayBar,
    ReplayCancelOutcome,
    ReplayCloseOutcome,
    ReplayDay,
    ReplayExecutionOutcome,
    ReplayModifyOutcome,
    ReplayRunner,
    ReplayTick,
    build_replay_days,
)
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


def test_build_replay_days_attaches_daily_zones_and_sorts_bars() -> None:
    day = date(2026, 9, 6)
    zone = build_daily_zones(
        [
            RawZone.from_values(
                broker_day=day, low="100", high="101", priority="normal", source_row=2
            )
        ]
    )[day][0]
    candle = Candle.from_values(broker_day=day, open="100", high="101", low="100", close="100")
    later = ReplayBar.from_values(
        bar_id="later",
        open_time=datetime(2026, 9, 6, 10, 15),
        close_time=datetime(2026, 9, 6, 10, 30),
        open_bid="100",
        candle=candle,
        ticks=(),
    )
    earlier = ReplayBar.from_values(
        bar_id="earlier",
        open_time=datetime(2026, 9, 6, 10),
        close_time=datetime(2026, 9, 6, 10, 15),
        open_bid="100",
        candle=candle,
        ticks=(),
    )

    replay_days = build_replay_days((later, earlier), {day: (zone,)})

    assert len(replay_days) == 1
    assert replay_days[0].zones == (zone,)
    assert [bar.bar_id for bar in replay_days[0].bars] == ["earlier", "later"]


def test_build_replay_days_fails_closed_when_daily_zones_are_missing() -> None:
    day = date(2026, 9, 6)
    candle = Candle.from_values(broker_day=day, open="100", high="100", low="100", close="100")
    bar = ReplayBar.from_values(
        bar_id="b1",
        open_time=datetime(2026, 9, 6, 10),
        close_time=datetime(2026, 9, 6, 10, 15),
        open_bid="100",
        candle=candle,
        ticks=(),
    )

    with pytest.raises(ValueError, match="Missing daily Zone input.*2026-09-06"):
        build_replay_days((bar,), {})


def execution_replay(outcome: ReplayExecutionOutcome) -> ReplayDay:
    day = date(2026, 9, 6)
    zones = build_daily_zones(
        [
            RawZone.from_values(
                broker_day=day, low="90", high="91", priority="normal", source_row=1
            ),
            RawZone.from_values(
                broker_day=day, low="100", high="101", priority="normal", source_row=2
            ),
            RawZone.from_values(
                broker_day=day, low="110", high="111", priority="normal", source_row=3
            ),
        ]
    )[day]
    bar = ReplayBar.from_values(
        bar_id="t",
        open_time=datetime(2026, 9, 6, 10),
        close_time=datetime(2026, 9, 6, 10, 15),
        open_bid="99",
        candle=Candle.from_values(broker_day=day, open="99", high="103", low="99", close="102.01"),
        ticks=(
            ReplayTick.from_values(
                broker_time=datetime(2026, 9, 6, 10, 1),
                bid="100",
                execution_outcomes=(outcome,),
            ),
            ReplayTick.from_values(broker_time=datetime(2026, 9, 6, 10, 14), bid="102.01"),
        ),
    )
    seed = Candle.from_values(broker_day=day, open="95", high="99", low="90", close="98")
    return ReplayDay(day, zones, (seed,), (bar,))


def test_replay_applies_explicit_market_fill_without_inferring_broker_behavior() -> None:
    candidate_id = "t:R:2026-09-06:R2:sell"
    outcome = ReplayExecutionOutcome.from_values(
        candidate_id=candidate_id,
        broker_time=datetime(2026, 9, 6, 10, 1, 1),
        accepted=True,
        fill_price="100.1",
    )

    result = ReplayRunner(MarketState(), AuditJournal()).run_day(execution_replay(outcome))

    assert [event.kind for event in result.events] == [
        AuditEventKind.SIGNAL,
        AuditEventKind.ORDER,
        AuditEventKind.FILL,
        AuditEventKind.SIGNAL,
    ]
    assert result.events[1].execution_request_id == candidate_id
    assert result.events[2].entry == Decimal("100.1")


def test_replay_applies_explicit_broker_reject_and_rejects_unknown_fixture() -> None:
    candidate_id = "t:R:2026-09-06:R2:sell"
    rejected = ReplayExecutionOutcome.from_values(
        candidate_id=candidate_id,
        broker_time=datetime(2026, 9, 6, 10, 1, 1),
        accepted=False,
        rejection_reason="native_reject",
    )
    result = ReplayRunner(MarketState(), AuditJournal()).run_day(execution_replay(rejected))
    assert [event.kind for event in result.events[:3]] == [
        AuditEventKind.SIGNAL,
        AuditEventKind.ORDER,
        AuditEventKind.REJECT,
    ]

    unknown = ReplayExecutionOutcome.from_values(
        candidate_id="unknown",
        broker_time=datetime(2026, 9, 6, 10, 1),
        accepted=False,
        rejection_reason="unused",
    )
    with pytest.raises(ValueError, match="no candidate"):
        ReplayRunner(MarketState(), AuditJournal()).run_day(execution_replay(unknown))


def test_invalid_market_outcome_fails_before_consuming_signal_capacity() -> None:
    invalid = ReplayExecutionOutcome.from_values(
        candidate_id="t:R:2026-09-06:R2:sell",
        broker_time=datetime(2026, 9, 6, 10, 1),
        accepted=True,
    )
    state = MarketState()
    with pytest.raises(ValueError, match="requires a fill price"):
        ReplayRunner(state, AuditJournal()).run_day(execution_replay(invalid))
    assert state.reversals.daily_usage("2026-09-06:R2") == 0


def test_replay_applies_explicit_pullback_pending_fill_and_usage() -> None:
    day = date(2026, 9, 6)
    zones = build_daily_zones(
        [
            RawZone.from_values(
                broker_day=day, low="90", high="91", priority="normal", source_row=1
            ),
            RawZone.from_values(
                broker_day=day, low="100", high="101", priority="normal", source_row=2
            ),
            RawZone.from_values(
                broker_day=day, low="110", high="111", priority="normal", source_row=3
            ),
        ]
    )[day]
    breakout_bar = ReplayBar.from_values(
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
    outcome = ReplayExecutionOutcome.from_values(
        candidate_id="BO1:PB1",
        broker_time=datetime(2026, 9, 6, 10, 16, 1),
        accepted=True,
        fill_price="101",
    )
    pullback_bar = ReplayBar.from_values(
        bar_id="t+1",
        open_time=datetime(2026, 9, 6, 10, 15),
        close_time=datetime(2026, 9, 6, 10, 30),
        open_bid="102.01",
        candle=Candle.from_values(
            broker_day=day, open="102.01", high="102.01", low="100.8", close="101"
        ),
        ticks=(
            ReplayTick.from_values(
                broker_time=datetime(2026, 9, 6, 10, 16),
                bid="100.8",
                execution_outcomes=(outcome,),
            ),
            ReplayTick.from_values(broker_time=datetime(2026, 9, 6, 10, 29), bid="101"),
        ),
    )
    seed = Candle.from_values(broker_day=day, open="95", high="99", low="90", close="98")
    state = MarketState()
    runner = ReplayRunner(state, AuditJournal())

    result = runner.run_day(ReplayDay(day, zones, (seed,), (breakout_bar, pullback_bar)))

    pullback_events = [
        event for event in result.events if event.signal_family is SignalFamily.PULLBACK
    ]
    assert [event.kind for event in pullback_events] == [
        AuditEventKind.SIGNAL,
        AuditEventKind.ORDER,
        AuditEventKind.FILL,
    ]
    assert all(event.parent_breakout_id == "BO1" for event in pullback_events)
    assert state.pullbacks.daily_fills("2026-09-06:R2") == 1
    assert runner.execution.record("BO1:PB1").status.value == "filled"


def test_replay_applies_only_explicit_close_to_an_existing_fill() -> None:
    candidate_id = "t:R:2026-09-06:R2:sell"
    fill = ReplayExecutionOutcome.from_values(
        candidate_id=candidate_id,
        broker_time=datetime(2026, 9, 6, 10, 1, 1),
        accepted=True,
        fill_price="100.1",
    )
    replay = execution_replay(fill)
    close = ReplayCloseOutcome.from_values(
        request_id=candidate_id,
        broker_time=datetime(2026, 9, 6, 10, 14, 1),
        close_price="102",
        rule_ids=("SESSION_END_FLATTEN",),
        reason="fixture_session_flatten",
    )
    second_tick = replace(replay.bars[0].ticks[1], close_outcomes=(close,))
    bar = replace(replay.bars[0], ticks=(replay.bars[0].ticks[0], second_tick))

    runner = ReplayRunner(MarketState(), AuditJournal())
    result = runner.run_day(replace(replay, bars=(bar,)))

    close_events = [event for event in result.events if event.kind is AuditEventKind.CLOSE]
    assert len(close_events) == 1
    assert close_events[0].execution_request_id == candidate_id
    assert close_events[0].close_price == Decimal("102")
    assert runner.execution.record(candidate_id).status.value == "closed"


def test_replay_rejects_close_without_an_existing_fill_before_audit() -> None:
    candidate_id = "t:R:2026-09-06:R2:sell"
    rejected = ReplayExecutionOutcome.from_values(
        candidate_id=candidate_id,
        broker_time=datetime(2026, 9, 6, 10, 1, 1),
        accepted=False,
        rejection_reason="native_reject",
    )
    replay = execution_replay(rejected)
    close = ReplayCloseOutcome.from_values(
        request_id=candidate_id,
        broker_time=datetime(2026, 9, 6, 10, 14),
        close_price="102",
        rule_ids=("SESSION_END_FLATTEN",),
        reason="invalid_close",
    )
    second_tick = replace(replay.bars[0].ticks[1], close_outcomes=(close,))
    bar = replace(replay.bars[0], ticks=(replay.bars[0].ticks[0], second_tick))

    with pytest.raises(ValueError, match="no open filled position"):
        ReplayRunner(MarketState(), AuditJournal()).run_day(replace(replay, bars=(bar,)))


@pytest.mark.parametrize(
    ("accepted", "reason", "expected_kind", "expected_stop"),
    [
        (True, None, AuditEventKind.MODIFY, Decimal("105")),
        (False, "native_modify_reject", AuditEventKind.MODIFY_REJECT, Decimal("106.00")),
    ],
)
def test_replay_applies_explicit_modify_outcome_and_preserves_rejected_state(
    accepted: bool,
    reason: str | None,
    expected_kind: AuditEventKind,
    expected_stop: Decimal,
) -> None:
    candidate_id = "t:R:2026-09-06:R2:sell"
    fill = ReplayExecutionOutcome.from_values(
        candidate_id=candidate_id,
        broker_time=datetime(2026, 9, 6, 10, 1, 1),
        accepted=True,
        fill_price="100.1",
    )
    replay = execution_replay(fill)
    modify = ReplayModifyOutcome.from_values(
        request_id=candidate_id,
        broker_time=datetime(2026, 9, 6, 10, 14, 1),
        accepted=accepted,
        stop_loss="105",
        rule_ids=("PROFIT_PROTECTION",),
        rejection_reason=reason,
    )
    second_tick = replace(replay.bars[0].ticks[1], modify_outcomes=(modify,))
    bar = replace(replay.bars[0], ticks=(replay.bars[0].ticks[0], second_tick))
    runner = ReplayRunner(MarketState(), AuditJournal())

    result = runner.run_day(replace(replay, bars=(bar,)))

    assert expected_kind in [event.kind for event in result.events]
    assert runner.execution.record(candidate_id).current_stop_loss == expected_stop


@pytest.mark.parametrize(
    ("accepted", "expected_kind", "expected_status"),
    [
        (True, AuditEventKind.CANCEL, "cancelled"),
        (False, AuditEventKind.CANCEL_REJECT, "submitted"),
    ],
)
def test_replay_applies_explicit_pending_cancel_outcome(
    accepted: bool, expected_kind: AuditEventKind, expected_status: str
) -> None:
    dummy = ReplayExecutionOutcome.from_values(
        candidate_id="t:R:2026-09-06:R2:sell",
        broker_time=datetime(2026, 9, 6, 10, 1),
        accepted=False,
        rejection_reason="unused",
    )
    base = execution_replay(dummy)
    first_tick = replace(base.bars[0].ticks[0], execution_outcomes=())
    breakout_bar = replace(base.bars[0], ticks=(first_tick, base.bars[0].ticks[1]))
    pending = ReplayExecutionOutcome.from_values(
        candidate_id="BO1:PB1",
        broker_time=datetime(2026, 9, 6, 10, 16),
        accepted=True,
    )
    cancel = ReplayCancelOutcome.from_values(
        request_id="BO1:PB1",
        broker_time=datetime(2026, 9, 6, 10, 29, 1),
        accepted=accepted,
        rule_ids=("SESSION_END_FLATTEN",),
        reason="session_end" if accepted else "native_cancel_reject",
    )
    pullback_bar = ReplayBar.from_values(
        bar_id="t+1",
        open_time=datetime(2026, 9, 6, 10, 15),
        close_time=datetime(2026, 9, 6, 10, 30),
        open_bid="102.01",
        candle=Candle.from_values(
            broker_day=base.broker_day,
            open="102.01",
            high="102.01",
            low="100.8",
            close="101",
        ),
        ticks=(
            ReplayTick.from_values(
                broker_time=datetime(2026, 9, 6, 10, 16),
                bid="100.8",
                execution_outcomes=(pending,),
            ),
            ReplayTick.from_values(
                broker_time=datetime(2026, 9, 6, 10, 29),
                bid="101",
                cancel_outcomes=(cancel,),
            ),
        ),
    )
    runner = ReplayRunner(MarketState(), AuditJournal())

    result = runner.run_day(replace(base, bars=(breakout_bar, pullback_bar)))

    assert expected_kind in [event.kind for event in result.events]
    assert runner.execution.record("BO1:PB1").status.value == expected_status
