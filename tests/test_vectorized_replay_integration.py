from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from test_vectorized_tick_separation import inputs

from application.xauusd_trading_strategy_1_vector import the_strategy as strategy_module
from application.xauusd_trading_strategy_1_vector.backtest import _extract_replay_signals
from application.xauusd_trading_strategy_1_vector.domain.columnar import SignalTable
from application.xauusd_trading_strategy_1_vector.domain.replay import LinearReplayEconomics, ReplayConfig
from application.xauusd_trading_strategy_1_vector.domain.robust import RobustInputs
from application.xauusd_trading_strategy_1_vector.execution_batch import adapter as adapter_module
from application.xauusd_trading_strategy_1_vector.execution_batch.adapter import BatchReplay
from application.xauusd_trading_strategy_1_vector.execution_batch.scan import scan
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily
from domain.xau_usd.models import XauZone


def _batch_replay_harness(monkeypatch, config):
    engine = BatchReplay.__new__(BatchReplay)
    engine.config, engine.stream_id = config, "test"
    engine.identities = pd.Index([""], dtype="str")
    engine.days = pd.Index([], dtype="str")
    engine.zone_keys = pd.Index([], dtype="str")
    engine.zone_table = pd.DataFrame()
    engine.cash_multiplier = None
    engine.last_tick = engine.last_time = -1
    engine.kernel = SimpleNamespace(clear_outputs=lambda: None)
    engine.normalize_zones = lambda frame: setattr(
        engine, "zone_keys", pd.Index(frame.broker_day + "|" + frame.zone_id)
    )
    engine.tables = lambda accounts: accounts
    captured = []
    monkeypatch.setattr(adapter_module, "scan", lambda *args: captured.append(args))
    return engine, captured


def test_candidate_preparation_preserves_tick_ordinals_with_duplicate_timestamps(monkeypatch):
    time = pd.Timestamp("2026-09-24 00:00", tz="UTC")
    economics = LinearReplayEconomics(
        100.0,
        100.0,
        10.0,
        20.0,
        0.0,
        {"2026-09-24": pd.Timestamp("2026-09-24 23:00", tz="UTC")},
    )
    config = ReplayConfig(
        economics,
        inputs=RobustInputs(
            enable_direct_breakout=True,
            breakout_normal_only=False,
            pullback_min_space=0,
            high_reversal_min_space=0,
            one_order_per_candle=True,
            max_positions=1,
        ),
    )
    streams = pd.DataFrame(
        {
            "stream_id": ["test"] * 3,
            "stream_tick": [0, 1, 2],
            "precise_time": [time, time, time + pd.Timedelta(minutes=1)],
            "broker_day": ["2026-09-24"] * 3,
            "bar_time": [time.floor("15min")] * 3,
            "bar_open": [101.0] * 3,
            "bid": [103.0, 103.0, 96.0],
            "ask": [103.2, 103.2, 96.2],
        }
    )
    zones = pd.DataFrame(
        {
            "zone_id": ["below", "z", "target"],
            "broker_day": ["2026-09-24"] * 3,
            "high": [92.0, 102.0, 112.0],
            "low": [90.0, 100.0, 110.0],
            "priority": [0, 1, 0],
        }
    )
    candidates = pd.DataFrame(
        {
            "stream_tick": [1, 1],
            "candidate_id": ["BO1", "BO2"],
            "parent_breakout_id": ["", ""],
            "bar_id": [str(time.floor("15min"))] * 2,
            "zone_id": ["z", "z"],
            "family": [int(XauSignalFamily.BREAKOUT)] * 2,
            "direction": [int(XauDirection.BUY)] * 2,
            "order_type": [int(XauOrderType.MARKET)] * 2,
            "signal_time": [time, time],
            "entry_price": [103.0, 103.0],
        }
    )

    engine, captured = _batch_replay_harness(monkeypatch, config)

    engine.run(streams, zones, candidates)

    _, ticks, _, _, _, candidate_ids, candidate_prices, _, pointers, _ = captured[0]
    assert ticks[:, 0].tolist() == [0, 1, 2]
    assert candidate_ids[:, 0].tolist() == [1, 2]
    assert engine.identities.take(candidate_ids[:, 0]).tolist() == ["BO1", "BO2"]
    assert candidate_prices.tolist() == [103.0, 103.0]
    assert pointers[1, :2].tolist() == [0, 2]
    assert pointers[2, :2].tolist() == [2, 2]


def test_scan_preserves_open_position_on_day_rollover():
    class Kernel:
        p = {"session_mode": 0}
        active = [0]
        active_cycles = []
        oi = [np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.int64)]
        of = [np.array([103.0, 90.0, 120.0, 0.0, 0.0, 103.0, 103.0, 0.0, 0.0, 0.0])]
        accept = np.ones(4, dtype=np.int64)
        day, bar, attempted = 0, -1, 4
        net, gross, locked, would_lock = 3.0, 2.0, 1, 1
        balance, bid, ask, structure_buy, structure_sell = 200.0, 110.0, 110.2, np.nan, np.nan

        def risk(self):
            return 0.0, 0.0, 1, self.balance

        def used(self):
            return 0.0

        def budget(self):
            return 100.0

        def manage(self):
            pass

        def snapshot(self):
            pass

    kernel = Kernel()
    time = pd.Timestamp("2026-09-25 00:00", tz="UTC")
    scan.py_func(
        kernel,
        np.array([[1, time.value, 1, time.value, 0, 0, -1, -1]], dtype=np.int64),
        np.array([[110.0, 110.2, np.nan, np.nan]]),
        np.array([[100.0, 10.0, 0.0, 0.0, 0.0]]),
        np.ones((1, 4), dtype=np.int64),
        np.empty((0, 6), dtype=np.int64),
        np.empty(0, dtype=np.float64),
        np.empty((0, 4), dtype=np.int64),
        np.zeros((2, 3), dtype=np.int64),
        np.empty((1, 9), dtype=np.float64),
    )

    assert kernel.day == 1
    assert kernel.oi[0][0] == 1
    assert kernel.balance == 200.0
    assert (kernel.net, kernel.gross, kernel.locked, kernel.would_lock, kernel.attempted) == (0, 0, 0, 0, -1)


def test_replay_rejects_candidate_events_outside_stream_partition(monkeypatch):
    time = pd.Timestamp("2026-09-24 00:00", tz="UTC")
    economics = LinearReplayEconomics(
        100.0,
        100.0,
        10.0,
        20.0,
        0.0,
        {"2026-09-24": pd.Timestamp("2026-09-24 23:00", tz="UTC")},
    )
    streams = pd.DataFrame(
        {
            "stream_id": ["test"],
            "stream_tick": [0],
            "precise_time": [time],
            "broker_day": ["2026-09-24"],
            "bar_time": [time.floor("15min")],
            "bar_open": [101.0],
            "bid": [103.0],
            "ask": [103.2],
        }
    )
    zones = pd.DataFrame(
        {
            "zone_id": ["z"],
            "broker_day": ["2026-09-24"],
            "high": [102.0],
            "low": [100.0],
            "priority": [1],
        }
    )
    candidates = pd.DataFrame(
        {
            "stream_tick": [1],
            "candidate_id": ["BO1"],
            "parent_breakout_id": [""],
            "bar_id": [str(time.floor("15min"))],
            "zone_id": ["z"],
            "family": [int(XauSignalFamily.BREAKOUT)],
            "direction": [int(XauDirection.BUY)],
            "order_type": [int(XauOrderType.MARKET)],
            "signal_time": [time],
            "entry_price": [103.0],
        }
    )

    engine, captured = _batch_replay_harness(monkeypatch, ReplayConfig(economics))
    with pytest.raises(ValueError, match="outside this replay partition"):
        engine.run(streams, zones, candidates)
    assert not captured


def test_report_projection_builds_separate_signals_for_overlapping_replay_positions():
    times = pd.date_range("2026-09-24", periods=4, freq="min", tz="UTC")
    index = pd.MultiIndex.from_arrays(
        [
            ["test"] * 4,
            ["XAUUSD!"] * 4,
            times.normalize(),
            times,
        ],
        names=["broker", "symbol", "date", "precise_time"],
    )
    ticks = pd.DataFrame(
        {
            "bid": [100.0, 101.0, 102.0, 103.0],
            "stream_tick": [0, 1, 2, 3],
        },
        index=index,
    )
    fills = pd.DataFrame(
        {
            "stream_id": ["test_XAUUSD!", "test_XAUUSD!"],
            "stream_tick": [0, 1],
            "position_id": ["P1", "P2"],
            "position_direction": [int(XauDirection.BUY), int(XauDirection.SELL)],
            "fill_price": [100.2, 101.2],
        }
    )
    closes = pd.DataFrame(
        {
            "stream_id": ["test_XAUUSD!", "test_XAUUSD!"],
            "stream_tick": [2, 3],
            "position_id": ["P1", "P2"],
            "position_direction": [int(XauDirection.BUY), int(XauDirection.SELL)],
            "close_price": [102.0, 103.0],
        }
    )

    close, entries, exits, short_entries, short_exits = _extract_replay_signals(ticks, fills, closes)

    assert close.columns.tolist() == ["P1", "P2"]
    assert close.P1.tolist() == [100.0, 101.0, 102.0, 103.0]
    assert close.P2.tolist() == [100.0, 101.0, 102.0, 103.0]
    assert entries.P1.tolist() == [True, False, False, False]
    assert entries.P2.tolist() == [False, False, False, False]
    assert exits.P1.tolist() == [False, False, True, False]
    assert exits.P2.tolist() == [False, False, False, False]
    assert short_entries.P1.tolist() == [False] * 4
    assert short_entries.P2.tolist() == [False, True, False, False]
    assert short_exits.P1.tolist() == [False] * 4
    assert short_exits.P2.tolist() == [False, False, False, True]


def test_strategy_adapts_native_candidates_and_dispatches_execution_artifacts(monkeypatch):
    ticks, candles = inputs()
    economics = LinearReplayEconomics(
        100.0,
        100.0,
        10.0,
        20.0,
        0.0,
        {"2026-09-18": pd.Timestamp("2026-09-18 23:00", tz="UTC")},
    )
    candidate = pd.DataFrame(
        {
            "stream_tick": [1],
            "candidate_id": ["BO1"],
            "parent_breakout_id": [""],
            "bar_id": [str(ticks.bar_time.iloc[1])],
            "zone_id": ["z"],
            "family": [int(XauSignalFamily.BREAKOUT)],
            "direction": [int(XauDirection.BUY)],
            "order_type": [int(XauOrderType.MARKET)],
            "signal_time": [ticks.index.get_level_values("precise_time")[1]],
            "entry_price": [103.0],
        },
        index=ticks.index[[1]],
    )
    signals = SignalTable.validate(candidate, lazy=True)
    result = SimpleNamespace(
        ticks=SimpleNamespace(stream_tick=pd.Series(range(len(ticks)), index=ticks.index)),
        signals=signals,
        windows=None,
    )

    class Zones:
        def get_zones_for_day(self, day):
            return [XauZone("below", 90, 92), XauZone("z", 100, 102, 1), XauZone("target", 110, 112)]

    replay_calls = []

    class Replay:
        def __init__(self, replay_config, stream_id):
            self.stream_id = stream_id
            self.modifications = self.cycles = self.accounts = self.feedback = self.actions = pd.DataFrame()
            self.kernel = SimpleNamespace(multiplier=100.0)
            self.zone_keys = pd.Index([], dtype="str")

        def run(self, streams, zones, candidates, windows, replay_candles):
            replay_calls.append((self, streams, zones, candidates, windows, replay_candles))
            return tuple(pd.DataFrame() for _ in range(6))

    class Manifest:
        meta = {}

        def __init__(self):
            self.saved = {}

        def __getattr__(self, name):
            if not name.startswith("save_daily_"):
                raise AttributeError(name)
            return lambda day, table: self.saved.__setitem__(name, table.copy())

    monkeypatch.setattr(
        strategy_module, "_new_vectorized_execution_replay", lambda config, stream_id: Replay(config, stream_id)
    )

    strategy = VectorizedXauUsdStrategy(
        Zones(),
        ReplayConfig(
            economics,
            inputs=RobustInputs(
                enable_direct_breakout=True,
                breakout_normal_only=False,
                pullback_min_space=0,
                high_reversal_min_space=0,
            ),
        ),
    )
    manifest = Manifest()
    strategy._run_execution_replay(manifest, "2026-09-18", ticks, candles, [(("test", "XAUUSD!"), result)])

    replay, streams, zones, prepared_candidates, windows, replay_candles = replay_calls[0]
    assert replay.stream_id == "test_XAUUSD!"
    assert streams.stream_tick.tolist() == [0, 1, 2, 3]
    assert prepared_candidates.candidate_id.tolist() == ["BO1"]
    assert zones.zone_id.tolist() == ["below", "z", "target"]
    assert windows is None
    assert not replay_candles.empty
    assert set(manifest.saved) == {
        "save_daily_orders",
        "save_daily_fills",
        "save_daily_closes",
        "save_daily_execution_events",
        "save_daily_rejections",
        "save_daily_positions",
        "save_daily_modifications",
        "save_daily_cycles",
        "save_daily_accounts",
        "save_daily_actions",
        "save_daily_feedback",
    }
    assert manifest.meta["initial_balance"] == 200.0
    assert manifest.meta["cash_per_price_unit_per_lot"] == 100.0
