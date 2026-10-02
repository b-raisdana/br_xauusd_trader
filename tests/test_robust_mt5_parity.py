import json
from dataclasses import replace

import pandas as pd
import pytest
from pydantic import ValidationError
from test_vectorized_execution import ZONES, candidate, config, step, window

from application.xauusd_trading_strategy_1_vector.domain.replay import ReplayFileConfig, ReplayOrder
from application.xauusd_trading_strategy_1_vector.domain.robust import RobustInputs, protection, pullback_allowed
from application.xauusd_trading_strategy_1_vector.market import MarketState
from application.xauusd_trading_strategy_1_vector.replay import ExecutionReplay
from domain.xau_usd.enums import XauDirection, XauExecutionStatus, XauSignalFamily
from domain.xau_usd.models import XauDailyZoneSignalState, XauZone


@pytest.mark.parametrize("reject_first", [False, True])
def test_breakout_closes_reversals_in_native_creation_order(monkeypatch, reject_first):
    replay = ExecutionReplay(config(), "close-order")
    time = pd.Timestamp("2026-09-24", tz="UTC")
    replay.state.broker_day = "2026-09-24"
    for name in ("first", "second"):
        replay.orders[name] = ReplayOrder(
            name,
            candidate(XauDirection.SELL, XauSignalFamily.REVERSAL, name=name),
            0.01,
            105,
            92,
            "below",
            time,
            status=XauExecutionStatus.FILLED,
            broker_day="2026-09-24",
        )
    closed = []

    def close(order, *args):
        closed.append(order.request_id)
        return not reject_first

    monkeypatch.setattr(replay, "_close", close)
    replay._breakout(candidate(), time, 103, 103.1)
    assert closed == (["first"] if reject_first else ["first", "second"])


@pytest.mark.parametrize("direction,stop", [(XauDirection.BUY, 104), (XauDirection.SELL, 102)])
def test_pending_profitable_stop_reserves_zero_native_cash_risk(direction, stop):
    replay = ExecutionReplay(config(), "pending-risk")
    time = pd.Timestamp("2026-09-24", tz="UTC")
    replay.orders["pending"] = ReplayOrder("pending", candidate(direction), 0.01, stop, 110, "target", time)
    assert replay._risk(103, 103.1)[1] == 0


def test_missing_live_stop_uses_tracked_initial_stop_for_cash_risk():
    replay = ExecutionReplay(config(), "missing-stop")
    time = pd.Timestamp("2026-09-24", tz="UTC")
    replay.orders["filled"] = ReplayOrder(
        "filled",
        candidate(),
        0.01,
        0,
        110,
        "target",
        time,
        status=XauExecutionStatus.FILLED,
        fill_price=103,
        initial_sl=97,
    )
    assert replay._risk(103, 103.1)[0] == 6


@pytest.mark.parametrize("high,used,allowed", [(False, 1, True), (False, 2, False), (True, 9, True), (True, 10, False)])
def test_explicit_pullback_limits_count_fills(high, used, allowed):
    zone = XauZone("z", 100, 102, int(high))
    zones = [zone, XauZone("next", 114, 116)]
    assert pullback_allowed(zones, XauDailyZoneSignalState(zone, pullback_fills=used), True, RobustInputs()) is allowed


def test_zero_high_quota_is_unlimited_but_zero_normal_blocks():
    inputs = RobustInputs(high_pullback_max=0, normal_pullback_max=0)
    high = XauZone("high", 100, 102, 1)
    normal = XauZone("normal", 130, 132)
    assert pullback_allowed([high, normal], XauDailyZoneSignalState(high, pullback_fills=100), True, inputs)
    assert not pullback_allowed([high, normal], XauDailyZoneSignalState(normal), True, inputs)


@pytest.mark.parametrize(
    "direction,entry,high,expected",
    [
        (XauDirection.BUY, 103, False, (101, 106, 2, "target")),
        (XauDirection.BUY, 103, True, (100, 106, 3, "target")),
        (XauDirection.SELL, 103, False, (106, 99, 3, "lower")),
        (XauDirection.SELL, 103, True, (107.5, 90, 4.5, "bottom")),
    ],
)
def test_targets_use_actual_risk_and_high_reversal_expansion(direction, entry, high, expected):
    zones = [
        XauZone("bottom", 88, 90),
        XauZone("lower", 97, 99),
        XauZone("stop", 100, 101),
        XauZone("signal", 102, 104),
        XauZone("target", 106, 108),
    ]
    assert protection(zones, 3, direction, entry, high, RobustInputs()) == expected


def test_default_direct_breakout_is_disabled():
    replay = ExecutionReplay(config(inputs=RobustInputs()), "default")
    output = step(replay, 103, breakouts=(candidate(),))
    assert output["actions"] == ()
    assert replay.orders == {}


def test_fill_ends_parent_and_new_breakout_can_open_another_cycle():
    replay = ExecutionReplay(config(), "cycle")
    step(replay, 101.8, openings=(window(),))
    step(replay, 102.2, time="2026-09-24 00:01")
    cycle = replay.state.pullbacks[0]
    assert not cycle.active and not cycle.order_ticket and not cycle.pending_active
    assert replay.state.zones[1].pullback_fills == 1
    second = window()
    second.parent_breakout_id = "BO2"
    output = step(replay, 101.8, time="2026-09-24 00:15", openings=(second,))
    assert output["actions"][0]["candidate"]["parent_breakout_id"] == "BO2"
    assert replay.state.pullbacks[0].parent_breakout_id == "BO1"


def test_failed_cancel_deactivates_cycle_but_preserves_pending_ticket():
    class RefuseCancel(type(config().economics)):
        def accepts(self, operation, request_id, time):
            return operation != "CANCEL"

    base = config()
    economics = RefuseCancel(**vars(base.economics))
    replay = ExecutionReplay(replace(base, economics=economics), "cancel")
    step(replay, 101.8, openings=(window(),))
    cycle = replay.state.pullbacks[0]
    ticket = cycle.order_ticket
    replay._end_cycle(cycle, pd.Timestamp("2026-09-24 00:01", tz="UTC"), "WINDOW_EXPIRED")
    assert not cycle.active and cycle.order_ticket == ticket
    assert replay.orders[ticket].status == XauExecutionStatus.SUBMITTED


def test_day_change_keeps_positions_and_resets_daily_accounting():
    replay = ExecutionReplay(config(), "carry")
    step(replay, 103, breakouts=(candidate(),))
    output = step(replay, 103, time="2026-09-25 00:00")
    assert output["positions"][0]["position_status"] == XauExecutionStatus.FILLED
    assert output["daily_net_realized_pnl"] == 0


def test_request_risk_anchor_survives_pending_fill_slippage():
    replay = ExecutionReplay(config(), "anchor")
    step(replay, 101.8, openings=(window(),))
    step(replay, 103, time="2026-09-24 00:01")
    order = next(iter(replay.orders.values()))
    assert order.candidate.entry_price == 102 and order.fill_price == 103.1
    assert order.r0 == 6 and order.initial_sl == 96
    step(replay, 108.1, time="2026-09-24 00:02")
    assert order.r_stage == 1
    assert order.stop_loss == 103.2


def test_market_preserves_native_open_and_previous_bid_at_new_bar():
    market = MarketState(RobustInputs())
    time = pd.Timestamp("2026-09-24", tz="UTC")
    history = [(99.0, 99.0, 99.0, 99.0)] * 3
    market.step(time, "2026-09-24", time, 99, 99, 99.1, history, ZONES)
    output = market.step(
        time + pd.Timedelta(minutes=15), "2026-09-24", time + pd.Timedelta(minutes=15), 99, 101, 101.1, history, ZONES
    )
    assert output["buy_engaged:z"]
    assert output["reversal_signals"][0].direction == XauDirection.SELL
    trace = json.loads(output["mt5_state"])
    assert trace["g_zones"][1]["last_reversal_sell_signal_bar"] == int((time + pd.Timedelta(minutes=15)).timestamp())


def test_bootstrap_rejects_missing_native_history():
    market = MarketState(RobustInputs())
    time = pd.Timestamp("2026-09-24", tz="UTC")
    with pytest.raises(ValueError, match="three native"):
        market.step(time, "2026-09-24", time, 100, 100, 100.1, [(100, 100, 100, 100)] * 2, ZONES)


def test_json_configuration_preserves_explicit_economics_and_ea_defaults():
    payload = dict(economics=vars(config().economics), initial_balance=500)
    parsed = ReplayFileConfig.model_validate_json(json.dumps(payload, default=str)).replay_config()
    assert parsed.initial_balance == 500 and parsed.inputs == RobustInputs()
    assert parsed.economics.session_end(pd.Timestamp("2026-09-24", tz="UTC")).hour == 23
    with pytest.raises(ValidationError):
        ReplayFileConfig.model_validate({**payload, "inputs": {"max_positions": 0}})


@pytest.mark.parametrize(
    "actual,path",
    [
        ({"g_trend": -1, "g_cycles": [{"active": False}]}, "$.g_cycles[0].active"),
        ({"g_trend": 2, "g_cycles": [{"active": True}]}, "$.g_trend"),
        ({"g_trend": -1}, "$:"),
    ],
)
def test_trace_comparison_reports_first_state_mismatch(actual, path):
    from application.xauusd_trading_strategy_1_vector.trace import first_difference

    expected = {"g_trend": -1, "g_cycles": [{"active": True}]}
    assert first_difference(expected, expected) is None
    assert first_difference(expected, actual).startswith(path)


@pytest.mark.parametrize("mode,closed", [("carry", False), ("pullback", False), ("all", True)])
def test_native_session_windows_preserve_gap_and_carry_state(mode, closed):
    base = config()
    times = [pd.Timestamp("2026-09-24 " + time, tz="UTC") for time in ("09:00", "12:00", "13:00", "17:00")]
    economics = replace(base.economics, session_windows=((times[0], times[1]), (times[2], times[3])))
    inputs = base.inputs.model_copy(update={"session_mode": mode})
    replay = ExecutionReplay(replace(base, economics=economics, inputs=inputs), "sessions")
    step(replay, 103, time="2026-09-24 09:00", breakouts=(candidate(),))
    gap = step(replay, 103, time="2026-09-24 12:30")
    assert not gap["operational_locked"]
    assert replay.session_active_to == times[1]
    step(replay, 103, time="2026-09-24 13:00")
    order = next(iter(replay.orders.values()))
    assert order.last_carry_audit_key == "2026.09.24 13:00:00->2026.09.24 17:00:00"
    step(replay, 103, time="2026-09-24 16:55")
    assert (order.status == XauExecutionStatus.CLOSED) is closed
    if closed:
        assert order.session_close_reason.startswith("broker_session_end=2026.09.24 17:00:00 cutoff=")
    step(replay, 103, time="2026-09-24 17:00")
    assert not replay.session_preclose
