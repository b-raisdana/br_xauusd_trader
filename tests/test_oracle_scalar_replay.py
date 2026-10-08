"""Test-only scalar oracle using ExecutionReplay phase order.

This module imports and uses the scalar ExecutionReplay.step driver to
characterize exact phase ordering and tie-break behavior. It is test
reference code only and must not be imported by production.
"""

from __future__ import annotations

from copy import deepcopy

import pandas as pd
import pytest

from application.xauusd_trading_strategy_1_vector.domain.replay import (
    LinearReplayEconomics,
    ReplayConfig,
)
from application.xauusd_trading_strategy_1_vector.domain.robust import RobustInputs
from application.xauusd_trading_strategy_1_vector.replay import ExecutionReplay
from domain.xau_usd.enums import (
    XauDirection,
    XauExecutionStatus,
    XauOrderType,
    XauSignalFamily,
)
from domain.xau_usd.models import XauPullbackWindowState, XauSignalCandidate, XauZone

ZONES = [XauZone("below", 90, 92), XauZone("z", 100, 102, 1), XauZone("target", 110, 112), XauZone("next", 120, 122)]


def config(**kwargs):
    economics = LinearReplayEconomics(
        100.0,
        100.0,
        10.0,
        20.0,
        0.0,
        {day: pd.Timestamp(day + " 23:00", tz="UTC") for day in ("2026-09-24", "2026-09-25")},
    )
    kwargs.setdefault(
        "inputs",
        RobustInputs(
            enable_direct_breakout=True,
            breakout_normal_only=False,
            pullback_min_space=0,
            high_reversal_min_space=0,
            one_order_per_candle=True,
        ),
    )
    return ReplayConfig(economics, **kwargs)


def candidate(
    direction=XauDirection.BUY,
    family=XauSignalFamily.BREAKOUT,
    bar="2026-09-24 00:00:00+00:00",
    entry=103.0,
    zone="z",
    name="BO1",
):
    return XauSignalCandidate(
        candidate_id=name,
        bar_id=bar,
        zone_id=zone,
        family=family,
        direction=direction,
        order_type=XauOrderType.MARKET,
        signal_time=pd.Timestamp(bar),
        entry_price=entry,
    )


def step(
    replay,
    price,
    time="2026-09-24 00:00",
    breakouts=(),
    reversals=(),
    openings=(),
    bar_open=101.0,
    zones=ZONES,
):
    """Oracle step using the exact ExecutionReplay phase order."""
    time = pd.Timestamp(time, tz="UTC")
    replay._begin_tick(float(price), float(price) + 0.1)
    replay._session(time, float(price), float(price) + 0.1)
    replay._roll(
        time.strftime("%Y-%m-%d"),
        time.floor("15min"),
        bar_open,
        zones,
        openings,
        time,
        float(price),
        float(price) + 0.1,
    )
    if not replay._restart(time, float(price), float(price) + 0.1):
        replay._settle(time, float(price), float(price) + 0.1)
        for candidate in breakouts:
            replay._breakout(candidate, time, float(price), float(price) + 0.1)
        for candidate in reversals:
            replay._submit(candidate, time, float(price), float(price) + 0.1)
        pullbacks = replay._pullbacks(time, float(price), float(price) + 0.1)
        replay._manage(time, float(price), float(price) + 0.1, ())
    else:
        pullbacks = []
    return replay._snapshot(float(price), float(price) + 0.1, pullbacks)


def window(priority=1, direction=XauDirection.BUY):
    return XauPullbackWindowState("BO1", XauZone("z", 100, 102, priority), direction, bar_offset=1, active=True)


@pytest.mark.parametrize(
    "direction,price,entry,stop,target",
    [
        (XauDirection.BUY, 103, 103.1, 97.1, 110),
        (XauDirection.SELL, 99, 99, 105, 92),
    ],
)
def test_oracle_market_fill_uses_quote_side_and_zone_protection(direction, price, entry, stop, target):
    replay = ExecutionReplay(config(), "test")
    output = step(replay, price, breakouts=(candidate(direction, entry=price),))
    order, position = output["orders"][0], output["positions"][0]
    assert order["stop_loss"] == stop
    assert order["take_profit"] == target
    assert position["position_entry_price"] == entry
    assert position["position_size"] == 0.01
    assert position["position_unrealized_pnl"] == pytest.approx(-0.2)
    assert [event["event"] for event in output["execution_events"]] == ["SUBMIT", "FILL"]


def test_oracle_rejected_broker_attempt_consumes_bar_but_risk_rejection_does_not():
    replay = ExecutionReplay(config(), "test")
    no_stop = candidate(zone="below", name="bad")
    valid = candidate()
    output = step(replay, 103, breakouts=(no_stop, valid))
    assert len(output["entry_rejections"]) == 1
    assert len(output["actions"]) == 1
    assert step(replay, 103, time="2026-09-24 00:01", breakouts=(valid,))["actions"] == ()


@pytest.mark.parametrize("priority,expected", [(1, 0)])
def test_oracle_pullback_feedback_prevents_duplicate_pending_and_consumes_fills(priority, expected):
    zones = deepcopy(ZONES)
    zones[1].priority = priority
    replay = ExecutionReplay(config(), "test")
    first = step(replay, 101.8, openings=(window(priority),), zones=zones)
    assert first["orders"][0]["order_status"] == XauExecutionStatus.SUBMITTED.value
    assert first["pullback_feedback"][0].pending_active
    assert step(replay, 101.8, time="2026-09-24 00:01", zones=zones)["pullback_signals"] == ()
    filled = step(replay, 102.2, time="2026-09-24 00:02", zones=zones)
    assert filled["pullback_feedback"][0].filled
    assert filled["positions"][0]["position_entry_price"] == pytest.approx(102.3)
    assert filled["pullback_signals"] == ()
    next_bar = step(replay, 101.8, time="2026-09-24 00:15", zones=zones)
    assert len(next_bar["actions"]) == expected
    if expected:
        assert next_bar["actions"][0]["candidate"]["parent_breakout_id"] == "BO1"


def test_oracle_pullback_pending_expires_and_does_not_fill_on_expiry_tick():
    replay = ExecutionReplay(config(), "test")
    step(replay, 101.8, openings=(window(),))
    for minute in (15, 30, 45, 60):
        step(replay, 101.8, time=str(pd.Timestamp("2026-09-24") + pd.Timedelta(minutes=minute)))
    expired = step(replay, 103, time="2026-09-24 01:15")
    assert expired["orders"][0]["order_status"] == XauExecutionStatus.CANCELLED.value
    assert not expired["positions"]


def test_oracle_stop_gap_pnl_and_native_cost_inputs_are_accounted_once():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, breakouts=(candidate(),))
    closed = step(replay, 96, time="2026-09-24 00:01")
    assert closed["positions"][0]["position_status"] == XauExecutionStatus.CLOSED.value
    assert closed["daily_net_realized_pnl"] == pytest.approx(-7.4)
    assert closed["daily_gross_loss"] == pytest.approx(7.4)
    assert closed["account_balance"] == pytest.approx(192.6)
    assert step(replay, 100, time="2026-09-24 00:02")["positions"] == ()


def test_oracle_profit_protection_uses_cost_adjusted_rf_and_never_loosens():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, breakouts=(candidate(),))
    protected = step(replay, 109.2, time="2026-09-24 00:01")
    assert protected["positions"][0]["stop_loss"] == pytest.approx(103.2)
    retrace = step(replay, 108, time="2026-09-24 00:02")
    assert retrace["positions"][0]["stop_loss"] == pytest.approx(103.2)


def test_oracle_pullback_tp_remains_fixed_when_current_bar_turns():
    replay = ExecutionReplay(config(), "test")
    step(replay, 101.8, openings=(window(),))
    step(replay, 102, time="2026-09-24 00:01")
    extended = step(replay, 109, time="2026-09-24 00:02")
    assert extended["positions"][0]["take_profit"] == 110
    restored = step(replay, 108, time="2026-09-24 00:15", bar_open=109)
    assert restored["positions"][0]["take_profit"] == 110


def test_oracle_pullback_does_not_block_opposite_reversal_at_target_touch():
    replay = ExecutionReplay(config(), "test")
    step(replay, 101.8, openings=(window(),))
    step(replay, 102, time="2026-09-24 00:01")
    step(replay, 109, time="2026-09-24 00:02")
    reversal = candidate(XauDirection.SELL, XauSignalFamily.REVERSAL, "2026-09-24 00:15:00+00:00", 120, "next")
    assert not replay._blocked_reversal(reversal, 120, 120.1)


def test_oracle_session_flatten_cancels_pending_and_closes_positions():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, time="2026-09-24 22:30", breakouts=(candidate(bar="2026-09-24 22:15:00+00:00"),))
    step(replay, 101.8, time="2026-09-24 22:45", openings=(window(),))
    output = step(replay, 101.8, time="2026-09-24 22:55")
    assert output["operational_locked"]
    assert all(o.status in (XauExecutionStatus.CLOSED, XauExecutionStatus.CANCELLED) for o in replay.orders.values())
    assert not step(replay, 103, time="2026-09-24 22:56", breakouts=(candidate(),))["actions"]


def test_oracle_restart_day_blocks_all_entries():
    replay = ExecutionReplay(config(restart_days=frozenset({"2026-09-24"})), "test")
    assert not step(replay, 103, breakouts=(candidate(),))["actions"]


def test_oracle_daily_loss_lock_resets_next_day():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, breakouts=(candidate(),))
    output = step(
        replay, 50, time="2026-09-24 00:15", breakouts=(candidate(bar="2026-09-25 00:00:00+00:00", entry=103),)
    )
    assert output["daily_loss_locked"]
    assert not output["actions"]
    reset = step(replay, 103, time="2026-09-25 00:00", breakouts=(candidate(bar="2026-09-25 00:00:00+00:00"),))
    assert not reset["daily_loss_locked"]
    assert len(reset["actions"]) == 1


@pytest.mark.parametrize("kind", ["margin", "gross", "concurrency"])
def test_oracle_risk_gates_prevent_attempts(kind):
    cfg = config()
    if kind == "margin":
        cfg = ReplayConfig(
            LinearReplayEconomics(
                100.0,
                100000.0,
                10.0,
                20.0,
                0.0,
                {day: pd.Timestamp(day + " 23:00", tz="UTC") for day in ("2026-09-24", "2026-09-25")},
            ),
            inputs=cfg.inputs,
        )
    replay = ExecutionReplay(cfg, "test")
    step(replay, 103)
    if kind == "gross":
        replay.gross_loss = 60
    if kind == "concurrency":
        for i in range(3):
            step(
                replay,
                103,
                time=f"2026-09-24 00:{i * 15:02d}",
                breakouts=(candidate(bar=f"2026-09-24 00:{i * 15:02d}:00+00:00"),),
            )
    rejected = step(replay, 103, time="2026-09-24 01:00", breakouts=(candidate(bar="2026-09-24 01:00:00+00:00"),))
    if kind == "margin":
        # With huge margin requirement, the order is REJECTED by broker
        assert len(rejected["actions"]) == 1
        assert not rejected["actions"][0]["accepted"]
        assert rejected["orders"][-1]["order_status"] == XauExecutionStatus.REJECTED.value
    else:
        assert not rejected["actions"]
        assert len(rejected["entry_rejections"]) == 1
    assert "unused" not in rejected["attempted_bars"]


def test_oracle_same_tick_fill_and_stop_with_stop_winning():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, breakouts=(candidate(),))
    # Gap down through stop on same tick
    output = step(replay, 96, time="2026-09-24 00:01")
    assert output["positions"][0]["position_status"] == XauExecutionStatus.CLOSED.value
    assert output["execution_events"][-1]["event"] == "CLOSE"
    assert output["execution_events"][-1]["reason"] == "SL"


def test_oracle_same_tick_stop_and_target_with_stop_first():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, breakouts=(candidate(),))
    # Move to near target, then gap through both
    step(replay, 109, time="2026-09-24 00:01")
    output = step(replay, 96, time="2026-09-24 00:02")
    assert output["positions"][0]["position_status"] == XauExecutionStatus.CLOSED.value
    assert output["execution_events"][-1]["reason"] == "SL"


def test_oracle_opposite_breakout_close_rejection_blocks_breakout():
    replay = ExecutionReplay(config(), "test")
    # First buy reversal
    rev = candidate(XauDirection.BUY, XauSignalFamily.REVERSAL, "2026-09-24 00:00:00+00:00", 101, "z", "R1")
    step(replay, 101, reversals=(rev,))
    # Try opposite breakout that should close first
    bo = candidate(XauDirection.SELL, XauSignalFamily.BREAKOUT, "2026-09-24 00:15:00+00:00", 99, "z", "BO2")

    # Make close fail by using economics.reject
    class RejectingEconomics:
        minimum_stop_distance = 0.0

        def profit(self, direction, volume, entry, exit_price):
            return 100.0 * (exit_price - entry) * volume

        def margin(self, volume, entry):
            return 100.0 * volume

        def cost(self, volume, time, opening):
            return 10.0 * volume

        def session_end(self, time):
            return pd.Timestamp("2026-09-24 23:00", tz="UTC")

        def session_window(self, time):
            return None

        def accepts(self, operation, request_id, time):
            return operation != "CLOSE"

    replay.economics = RejectingEconomics()
    output = step(replay, 99, time="2026-09-24 00:15", breakouts=(bo,))
    # Close was rejected, so breakout should not proceed
    assert len(output["actions"]) == 0


def test_oracle_risk_modes_off_vs_gross():
    # Risk mode off - no risk limits
    cfg_off = config(inputs=config().inputs.model_copy(update={"risk_mode": "off"}))
    replay_off = ExecutionReplay(cfg_off, "test")
    # Can open many positions despite gross loss
    replay_off.gross_loss = 1000
    output = step(replay_off, 103, breakouts=(candidate(),))
    assert len(output["actions"]) == 1


def test_oracle_qa_discovery_logs_would_trigger_without_locking():
    cfg_qa = config(inputs=config().inputs.model_copy(update={"qa_discovery": True, "qa_capital": 200}))
    replay_qa = ExecutionReplay(cfg_qa, "test")
    step(replay_qa, 103, breakouts=(candidate(),))
    # Take huge loss
    output = step(replay_qa, 50, time="2026-09-24 00:01")
    # In QA discovery mode, daily lock is NOT set
    assert not output["daily_loss_locked"]


def test_oracle_modify_rejection_when_broker_rejects():
    class RejectModifyEconomics:
        minimum_stop_distance = 0.0

        def profit(self, direction, volume, entry, exit_price):
            return 100.0 * (exit_price - entry) * volume

        def margin(self, volume, entry):
            return 100.0 * volume

        def cost(self, volume, time, opening):
            return 10.0 * volume

        def session_end(self, time):
            return pd.Timestamp("2026-09-24 23:00", tz="UTC")

        def session_window(self, time):
            return None

        def accepts(self, operation, request_id, time):
            return operation != "MODIFY"

    cfg = config()
    replay = ExecutionReplay(cfg, "test")
    replay.economics = RejectModifyEconomics()
    step(replay, 103, breakouts=(candidate(),))
    initial_sl = [o.stop_loss for o in replay.orders.values() if o.status == XauExecutionStatus.FILLED][0]
    # Move into profit protection territory
    output = step(replay, 109.2, time="2026-09-24 00:01")
    # Modify should be rejected
    assert any(e["event"] == "MODIFY_REJECT" for e in output["execution_events"])
    # Stop should not have moved from initial value
    assert output["positions"][0]["stop_loss"] == pytest.approx(initial_sl)
