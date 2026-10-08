from types import SimpleNamespace

import pandas as pd
import pytest
from test_vectorized_tick_separation import inputs

from application.xauusd_trading_strategy_1_vector.backtest import _extract_replay_signals
from application.xauusd_trading_strategy_1_vector.domain.columnar import SignalTable
from application.xauusd_trading_strategy_1_vector.domain.replay import LinearReplayEconomics, ReplayConfig
from application.xauusd_trading_strategy_1_vector.domain.robust import RobustInputs
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
from application.xauusd_trading_strategy_1_vector.vectorized_replay import VectorizedExecutionReplay
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily
from domain.xau_usd.models import XauZone
from infrastructure.result_processing.io import ResultFilesManifest


def test_replay_joins_candidates_to_tick_ordinals_with_duplicate_timestamps(tmp_path):
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

    engine = VectorizedExecutionReplay(config, "test")
    orders, fills, closes, positions, events, rejections = engine.run(streams, zones, candidates)

    assert len(orders) == 2, (engine.replay.orders, engine.replay.rejections, events)
    assert len(fills) == 1
    assert len(closes) == 1
    assert len(positions) == 2
    assert events.event.tolist() == ["SUBMIT", "FILL", "CLOSE"]
    assert events.stream_id.tolist() == ["test"] * 3
    assert events.stream_tick.tolist() == [1, 1, 2]
    assert events.event_ordinal.tolist() == [0, 1, 0]
    assert fills.iloc[0].fill_time == time
    assert (fills.stream_id == "test").all()
    assert fills.stream_tick.tolist() == [1]
    assert fills.iloc[0].cost == 0.1
    assert closes.stream_tick.tolist() == [2]
    assert closes.iloc[0].exit_cost == 0.2
    assert positions.stream_tick.tolist() == [1, 2]
    assert rejections.to_dict("records") == [
        {
            "stream_id": "test",
            "stream_tick": 1,
            "rejection_ordinal": 0,
            "candidate_id": "BO2",
            "rejection_code": 3,
        }
    ]
    manifest = ResultFilesManifest(root=tmp_path)
    try:
        manifest.save_daily_rejections(time.to_pydatetime(), rejections)
        manifest.wait_for_writes()
        pd.testing.assert_frame_equal(
            manifest.read_daily_execution_artifact("rejections", time.to_pydatetime()), rejections
        )
    finally:
        manifest.close()


def test_replay_state_continues_across_day_partition():
    day_one = pd.Timestamp("2026-09-24 00:00", tz="UTC")
    day_two = pd.Timestamp("2026-09-25 00:00", tz="UTC")
    economics = LinearReplayEconomics(
        100.0,
        100.0,
        10.0,
        20.0,
        0.0,
        {
            "2026-09-24": pd.Timestamp("2026-09-24 23:00", tz="UTC"),
            "2026-09-25": pd.Timestamp("2026-09-25 23:00", tz="UTC"),
        },
    )
    config = ReplayConfig(
        economics,
        inputs=RobustInputs(
            enable_direct_breakout=True,
            breakout_normal_only=False,
            pullback_min_space=0,
            high_reversal_min_space=0,
        ),
    )
    stream_columns = {
        "stream_id": ["test"],
        "stream_tick": [0],
        "precise_time": [day_one],
        "broker_day": ["2026-09-24"],
        "bar_time": [day_one.floor("15min")],
        "bar_open": [101.0],
        "bid": [103.0],
        "ask": [103.2],
    }
    day_one_streams = pd.DataFrame(stream_columns)
    day_two_streams = pd.DataFrame(
        {
            **stream_columns,
            "stream_tick": [1],
            "precise_time": [day_two],
            "broker_day": ["2026-09-25"],
            "bar_time": [day_two.floor("15min")],
            "bar_open": [110.0],
            "bid": [110.0],
            "ask": [110.2],
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
    day_two_zones = zones.assign(broker_day="2026-09-25")
    candidates = pd.DataFrame(
        {
            "stream_tick": [0],
            "candidate_id": ["BO1"],
            "parent_breakout_id": [""],
            "bar_id": [str(day_one.floor("15min"))],
            "zone_id": ["z"],
            "family": [int(XauSignalFamily.BREAKOUT)],
            "direction": [int(XauDirection.BUY)],
            "order_type": [int(XauOrderType.MARKET)],
            "signal_time": [day_one],
            "entry_price": [103.0],
        }
    )
    engine = VectorizedExecutionReplay(config, "test")

    _, first_fills, first_closes, _, first_events, _ = engine.run(day_one_streams, zones, candidates)
    second_orders, second_fills, second_closes, second_positions, second_events, _ = engine.run(
        day_two_streams,
        day_two_zones,
        candidates.iloc[:0],
    )

    assert len(first_fills) == 1
    assert first_closes.empty
    assert first_events.event.tolist() == ["SUBMIT", "FILL"]
    assert second_events.event.tolist() == ["CLOSE"]
    assert second_events.stream_tick.tolist() == [1]
    assert second_closes.close_reason.tolist() == ["TP"]
    assert second_positions.position_status.tolist() == [3]
    assert second_orders.request_id.nunique() == 1
    assert second_fills.empty


def test_replay_rejects_candidate_events_outside_stream_partition():
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

    with pytest.raises(ValueError, match="outside this replay partition"):
        VectorizedExecutionReplay(ReplayConfig(economics), "test").run(streams, zones, candidates)


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
    assert entries.P2.tolist() == [False, True, False, False]
    assert exits.P1.tolist() == [False, False, True, False]
    assert exits.P2.tolist() == [False, False, False, True]
    assert short_entries.P1.tolist() == [False] * 4
    assert short_entries.P2.tolist() == [False, True, False, False]
    assert short_exits.P1.tolist() == [False] * 4
    assert short_exits.P2.tolist() == [False, False, False, True]


def test_strategy_extracts_native_candidates_and_persists_execution_artifacts(tmp_path):
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
        windows=pd.DataFrame(),
    )

    class Zones:
        def get_zones_for_day(self, day):
            return [XauZone("below", 90, 92), XauZone("z", 100, 102, 1), XauZone("target", 110, 112)]

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
    manifest = ResultFilesManifest(root=tmp_path)
    try:
        strategy._run_execution_replay(
            manifest,
            "2026-09-18",
            ticks,
            candles,
            [(("test", "XAUUSD!"), result)],
        )
        manifest.wait_for_writes()

        orders = pd.read_parquet(manifest.get_path("orders", pd.Timestamp("2026-09-18").to_pydatetime()))
        positions = pd.read_parquet(manifest.get_path("positions", pd.Timestamp("2026-09-18").to_pydatetime()))
        assert orders.candidate_id.eq("BO1").any()
        assert positions.position_id.eq("POS-test_XAUUSD!-1").any()
        assert len(manifest.read_daily_execution_artifact("fills", pd.Timestamp("2026-09-18"))) == 2
        assert manifest.read_daily_execution_artifact("closes", pd.Timestamp("2026-09-18")).empty
        events = manifest.read_daily_execution_artifact("execution_events", pd.Timestamp("2026-09-18"))
        assert {"SUBMIT", "FILL"} <= set(events.event)
    finally:
        manifest.close()
