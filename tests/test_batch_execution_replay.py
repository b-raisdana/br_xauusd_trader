"""Independent phase-driver comparisons against every exposed replay output."""

from copy import deepcopy
from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest
from test_oracle_scalar_replay import ZONES, candidate, config, window

from application.xauusd_trading_strategy_1_vector.domain.batch_schema import ReplayWindows
from application.xauusd_trading_strategy_1_vector.domain.execution_schema import CandidateEvents
from application.xauusd_trading_strategy_1_vector.domain.replay import ReplayConfig
from application.xauusd_trading_strategy_1_vector.execution_batch.economics import prepare_economics
from application.xauusd_trading_strategy_1_vector.execution_batch.kernel import decimal_price, scan
from application.xauusd_trading_strategy_1_vector.replay import ExecutionReplay
from application.xauusd_trading_strategy_1_vector.vectorized_replay import VectorizedExecutionReplay
from domain.xau_usd.enums import XauDirection, XauSignalFamily


class RejectedOperations:
    def __init__(self, linear, rejected):
        self.linear = linear
        self.rejected = rejected
        self.scalar_calls = 0

    def __getattr__(self, name):
        return getattr(self.linear, name)

    def accepts(self, operation, request_id, time):
        self.scalar_calls += 1
        return operation not in self.rejected

    def prepare_batch(self, streams, preclose_minutes):
        batch = prepare_economics(self.linear, streams, preclose_minutes)
        for operation in self.rejected:
            batch.acceptance[:, ["SUBMIT", "CLOSE", "CANCEL", "MODIFY"].index(operation)] = 0
        return batch


def _empty_replay_windows():
    """Create an empty ReplayWindows DataFrame with correct dtypes."""
    return pd.DataFrame(
        {
            "stream_tick": pd.array([], dtype="int64"),
            "parent_breakout_id": pd.array([], dtype="string[pyarrow]"),
            "zone_id": pd.array([], dtype="string[pyarrow]"),
            "direction": pd.array([], dtype="int64"),
            "breakout_bar_time": pd.array([], dtype="datetime64[ns, UTC]"),
            "broker_day": pd.array([], dtype="string[pyarrow]"),
        }
    )


def frames(prices, times, signals, openings):
    times = pd.DatetimeIndex(times).as_unit("ns")
    streams = pd.DataFrame(
        {
            "stream_id": "test",
            "stream_tick": np.arange(len(prices)),
            "precise_time": times,
            "broker_day": times.strftime("%Y-%m-%d"),
            "bar_time": times.floor("15min"),
            "bar_open": 101.0,
            "bid": prices,
            "ask": np.asarray(prices) + 0.1,
        }
    )
    zones = pd.DataFrame(
        [
            {"zone_id": z.id, "broker_day": day, "high": z.high, "low": z.low, "priority": z.priority}
            for day in streams.broker_day.unique()
            for z in ZONES
        ]
    )
    candidates = pd.DataFrame(
        [{"stream_tick": tick, **asdict(c)} for tick, group in signals.items() for c in group],
        columns=list(CandidateEvents.to_schema().columns),
    )
    windows = _empty_replay_windows()
    if openings:
        windows = pd.DataFrame(
            [
                {
                    "stream_tick": tick,
                    "parent_breakout_id": w.parent_breakout_id,
                    "zone_id": w.zone.id,
                    "direction": int(w.direction),
                    "breakout_bar_time": times[tick].floor("15min"),
                    "broker_day": streams.broker_day.iloc[tick],
                }
                for tick, group in openings.items()
                for w in group
            ],
            columns=list(ReplayWindows.to_schema().columns.keys()),
        )
    return streams, zones, candidates, windows


def assert_value(actual, expected):
    if expected is None:
        assert pd.isna(actual)
    elif isinstance(expected, (float, np.floating)):
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-10)
    else:
        assert actual == expected


def differential(cfg, prices, times, signals=None, openings=None, partitions=None, asks=None):
    signals, openings = signals or {}, openings or {}
    streams, zones, candidates, windows = frames(prices, times, signals, openings)
    if asks is not None:
        streams["ask"] = asks
    engine = VectorizedExecutionReplay(cfg, "test")
    partitions = partitions or [len(streams)]
    batches = []
    accounts, feedback, actions, cycles, modifications = [], [], [], [], []
    offset = 0
    for stop in partitions:
        rows = streams.iloc[offset:stop]
        batch = engine.run(
            rows,
            zones.loc[zones.broker_day.isin(rows.broker_day)],
            candidates.loc[candidates.stream_tick.isin(rows.stream_tick)],
            windows.loc[windows.stream_tick.isin(rows.stream_tick)] if len(windows) else windows,
        )
        batches.append(batch)
        accounts.append(engine.accounts.copy())
        feedback.append(engine.feedback.copy())
        actions.append(engine.actions.copy())
        cycles.append(engine.cycles.copy())
        modifications.append(engine.modifications.copy())
        offset = stop
    tables = [pd.concat([batch[i] for batch in batches], ignore_index=True) for i in range(6)]
    account_table = pd.concat(accounts, ignore_index=True)
    feedback_table = pd.concat(feedback, ignore_index=True)
    action_table = pd.concat(actions, ignore_index=True)
    cycle_table = pd.concat(cycles, ignore_index=True)
    modification_table = pd.concat(modifications, ignore_index=True)
    reference = ExecutionReplay(cfg, "test")
    requested_stops = {}
    accept_modification = reference._accept_modification

    def record_modification(order, time):
        requested_stops[order.request_id] = order.desired_sl
        return accept_modification(order, time)

    reference._accept_modification = record_modification
    for tick, row in enumerate(streams.itertuples(index=False)):
        requested_stops.clear()
        bid, ask, time = row.bid, row.ask, row.precise_time
        reference._begin_tick(bid, ask)
        reference._session(time, bid, ask)
        reference._roll(
            row.broker_day, row.bar_time, row.bar_open, ZONES, deepcopy(openings.get(tick, [])), time, bid, ask
        )
        if not reference._restart(time, bid, ask):
            reference._settle(time, bid, ask)
            for c in signals.get(tick, []):
                if c.family == XauSignalFamily.BREAKOUT:
                    reference._breakout(c, time, bid, ask)
            for c in signals.get(tick, []):
                if c.family == XauSignalFamily.REVERSAL:
                    reference._submit(c, time, bid, ask)
            pullbacks = reference._pullbacks(time, bid, ask)
            previous_stops = {key: order.stop_loss for key, order in reference.orders.items()}
            reference._manage(time, bid, ask, ())
        else:
            pullbacks = []
        expected = reference._snapshot(bid, ask, pullbacks)
        orders = tables[0].loc[tables[0].stream_tick.eq(tick)]
        assert len(orders) == len(expected["orders"])
        for actual, original in zip(orders.to_dict("records"), expected["orders"], strict=True):
            for key, value in original.items():
                assert_value(actual["request_id" if key == "order_id" else key], value)
        positions = tables[3].loc[tables[3].stream_tick.eq(tick)]
        assert len(positions) == len(expected["positions"])
        for actual, original in zip(positions.to_dict("records"), expected["positions"], strict=True):
            for key, value in original.items():
                assert_value(actual[key], value)
        events = tables[4].loc[tables[4].stream_tick.eq(tick)]
        assert events[["request_id", "event", "time", "reason"]].to_dict("records") == [
            {key: event[key] for key in ("request_id", "event", "time", "reason")}
            for event in expected["execution_events"]
        ]
        for i, kind in ((1, "FILL"), (2, "CLOSE")):
            actual = tables[i].loc[tables[i].stream_tick.eq(tick)]
            original = [event for event in expected["execution_events"] if event["event"] == kind]
            assert len(actual) == len(original)
            for a, e in zip(actual.to_dict("records"), original, strict=True):
                order = reference.orders[e["request_id"]]
                assert a["request_id"] == order.request_id
                assert a["position_id"] == order.position_id
                for field in (
                    ("fill_price", "volume", "entry_cost") if i == 1 else ("close_price", "exit_cost", "realized_pnl")
                ):
                    key = "cost" if field == "entry_cost" else field
                    assert_value(a[key], getattr(order, field))
        changed = modification_table.loc[modification_table.stream_tick.eq(tick)]
        original_modifications = [e for e in expected["execution_events"] if e["event"] in ("MODIFY", "MODIFY_REJECT")]
        assert len(changed) == len(original_modifications)
        for actual, original in zip(changed.to_dict("records"), original_modifications, strict=True):
            assert actual["request_id"] == original["request_id"]
            assert_value(actual["previous_stop_loss"], previous_stops[original["request_id"]])
            assert_value(
                actual["requested_stop_loss"],
                requested_stops.get(original["request_id"], reference.orders[original["request_id"]].desired_sl),
            )
            assert_value(actual["resulting_stop_loss"], original["stop_loss"])
            assert_value(actual["take_profit"], original["take_profit"])
            assert actual["accepted"] == (original["event"] == "MODIFY")
        history = (
            cycle_table.loc[cycle_table.stream_tick.le(tick)]
            .groupby("cycle_id", sort=False)
            .tail(1)
            .sort_values("cycle_ordinal")
        )
        assert len(history) == len(reference.state.pullbacks)
        for actual, original in zip(history.to_dict("records"), reference.state.pullbacks, strict=True):
            for key in (
                "parent_breakout_id",
                "direction",
                "bar_offset",
                "active",
                "penetration_latched",
                "pending_active",
                "sequence",
                "broker_day",
                "order_ticket",
                "waiting_logged",
                "risk_waiting_logged",
            ):
                assert_value(actual[key], getattr(original, key))
            assert actual["zone_id"] == original.zone.id
        assert_value(
            account_table.loc[account_table.stream_tick.eq(tick)].iloc[0].daily_would_trigger_logged,
            reference.daily_would_trigger_logged,
        )
        actual_actions = action_table.loc[action_table.stream_tick.eq(tick)]
        assert len(actual_actions) == len(expected["actions"])
        for actual, original in zip(actual_actions.to_dict("records"), expected["actions"], strict=True):
            for key in (
                "request_id",
                "direction",
                "order_type",
                "entry_price",
                "stop_loss",
                "take_profit",
                "volume",
                "accepted",
            ):
                assert_value(actual[key], original[key])
            assert actual["candidate_id"] == original["candidate"]["candidate_id"]
            assert actual["parent_breakout_id"] == original["candidate"]["parent_breakout_id"]
        r = tables[5].loc[tables[5].stream_tick.eq(tick)]
        assert list(zip(r.candidate_id, r.rejection_code, strict=True)) == list(expected["entry_rejections"])
        account = account_table.loc[account_table.stream_tick.eq(tick)].iloc[0]
        for key in (
            "account_balance",
            "daily_net_realized_pnl",
            "daily_gross_loss",
            "daily_loss_locked",
            "operational_locked",
        ):
            assert_value(account[key], expected[key])
        risk = reference._risk(bid, ask)
        for key, value in zip(("open_risk", "pending_risk", "open_count", "free_margin"), risk, strict=True):
            assert_value(account[key], value)
        assert_value(account.risk_used, reference._risk_used(bid, ask))
        f = feedback_table.loc[feedback_table.stream_tick.eq(tick)]
        assert len(f) == len(expected["pullback_feedback"])
        for actual, original in zip(f.itertuples(index=False), expected["pullback_feedback"], strict=True):
            assert actual.zone_id == original.zone_id
            assert actual.direction == original.direction
            assert actual.fill_count == original.daily_fills
            assert bool(actual.pending_active) == original.pending_active
            assert bool(actual.filled) == original.filled
    assert scan.nopython_signatures
    return engine, tables


@pytest.mark.parametrize("side", [XauDirection.BUY, XauDirection.SELL])
@pytest.mark.parametrize("risk_mode", ["off", "net", "gross"])
@pytest.mark.parametrize("session_mode", ["carry", "pullback", "all"])
def test_market_lifecycle_all_risk_and_session_modes(side, risk_mode, session_mode):
    cfg = config(inputs=config().inputs.model_copy(update={"risk_mode": risk_mode, "session_mode": session_mode}))
    prices = [103.0, 109.2, 108.0, 96.0] if side == XauDirection.BUY else [99.0, 93.0, 94.0, 106.0]
    times = pd.date_range("2026-09-24", periods=4, freq="min", tz="UTC")
    differential(cfg, prices, times, {0: [candidate(side)]})


@pytest.mark.parametrize("operation", ["SUBMIT", "CLOSE", "CANCEL", "MODIFY"])
def test_batch_broker_rejections_preserve_failure_semantics(operation):
    cfg = config()
    economics = RejectedOperations(cfg.economics, {operation})
    cfg = ReplayConfig(economics, inputs=cfg.inputs)
    times = pd.DatetimeIndex(["2026-09-24 22:45", "2026-09-24 22:46", "2026-09-24 22:55"], tz="UTC")
    if operation == "CANCEL":
        prices, signals, openings = [101.8] * 3, {}, {0: [window()]}
    else:
        prices, signals, openings = [103.0, 109.2, 96.0], {0: [candidate()]}, {}
    engine, _ = differential(cfg, prices, times, signals, openings)
    # Only the independent scalar reference calls accepts; batch run never does.
    assert engine.kernel.p["initial_balance"] == cfg.initial_balance


@pytest.mark.parametrize("priority", [0, 1])
def test_pending_feedback_expiry_and_partition_inside_bar(priority):
    times = pd.DatetimeIndex(
        [
            "2026-09-24 00:00",
            "2026-09-24 00:01",
            "2026-09-24 00:02",
            "2026-09-24 00:15",
            "2026-09-24 00:30",
            "2026-09-24 00:45",
            "2026-09-24 01:00",
            "2026-09-24 01:15",
        ],
        tz="UTC",
    )
    differential(
        config(),
        [101.8, 101.8, 102.2, 101.8, 101.8, 101.8, 101.8, 103.0],
        times,
        openings={0: [window(priority)]},
        partitions=[2, 8],
    )


def test_daily_loss_reset_restart_and_duplicate_candidates():
    times = pd.DatetimeIndex(["2026-09-24 00:00", "2026-09-24 00:00", "2026-09-24 00:15", "2026-09-25 00:00"], tz="UTC")
    signals = {0: [candidate(name="A"), candidate(name="B")], 3: [candidate(bar="2026-09-25 00:00:00+00:00")]}
    differential(config(), [103.0, 103.0, 50.0, 103.0], times, signals, partitions=[3, 4])
    differential(config(restart_days=frozenset({"2026-09-24"})), [103.0, 103.0, 50.0, 103.0], times, signals)


@pytest.mark.parametrize("value", [1.005, 1.015, 2.675, 97.095, 103.105, 1.0049999999999999, -1.005])
def test_decimal_boundary(value):
    from application.xauusd_trading_strategy_1_vector.domain.robust import normalize_price

    assert decimal_price(value, 2) == normalize_price(value, 2)


def test_empty_and_repeated_partition_contract():
    streams, zones, candidates, windows = frames([103.0], pd.DatetimeIndex(["2026-09-24"], tz="UTC"), {}, {})
    engine = VectorizedExecutionReplay(config(), "test")
    assert all(table.empty for table in engine.run(streams.iloc[:0], zones, candidates, windows))
    engine.run(streams, zones, candidates, windows)
    with pytest.raises(ValueError, match="partitions"):
        engine.run(streams, zones, candidates, windows)


def test_scalar_callbacks_are_rejected_before_execution():
    cfg = config()

    class ScalarOnly:
        minimum_stop_distance = 0.0

    engine = VectorizedExecutionReplay(ReplayConfig(ScalarOnly(), inputs=cfg.inputs), "test")
    streams, zones, candidates, windows = frames([103.0], pd.DatetimeIndex(["2026-09-24"], tz="UTC"), {}, {})
    with pytest.raises(ValueError, match="prepare_batch"):
        engine.run(streams, zones, candidates, windows)


@pytest.mark.parametrize("mode", ["carry", "pullback", "all"])
def test_session_cutoff_boundaries_with_pending_and_open_positions(mode):
    cfg = config(inputs=config().inputs.model_copy(update={"session_mode": mode, "one_order_per_candle": False}))
    times = pd.DatetimeIndex(
        [
            "2026-09-24 22:54",
            "2026-09-24 22:54:30",
            "2026-09-24 22:54:59.999999999",
            "2026-09-24 22:55",
            "2026-09-24 22:59:59.999999999",
            "2026-09-24 23:00",
        ],
        tz="UTC",
    )
    differential(
        cfg, [101.8, 102.2, 101.8, 101.8, 101.8, 103.0], times, signals={0: [candidate()]}, openings={0: [window()]}
    )


def test_pending_can_fill_then_stop_on_the_same_wide_spread_tick():
    times = pd.date_range("2026-09-24", periods=2, freq="min", tz="UTC")
    _, tables = differential(config(), [101.8, 96.0], times, openings={0: [window()]}, asks=[101.9, 103.0])
    last = tables[4].loc[tables[4].stream_tick.eq(1)]
    assert last.event.tolist() == ["FILL", "CLOSE"]
    assert last.reason.tolist() == ["", "SL"]


def test_fill_time_position_cap_uses_insertion_order():
    cfg = config(inputs=config().inputs.model_copy(update={"max_positions": 1, "one_order_per_candle": False}))
    second = deepcopy(window())
    second.zone = ZONES[2]
    second.parent_breakout_id = "BO2"
    times = pd.date_range("2026-09-24", periods=2, freq="min", tz="UTC")
    _, tables = differential(cfg, [101.8, 108.0], times, openings={0: [window(), second]}, asks=[101.9, 113.0])
    assert "POSITION_CAP" in tables[4].reason.tolist()


def test_close_loss_cancels_pending_risk_before_later_admission():
    cfg = config(inputs=config().inputs.model_copy(update={"risk_percent": 6.0, "one_order_per_candle": False}))
    second = deepcopy(window())
    second.zone = ZONES[2]
    second.parent_breakout_id = "BO2"
    times = pd.date_range("2026-09-24", periods=2, freq="min", tz="UTC")
    _, tables = differential(cfg, [103.0, 96.0], times, signals={0: [candidate()]}, openings={0: [second]})
    assert "PORTFOLIO_RISK" in tables[4].reason.tolist()


def test_margin_rejection_consumes_attempt_and_reversal_fill_limit():
    from dataclasses import replace

    cfg = config()
    cfg = replace(cfg, economics=replace(cfg.economics, margin_per_lot=100000.0))
    times = pd.date_range("2026-09-24", periods=2, freq="min", tz="UTC")
    differential(
        cfg, [103.0, 103.0], times, signals={0: [candidate(name="A"), candidate(name="B")], 1: [candidate(name="C")]}
    )
    cfg = config(inputs=config().inputs.model_copy(update={"one_order_per_candle": False, "high_reversal_max": 2}))
    signals = {0: [candidate(family=XauSignalFamily.REVERSAL, name=name) for name in ("R1", "R2", "R3")]}
    _, tables = differential(cfg, [103.0, 96.0], times, signals=signals)
    assert len(tables[1]) == 2


def test_qa_discovery_records_would_lock_without_locking():
    cfg = config(inputs=config().inputs.model_copy(update={"qa_discovery": True, "qa_capital": 200.0}))
    times = pd.date_range("2026-09-24", periods=2, freq="min", tz="UTC")
    engine, _ = differential(cfg, [103.0, 50.0], times, signals={0: [candidate()]})
    assert engine.accounts.daily_would_trigger_logged.iloc[-1]
    assert not engine.accounts.daily_loss_locked.iloc[-1]
