from copy import deepcopy
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from pandera.errors import SchemaErrors
from vectorized_fixtures import prepared_ticks

from application.xauusd_trading_strategy_1_vector.actions import generate_actions
from application.xauusd_trading_strategy_1_vector.domain.replay import LinearReplayEconomics, ReplayConfig
from application.xauusd_trading_strategy_1_vector.domain.robust import RobustInputs
from application.xauusd_trading_strategy_1_vector.replay import ExecutionReplay
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
from domain.xau_usd.enums import XauDirection, XauExecutionStatus, XauOrderType, XauSignalFamily
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


def step(replay, price, time="2026-09-24 00:00", breakouts=(), reversals=(), openings=(), bar_open=101.0, zones=ZONES):
    time = pd.Timestamp(time, tz="UTC")
    return replay.step(
        time,
        time.strftime("%Y-%m-%d"),
        time.floor("15min"),
        bar_open,
        float(price),
        float(price) + 0.1,
        zones,
        openings,
        breakouts,
        reversals,
    )


def window(priority=1, direction=XauDirection.BUY):
    return XauPullbackWindowState("BO1", XauZone("z", 100, 102, priority), direction, bar_offset=1, active=True)


@pytest.mark.parametrize(
    "direction,price,entry,stop,target",
    [
        (XauDirection.BUY, 103, 103.1, 97.1, 110),
        (XauDirection.SELL, 99, 99, 105, 92),
    ],
)
def test_market_fill_uses_quote_side_and_zone_protection(direction, price, entry, stop, target):
    replay = ExecutionReplay(config(), "test")
    output = step(replay, price, breakouts=(candidate(direction, entry=price),))
    order, position = output["orders"][0], output["positions"][0]
    assert order["stop_loss"] == stop
    assert order["take_profit"] == target
    assert position["position_entry_price"] == entry
    assert position["position_size"] == 0.01
    assert position["position_unrealized_pnl"] == pytest.approx(-0.2)
    assert [event["event"] for event in output["execution_events"]] == ["SUBMIT", "FILL"]


def test_rejected_broker_attempt_consumes_bar_but_risk_rejection_does_not():
    replay = ExecutionReplay(config(), "test")
    no_stop = candidate(zone="below", name="bad")
    valid = candidate()
    output = step(replay, 103, breakouts=(no_stop, valid))
    assert len(output["entry_rejections"]) == 1
    assert len(output["actions"]) == 1
    assert step(replay, 103, time="2026-09-24 00:01", breakouts=(valid,))["actions"] == ()
    replay = ExecutionReplay(replace(config(), economics=replace(config().economics, minimum_stop_distance=8)), "test")
    rejected = step(replay, 103, breakouts=(valid, valid))
    assert len(rejected["actions"]) == 1
    assert rejected["orders"][0]["order_status"] == XauExecutionStatus.REJECTED
    assert step(replay, 103, time="2026-09-24 00:01", breakouts=(valid,))["actions"] == ()


@pytest.mark.parametrize("priority,expected", [(0, 0), (1, 0)])
def test_pullback_feedback_prevents_duplicate_pending_and_consumes_fills(priority, expected):
    zones = deepcopy(ZONES)
    zones[1].priority = priority
    replay = ExecutionReplay(config(), "test")
    first = step(replay, 101.8, openings=(window(priority),), zones=zones)
    assert first["orders"][0]["order_status"] == XauExecutionStatus.SUBMITTED
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


def test_pullback_pending_expires_and_does_not_fill_on_expiry_tick():
    replay = ExecutionReplay(config(), "test")
    step(replay, 101.8, openings=(window(),))
    for minute in (15, 30, 45, 60):
        step(replay, 101.8, time=str(pd.Timestamp("2026-09-24") + pd.Timedelta(minutes=minute)))
    expired = step(replay, 103, time="2026-09-24 01:15")
    assert expired["orders"][0]["order_status"] == XauExecutionStatus.CANCELLED
    assert not expired["positions"]


def test_stop_gap_pnl_and_native_cost_inputs_are_accounted_once():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, breakouts=(candidate(),))
    closed = step(replay, 96, time="2026-09-24 00:01")
    assert closed["positions"][0]["position_status"] == XauExecutionStatus.CLOSED
    assert closed["daily_net_realized_pnl"] == pytest.approx(-7.4)
    assert closed["daily_gross_loss"] == pytest.approx(7.4)
    assert closed["account_balance"] == pytest.approx(192.6)
    assert step(replay, 100, time="2026-09-24 00:02")["positions"] == ()


def test_profit_protection_uses_cost_adjusted_rf_and_never_loosens():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, breakouts=(candidate(),))
    protected = step(replay, 109.2, time="2026-09-24 00:01")
    assert protected["positions"][0]["stop_loss"] == pytest.approx(103.2)
    retrace = step(replay, 108, time="2026-09-24 00:02")
    assert retrace["positions"][0]["stop_loss"] == pytest.approx(103.2)


def test_pullback_tp_remains_fixed_when_current_bar_turns():
    replay = ExecutionReplay(config(), "test")
    step(replay, 101.8, openings=(window(),))
    step(replay, 102, time="2026-09-24 00:01")
    extended = step(replay, 109, time="2026-09-24 00:02")
    assert extended["positions"][0]["take_profit"] == 110
    restored = step(replay, 108, time="2026-09-24 00:15", bar_open=109)
    assert restored["positions"][0]["take_profit"] == 110


def test_pullback_does_not_block_opposite_reversal_at_target_touch():
    replay = ExecutionReplay(config(), "test")
    step(replay, 101.8, openings=(window(),))
    step(replay, 102, time="2026-09-24 00:01")
    step(replay, 109, time="2026-09-24 00:02")
    reversal = candidate(XauDirection.SELL, XauSignalFamily.REVERSAL, "2026-09-24 00:15:00+00:00", 120, "next")
    assert not replay._blocked_reversal(reversal, 120, 120.1)


def test_session_flatten_cancels_pending_and_closes_positions():
    replay = ExecutionReplay(config(), "test")
    step(replay, 103, time="2026-09-24 22:30", breakouts=(candidate(bar="2026-09-24 22:15:00+00:00"),))
    step(replay, 101.8, time="2026-09-24 22:45", openings=(window(),))
    output = step(replay, 101.8, time="2026-09-24 22:55")
    assert output["operational_locked"]
    assert all(o.status in (XauExecutionStatus.CLOSED, XauExecutionStatus.CANCELLED) for o in replay.orders.values())
    assert not step(replay, 103, time="2026-09-24 22:56", breakouts=(candidate(),))["actions"]


def test_restart_day_blocks_all_entries():
    replay = ExecutionReplay(config(restart_days=frozenset({"2026-09-24"})), "test")
    assert not step(replay, 103, breakouts=(candidate(),))["actions"]


def test_daily_loss_lock_resets_next_day():
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
def test_risk_gates_prevent_attempts(kind):
    cfg = config()
    if kind == "margin":
        cfg = replace(cfg, economics=replace(cfg.economics, margin_per_lot=100000))
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
        assert len(rejected["actions"]) == 1
        assert not rejected["actions"][0]["accepted"]
        assert rejected["orders"][-1]["order_status"] == XauExecutionStatus.REJECTED
    else:
        assert not rejected["actions"]
        assert len(rejected["entry_rejections"]) == 1
    assert "unused" not in rejected["attempted_bars"]


@prepared_ticks
def frame(prices):
    times = pd.date_range("2026-09-24", periods=len(prices), freq="min", tz="UTC").as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [["b"] * len(times), ["XAUUSD"] * len(times), times, times.normalize()],
        names=["broker", "symbol", "precise_time", "date"],
    )
    return pd.DataFrame({"bid": np.array(prices, dtype=float), "ask": np.array(prices, dtype=float) + 0.1}, index=index)


class Zones:
    def get_zones_for_day(self, day):
        return deepcopy(ZONES)


@pytest.mark.parametrize("defect", ["missing", "dtype", "index"])
def test_execution_input_validation_rejects_broken_data(defect):
    ticks = frame([103])
    data = VectorizedXauUsdStrategy(Zones())._initialize_per_tick_temp_state(ticks)
    if defect == "missing":
        ticks = ticks.drop(columns="ask")
    elif defect == "dtype":
        ticks["bid"] = "bad"
    else:
        arrays = [data.index.get_level_values(name) for name in data.index.names]
        arrays[2] = arrays[2].as_unit("us")
        data.index = pd.MultiIndex.from_arrays(arrays, names=data.index.names)
    with pytest.raises(SchemaErrors):
        generate_actions(ticks, data, ZONES, config())


def test_action_compatibility_replay_rejects_misaligned_state():
    ticks = frame([103, 104])
    data = VectorizedXauUsdStrategy(Zones())._initialize_per_tick_temp_state(ticks).iloc[::-1]
    with pytest.raises(ValueError, match="identical ordered indexes"):
        generate_actions(ticks, data, ZONES, config())


def test_action_compatibility_replay_clears_stale_native_snapshot():
    ticks = frame([103])
    data = VectorizedXauUsdStrategy(Zones())._initialize_per_tick_temp_state(ticks)
    data["mt5_state"] = '{"g_daily_stop":true}'
    result = generate_actions(ticks, data, ZONES, config())
    assert result["mt5_state"].tolist() == ["{}"]
