from collections import deque
from dataclasses import replace

import pandas as pd
import pytest
from test_vectorized_execution import ZONES, candidate, config, step

from application.xauusd_trading_strategy_1_vector.domain.native import (
    EA_MAGIC,
    NativeDeal,
    NativeHistoryDeal,
    NativeOperation,
    NativePosition,
    NativeView,
    RecordedEconomics,
)
from application.xauusd_trading_strategy_1_vector.domain.recording import (
    NativeRecording,
    RecordedDeal,
    RecordedInit,
    RecordedTick,
)
from application.xauusd_trading_strategy_1_vector.domain.replay import ReplayOrder
from application.xauusd_trading_strategy_1_vector.native_replay import RecordedExecutionReplay, parse_native_comment
from application.xauusd_trading_strategy_1_vector.recorded_runner import compare_checkpoints, replay_recording
from application.xauusd_trading_strategy_1_vector.trace import shared_trace
from domain.xau_usd.enums import XauExecutionStatus, XauSignalFamily
from domain.xau_usd.models import XauPullbackWindowState

TIME = pd.Timestamp("2026-09-24", tz="UTC")


def view(*, position=True, deals=()):
    positions = (
        (
            NativePosition(
                identifier=70,
                ticket=90,
                magic=EA_MAGIC,
                symbol="OTHER",
                buy=True,
                volume=0.01,
                entry=103.7,
                sl=97.1,
                tp=120,
                opened=TIME,
                comment="R|20260924|z|B",
            ),
        )
        if position
        else ()
    )
    return NativeView(balance=200, free_margin=199, positions=positions, history=tuple(deals))


def history(ticket=1, profit=0.0, commission=-0.2, magic=EA_MAGIC):
    return NativeHistoryDeal(
        ticket=ticket, position_id=70, magic=magic, profit=profit, commission=commission, swap=0, fee=-0.1
    )


def deal(entry="IN", **kwargs):
    values = dict(
        time=TIME,
        ticket=1,
        position_id=70,
        magic=EA_MAGIC,
        symbol="OTHER",
        entry=entry,
        price=103.7,
        volume=0.01,
        comment="R|20260924|z|B",
    )
    return NativeDeal(**(values | kwargs))


def replay(operations=()):
    base = config()
    inputs = base.inputs.model_copy(update={"risk_mode": "off", "one_order_per_candle": False})
    economics = RecordedEconomics(0, (), {}, {}, deque(operations), view(position=False))
    result = RecordedExecutionReplay(replace(base, inputs=inputs, economics=economics), "native")
    result._change_day("2026-09-24", ZONES, TIME)
    return result


def test_native_acceptance_does_not_invent_fill_before_callback():
    empty = view(position=False)
    operation = NativeOperation(
        operation="SUBMIT",
        target="R|20260924|z|B",
        time=TIME,
        accepted=True,
        order_ticket=80,
        after=empty,
        price=103.1,
        sl=94.1,
        tp=120,
        volume=0.01,
    )
    engine = replay([operation])
    # The sole calculation is the requested entry's native initial-risk result.
    engine.native.profits[(candidate().direction, 0.01, 103.1, 94.1)] = -9.0
    step(engine, 103, reversals=(candidate(family=XauSignalFamily.REVERSAL),))
    assert engine.requests[0].request_active
    assert shared_trace(engine.state, engine)["g_positions"] == []
    engine.on_deal(deal(), view(deals=[history()]), 103.6, 103.7)
    trace = shared_trace(engine.state, engine)
    assert not trace["g_requests"][0]["active"]
    assert trace["g_positions"][0]["position_id"] == 70
    assert trace["g_positions"][0]["position_ticket"] == 90
    assert trace["g_positions"][0]["actual_fill"] == 103.7
    assert trace["g_positions"][0]["risk_anchor_entry"] == 103.1
    engine.native.assert_consumed()


def test_missing_metadata_and_cross_symbol_callback_keep_native_defaults():
    engine = replay()
    engine.on_deal(deal(), view(deals=[history()]), 103.6, 103.7)
    position = shared_trace(engine.state, engine)["g_positions"][0]
    assert position["risk_anchor_entry"] == position["r0"] == position["initial_sl"] == 0
    assert position["reversal_ordinal"] == 0
    assert engine.state.zones[1].reversal_fill_count == 1


def test_repeated_entry_does_not_increment_track_or_quota_twice():
    engine = replay()
    for ticket in (1, 2):
        engine.on_deal(deal(ticket=ticket, volume=0.005), view(deals=[history(1), history(2)]), 103.6, 103.7)
    assert len(shared_trace(engine.state, engine)["g_positions"]) == 1
    assert engine.state.zones[1].reversal_fill_count == 1


def test_partial_exit_deactivates_track_and_repeated_exit_does_not_recount_net():
    engine = replay()
    engine.on_deal(deal(), view(deals=[history()]), 103.6, 103.7)
    native = view(deals=[history(), history(2, profit=-2), history(3, profit=99, magic=123)])
    engine.on_deal(deal("OUT", ticket=2, volume=0.005), native, 102, 102.1)
    assert engine.net_realized == pytest.approx(-2.6)
    assert engine.gross_loss == pytest.approx(2.6)
    assert not shared_trace(engine.state, engine)["g_positions"][0]["active"]
    engine.on_deal(deal("OUT", ticket=2, volume=0.005), native, 102, 102.1)
    assert engine.net_realized == pytest.approx(-2.6)
    assert len(native.positions) == 1  # Tracking closes even if the terminal still holds a partial position.


def test_inout_adds_then_closes_tracking_in_one_callback():
    engine = replay()
    engine.on_deal(deal("INOUT"), view(deals=[history(profit=5)]), 103.6, 103.7)
    assert engine.net_realized == pytest.approx(4.7)
    assert engine.state.zones[1].reversal_fill_count == 1
    assert engine.state.zones[1].reversal_usage == 0
    assert next(iter(engine.orders.values())).status == XauExecutionStatus.CLOSED


@pytest.mark.parametrize("change", [{"magic": 0}, {"ticket": 0}, {"deal_add": False}, {"history_selected": False}])
def test_native_callback_filters_ignore_unselected_or_non_ea_deals(change):
    engine = replay()
    engine.on_deal(deal(**change), view(), 103.6, 103.7)
    assert engine.orders == {}


def test_recorded_operations_fail_on_missing_or_reordered_outcomes():
    operation = NativeOperation(operation="CLOSE", target="90", time=TIME, accepted=False, after=view())
    engine = replay([operation])
    with pytest.raises(ValueError, match="mismatch"):
        engine.native.accepts("MODIFY", "90", TIME)
    with pytest.raises(ValueError, match="not consumed"):
        engine.native.assert_consumed()
    assert not engine.native.accepts("CLOSE", "90", TIME)
    with pytest.raises(ValueError, match="Missing"):
        engine.native.accepts("CLOSE", "90", TIME)


def test_native_comment_parser_preserves_permissive_source_behavior():
    assert parse_native_comment("unknown|abcdefgh|z|anything|extra") == ("unknown", "abcd-ef-gh", "z", False)
    assert parse_native_comment("R|short|z|B") is None


def test_same_comment_consumes_latest_active_request_even_for_repeated_position():
    engine = replay()
    for n in (1, 2):
        request = ReplayOrder(
            str(n),
            candidate(family=XauSignalFamily.REVERSAL, entry=100 + n),
            0.01,
            95,
            120,
            "next",
            TIME,
            broker_day="2026-09-24",
            initial_sl=95,
            r0=5 + n,
            reversal_ordinal=n,
        )
        engine.requests.append(request)
    engine.on_deal(deal(), view(deals=[history()]), 103.6, 103.7)
    assert [r.request_active for r in engine.requests] == [True, False]
    engine.on_deal(deal(ticket=2), view(deals=[history(), history(2)]), 103.6, 103.7)
    assert [r.request_active for r in engine.requests] == [False, False]
    track = shared_trace(engine.state, engine)["g_positions"][0]
    assert track["risk_anchor_entry"] == 102
    assert track["reversal_ordinal"] == 2


@pytest.mark.parametrize("fill_first", [False, True])
def test_callback_order_controls_expiry_and_late_fill_metadata(fill_first):
    empty = view(position=False)
    cancel = NativeOperation(operation="CANCEL", target="80", time=TIME, accepted=True, after=empty)
    engine = replay([] if fill_first else [cancel])
    request = ReplayOrder(
        "pending",
        candidate(family=XauSignalFamily.PULLBACK, entry=102),
        0.01,
        96,
        120,
        "next",
        TIME,
        broker_day="2026-09-24",
        initial_sl=96,
        r0=6,
        native_order_ticket=80,
    )
    engine.requests.append(request)
    engine.orders[request.request_id] = request
    cycle = XauPullbackWindowState(
        "BO1",
        ZONES[1],
        candidate().direction,
        active=True,
        broker_day="2026-09-24",
        order_ticket="pending",
        pending_active=True,
    )
    engine.state.pullbacks.append(cycle)
    callback = deal(comment="P|20260924|z|B", order_ticket=80)
    if fill_first:
        engine.on_deal(callback, view(deals=[history()]), 103.6, 103.7)
        engine._end_cycle(cycle, TIME, "WINDOW_EXPIRED")
    else:
        engine._end_cycle(cycle, TIME, "WINDOW_EXPIRED")
        assert request.request_active
        engine.on_deal(callback, view(deals=[history()]), 103.6, 103.7)
    assert not cycle.active
    assert cycle.order_ticket == ("" if fill_first else "pending")
    assert engine.state.zones[1].pullback_fills == 1
    assert not request.request_active
    engine.native.assert_consumed()


def test_successful_close_waits_for_native_exit_callback():
    terminal = view(deals=[history()])
    outcome = NativeOperation(operation="CLOSE", target="90", time=TIME, accepted=True, after=terminal)
    engine = replay([outcome])
    engine.on_deal(deal(), terminal, 103.6, 103.7)
    track = engine._track(70)
    assert engine._close(track, TIME, 103.6, 103.7, "OPPOSITE_BREAKOUT")
    assert track.status == XauExecutionStatus.FILLED
    assert engine.net_realized == 0
    engine.on_deal(deal("OUT", ticket=2), view(position=False, deals=[history(), history(2, profit=3)]), 103.6, 103.7)
    assert track.status == XauExecutionStatus.CLOSED
    assert engine.net_realized == pytest.approx(2.4)


def test_recording_runs_market_and_callback_checkpoints_with_first_difference():
    engine = replay()
    tick = RecordedInit(
        has_ea_deal_today=False,
        time=TIME,
        day="2026-09-24",
        bar_time=TIME,
        bar_open=103,
        bid=103,
        ask=103.1,
        history=((103, 104, 102, 103),) * 3,
        zones=tuple(ZONES),
        view=view(position=False),
    )
    callback = RecordedDeal(deal=deal(), bid=103.6, ask=103.7, view=view(deals=[history()]))
    tape = NativeRecording(
        provenance="source-derived",
        reference_sha256="0" * 64,
        initial_balance=200,
        inputs=engine.config.inputs,
        minimum_stop_distance=0,
        session_windows=(),
        profits=(),
        operations=(),
        events=(tick, callback),
    )
    checkpoints = list(replay_recording(NativeRecording.model_validate_json(tape.model_dump_json())))
    assert checkpoints[0].state["g_positions"] == []
    assert checkpoints[1].state["g_positions"][0]["position_id"] == 70
    assert compare_checkpoints(checkpoints, checkpoints) is None
    changed = checkpoints[1].model_copy(update={"state": checkpoints[1].state | {"g_trend": 99}})
    assert "event 1" in compare_checkpoints(checkpoints, [checkpoints[0], changed])
    assert "$.state.g_trend" in compare_checkpoints(checkpoints, [checkpoints[0], changed])
    assert "empty evidence" in compare_checkpoints([], [])


def test_market_recording_generates_exact_command_then_delayed_native_fill():
    engine = replay()
    second = TIME + pd.Timedelta(seconds=1)
    native_position = (
        view()
        .positions[0]
        .model_copy(
            update={
                "buy": False,
                "entry": 100.9,
                "sl": 110.0,
                "tp": 92.0,
                "comment": "R|20260924|z|S",
                "opened": second,
            }
        )
    )
    filled = NativeView(balance=199.7, free_margin=198.7, positions=(native_position,), history=(history(),))
    before_callback = filled.model_copy(update={"history": ()})
    init = RecordedInit(
        time=TIME,
        day="2026-09-24",
        bar_time=TIME,
        bar_open=99,
        bid=99,
        ask=99.1,
        history=((98.5, 99.0, 98.0, 98.5),) * 3,
        zones=tuple(ZONES),
        view=view(position=False),
        has_ea_deal_today=False,
    )
    tick = RecordedTick(
        **(init.model_dump(exclude={"kind", "has_ea_deal_today"}) | {"time": second, "bid": 101, "ask": 101.1})
    )
    callback = RecordedDeal(
        deal=deal(time=second, price=100.9, comment="R|20260924|z|S"), bid=101, ask=101.1, view=filled
    )
    command = NativeOperation(
        operation="SUBMIT",
        target="R|20260924|z|S",
        time=second,
        accepted=True,
        order_ticket=80,
        after=before_callback,
        price=101,
        sl=110,
        tp=92,
        volume=0.01,
    )
    recording = NativeRecording(
        provenance="source-derived",
        reference_sha256="0" * 64,
        initial_balance=200,
        inputs=engine.config.inputs,
        minimum_stop_distance=0,
        session_windows=(),
        profits=(),
        operations=(command,),
        events=(init, tick, callback),
    )
    states = [c.state for c in replay_recording(recording)]
    assert states[0]["g_trend"] == 0
    assert states[1]["g_trend"] == 1
    assert states[1]["g_requests"][0]["active"]
    assert states[1]["g_positions"] == []
    assert states[2]["g_positions"][0]["risk_anchor_entry"] == 101
    assert states[2]["g_positions"][0]["actual_fill"] == 100.9
    assert states[2]["g_zones"][1]["reversal_fill_count"] == 1


def test_native_risk_calculation_failure_does_not_invent_postfill_close():
    engine = replay()
    engine.config = replace(engine.config, inputs=engine.config.inputs.model_copy(update={"risk_mode": "gross"}))
    engine.native.profits[(candidate().direction, 0.01, 103.7, 97.1)] = None
    engine.on_deal(deal(), view(deals=[history()]), 103.6, 103.7)
    assert engine.risk_state_error
    assert engine._track(70).status == XauExecutionStatus.FILLED
    assert [event["event"] for event in engine.events] == ["FILL"]


@pytest.mark.parametrize("fresh_start,locked", [(False, True), (True, False)])
def test_restart_from_native_history_observation(fresh_start, locked):
    engine = replay()
    engine.config = replace(
        engine.config, inputs=engine.config.inputs.model_copy(update={"allow_same_day_fresh_start": fresh_start})
    )
    engine.detect_restart(TIME, True, 103, 103.1)
    assert engine.restart_locked is locked


def test_session_closes_untracked_native_position_without_fabricating_track():
    time = TIME + pd.Timedelta(hours=22, minutes=55)
    close = NativeOperation(operation="CLOSE", target="90", time=time, accepted=False, after=view())
    engine = replay([close])
    engine.native.session_windows = ((TIME, TIME + pd.Timedelta(hours=23)),)
    engine.update_view(view())
    engine._session(time, 103, 103.1)
    assert engine.session_preclose
    assert shared_trace(engine.state, engine)["g_positions"] == []
    engine.native.assert_consumed()


def test_native_stop_retry_uses_recorded_costs_and_exact_modify_parameters():
    terminal = view(deals=[history()])
    updated = terminal.model_copy(update={"positions": (terminal.positions[0].model_copy(update={"sl": 104.0}),)})
    commands = [
        NativeOperation(
            operation="MODIFY",
            target="90",
            time=TIME,
            sl=104.0,
            tp=120.0,
            accepted=accepted,
            after=updated if accepted else terminal,
        )
        for accepted in (False, True)
    ]
    engine = replay(commands)
    request = ReplayOrder(
        "request",
        candidate(family=XauSignalFamily.REVERSAL),
        0.01,
        97,
        120,
        "next",
        TIME,
        broker_day="2026-09-24",
        initial_sl=97,
        r0=6,
    )
    engine.requests.append(request)
    engine.on_deal(deal(), terminal, 103.6, 103.7)
    engine.native.profits[(candidate().direction, 0.01, 103.7, 104.7)] = 1.0
    track = engine._track(70)
    engine._manage(TIME, 109.1, 109.2, ())
    assert track.r_stage == 1 and track.desired_sl == 104.0 and track.sl_retry_logged
    assert track.stop_loss == 97.1
    engine._manage(TIME, 109.1, 109.2, ())
    assert track.stop_loss == 104.0 and track.desired_sl == 0 and not track.sl_retry_logged
    engine.native.assert_consumed()
