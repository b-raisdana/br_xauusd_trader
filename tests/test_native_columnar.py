"""Scalar-oracle characterization; row iteration is confined to the oracle."""

import ast
from dataclasses import asdict
from pathlib import Path
from threading import Event

import numpy as np
import pandas as pd
import pytest
from pandera.errors import SchemaErrors
from vectorized_fixtures import candles_from_ticks, with_native_bootstrap

from application.xauusd_trading_strategy_1_vector.columnar import process_columns
from application.xauusd_trading_strategy_1_vector.domain.columnar import (
    ColumnarMarket,
    SignalTable,
    SignalTickState,
    WindowTable,
)
from application.xauusd_trading_strategy_1_vector.domain.robust import RobustInputs
from application.xauusd_trading_strategy_1_vector.market import MarketState
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
from domain.xau_usd.models import XauZone

ZONES = [XauZone("low", 70.0, 72.0), XauZone("z", 100.0, 102.0, 1), XauZone("high", 130.0, 132.0)]


def data(seed=1, bars=20, ticks_per_bar=12):
    rng = np.random.default_rng(seed)
    times = pd.date_range(
        "2026-09-24 23:00", periods=bars * ticks_per_bar, freq=pd.Timedelta(minutes=15) / ticks_per_bar, tz="UTC"
    ).as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [["test"] * len(times), ["XAUUSD"] * len(times), times.normalize(), times],
        names=["broker", "symbol", "date", "precise_time"],
    )
    bid = rng.choice(
        [69.0, 70.0, 71.0, 72.0, 73.0, 99.0, 100.0, 101.0, 101.8, 102.0, 103.0, 129.0, 130.0, 131.0, 132.0, 133.0],
        len(times),
    )
    ticks = pd.DataFrame(
        {"bid": bid, "ask": bid + 0.2, "last": bid, "volume": np.uint64(0), "flags": np.uint32(0), "volume_real": 0.0},
        index=index,
    )
    ticks = VectorizedXauUsdStrategy.add_bar_time_n_broker_day(ticks)
    return ticks, with_native_bootstrap(candles_from_ticks(ticks)).astype({"volume": "float64"})


def oracle(ticks, candles, inputs, market=None, position_offset=0, zones=None):
    market = market or MarketState(inputs)
    zones = ZONES if zones is None else zones
    rows, signals, windows = [], [], []
    times = candles.index.get_level_values("bar_time")
    for position, (time, tick) in enumerate(
        zip(ticks.index.get_level_values("precise_time"), ticks.itertuples(), strict=True)
    ):
        location = times.get_loc(tick.bar_time)
        history = candles.iloc[max(0, location - 102) : location][["open", "high", "low", "close"]].to_numpy()
        row = market.step(
            time,
            str(tick.broker_day.date()),
            tick.bar_time,
            float(candles.open.iloc[location]),
            tick.bid,
            tick.ask,
            history,
            zones,
        )
        rows.append(row)
        for family in ("breakout", "reversal", "pullback"):
            for candidate in row[f"{family}_signals"]:
                signals.append({"stream_tick": position + position_offset, **asdict(candidate)})
        for window in row["pullback_windows_opened"]:
            windows.append(
                {
                    "stream_tick": position + position_offset,
                    "parent_breakout_id": window.parent_breakout_id,
                    "zone_id": window.zone.id,
                    "zone_low": window.zone.low,
                    "zone_high": window.zone.high,
                    "priority": window.zone.priority,
                    "direction": int(window.direction),
                    "bar_offset": window.bar_offset,
                    "active": window.active,
                    "penetration_latched": window.penetration_latched,
                    "breakout_bar_time": window.breakout_bar_time,
                    "broker_day": window.broker_day,
                }
            )
    return pd.DataFrame(rows, index=ticks.index), pd.DataFrame(signals), pd.DataFrame(windows), market


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("window_bars", [1, 3, 5, 10])
def test_columns_and_signal_tables_match_scalar(seed, window_bars):
    ticks, candles = data(seed)
    inputs = RobustInputs(window_bars=window_bars)
    expected, signals, windows, scalar = oracle(ticks, candles, inputs)
    market = ColumnarMarket(inputs)
    result = process_columns(ticks, candles, market, ZONES)
    columns = result.ticks.columns.drop("stream_tick")
    pd.testing.assert_frame_equal(result.ticks[columns], expected[columns], check_like=True)
    if not signals.empty:
        actual = result.signals.reset_index(drop=True)[signals.columns]
        pd.testing.assert_frame_equal(actual, signals, check_dtype=False)
    else:
        assert result.signals.empty
    if not windows.empty:
        pd.testing.assert_frame_equal(
            result.windows.reset_index(drop=True)[windows.columns], windows, check_dtype=False
        )
    else:
        assert result.windows.empty
    assert market.previous_bid == scalar.previous_bid
    assert market.trend == scalar.trend
    assert market.zones == scalar.state.zones
    assert market.breakout_sequence == scalar.state.breakout_sequence
    if any(w.active for w in scalar.state.pullbacks):
        expected_windows = pd.DataFrame(
            [
                {
                    "parent_breakout_id": w.parent_breakout_id,
                    "zone_id": w.zone.id,
                    "direction": int(w.direction),
                    "active": w.active,
                    "bar_offset": w.bar_offset,
                    "penetration_latched": w.penetration_latched,
                }
                for w in scalar.state.pullbacks
                if w.active
            ]
        )
        pd.testing.assert_frame_equal(market.windows[expected_windows.columns], expected_windows, check_dtype=False)


def test_chunked_stream_including_duplicate_timestamps_matches_whole():
    ticks, candles = data()
    ticks = pd.concat([ticks.iloc[:5], ticks.iloc[4:]])
    whole = process_columns(ticks, candles, ColumnarMarket(RobustInputs()), ZONES)
    market = ColumnarMarket(RobustInputs())
    cuts = [0, 1, 7, 12, 49, 51, len(ticks)]
    parts = [
        process_columns(ticks.iloc[start:end], candles, market, ZONES)
        for start, end in zip(cuts[:-1], cuts[1:], strict=True)
    ]
    for name in ("ticks", "signals", "windows"):
        actual = pd.concat([getattr(part, name) for part in parts])
        pd.testing.assert_frame_equal(actual, getattr(whole, name))


def test_bar_ids_and_window_times_preserve_nanoseconds():
    ticks, candles = data()
    delta = pd.Timedelta(nanoseconds=123456789)
    ticks["bar_time"] += delta
    for frame, level in ((ticks, "precise_time"), (candles, "bar_time")):
        number = frame.index.names.index(level)
        frame.index = frame.index.set_levels(frame.index.levels[number] + delta, level=level)
    expected, signals, windows, scalar = oracle(ticks, candles, RobustInputs())
    result = process_columns(ticks, candles, ColumnarMarket(), ZONES)
    pd.testing.assert_frame_equal(result.signals.reset_index(drop=True)[signals.columns], signals, check_dtype=False)
    pd.testing.assert_frame_equal(result.windows.reset_index(drop=True)[windows.columns], windows, check_dtype=False)


def test_resume_same_bar_retains_history_but_reports_supplied_native_open():
    ticks, candles = data()
    inputs = RobustInputs()
    _, _, _, scalar = oracle(ticks.iloc[:5], candles, inputs)
    market = ColumnarMarket(inputs)
    process_columns(ticks.iloc[:5], candles, market, ZONES)
    changed = candles.copy()
    current = changed.index.get_level_values("bar_time") == ticks.bar_time.iloc[0]
    changed.loc[current, "open"] = 105.0
    changed.iloc[0, changed.columns.get_loc("high")] = 1000.0
    expected, signals, windows, scalar = oracle(ticks.iloc[5:], changed, inputs, scalar, position_offset=5)
    result = process_columns(ticks.iloc[5:], changed, market, ZONES)
    columns = result.ticks.columns.drop("stream_tick")
    pd.testing.assert_frame_equal(result.ticks[columns], expected[columns], check_like=True)
    pd.testing.assert_frame_equal(result.signals.reset_index(drop=True)[signals.columns], signals, check_dtype=False)


def test_new_day_uses_outgoing_zones_before_replacing_them():
    ticks, candles = data()
    split = int(ticks.broker_day.eq(ticks.broker_day.iloc[0]).sum())
    inputs = RobustInputs()
    _, _, _, scalar = oracle(ticks.iloc[:split], candles, inputs)
    market = ColumnarMarket(inputs)
    process_columns(ticks.iloc[:split], candles, market, ZONES)
    changed_zones = [XauZone("other", 100.0, 120.0)]
    expected, signals, windows, scalar = oracle(
        ticks.iloc[split:], candles, inputs, scalar, position_offset=split, zones=changed_zones
    )
    result = process_columns(ticks.iloc[split:], candles, market, changed_zones)
    columns = result.ticks.columns.drop("stream_tick")
    pd.testing.assert_frame_equal(result.ticks[columns], expected[columns], check_like=True)
    pd.testing.assert_frame_equal(result.signals.reset_index(drop=True)[signals.columns], signals, check_dtype=False)
    assert market.zones == scalar.state.zones


def test_empty_input_has_valid_primitive_outputs():
    ticks, candles = data()
    result = process_columns(ticks.iloc[:0], candles.iloc[:0], ColumnarMarket(RobustInputs()), [])
    assert result.ticks.empty and result.candles.empty and result.signals.empty and result.windows.empty
    for model, frame in ((SignalTickState, result.ticks), (SignalTable, result.signals), (WindowTable, result.windows)):
        model.validate(frame, lazy=True)


@pytest.mark.parametrize("column,value", [("bid", None), ("bid", "invalid")])
def test_invalid_inputs_rejected(column, value):
    ticks, candles = data()
    bad = ticks.drop(columns=column) if value is None else ticks.assign(**{column: value})
    with pytest.raises(SchemaErrors):
        process_columns(bad, candles, ColumnarMarket(RobustInputs()), ZONES)


def test_output_contract_rejects_missing_column_and_wrong_timestamp_precision():
    ticks, candles = data()
    state = process_columns(ticks, candles, ColumnarMarket(RobustInputs()), ZONES).ticks
    with pytest.raises(SchemaErrors):
        SignalTickState.validate(state.drop(columns="trend"), lazy=True)
    bad = state.copy()
    level = bad.index.names.index("precise_time")
    bad.index = bad.index.set_levels(bad.index.levels[level].as_unit("us"), level=level)
    with pytest.raises(SchemaErrors):
        SignalTickState.validate(bad, lazy=True)


def test_production_does_not_use_scalar_step_or_tick_iteration(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Row processing is forbidden")

    ticks, candles = data()
    monkeypatch.setattr(MarketState, "step", forbidden)
    monkeypatch.setattr(pd.DataFrame, "itertuples", forbidden)
    monkeypatch.setattr(pd.DataFrame, "iterrows", forbidden)
    process_columns(ticks, candles, ColumnarMarket(RobustInputs()), ZONES)


def test_native_algorithm_has_no_row_callbacks_or_array_conversion():
    forbidden = {"iterrows", "itertuples", "apply", "map", "to_numpy", "step"}
    for path in Path("src/application/xauusd_trading_strategy_1_vector").glob("columnar*.py"):
        tree = ast.parse(path.read_text())
        assert not [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr in forbidden]


@pytest.mark.parametrize(
    "inputs",
    [
        RobustInputs(enable_pullback=False),
        RobustInputs(normal_pullback_max=0),
        RobustInputs(high_pullback=False),
        RobustInputs(explicit_controls=False, legacy_profile=1),
    ],
)
def test_pullback_controls_preserve_scalar_results(inputs):
    ticks, candles = data(7)
    expected, signals, windows, scalar = oracle(ticks, candles, inputs)
    result = process_columns(ticks, candles, ColumnarMarket(inputs), ZONES)
    columns = result.ticks.columns.drop("stream_tick")
    pd.testing.assert_frame_equal(result.ticks[columns], expected[columns], check_like=True)
    pd.testing.assert_frame_equal(result.signals.reset_index(drop=True)[signals.columns], signals, check_dtype=False)


def test_columnar_persistence_uses_no_python_row_serialization(tmp_path, monkeypatch):
    from infrastructure.result_processing.io import ResultFilesManifest

    ticks, candles = data()
    result = process_columns(ticks, candles, ColumnarMarket(), ZONES)

    def forbidden(*args, **kwargs):
        raise AssertionError("Python serialization callback is forbidden")

    monkeypatch.setattr(pd.Series, "map", forbidden)
    with_manifest = ResultFilesManifest(root=tmp_path)
    day = ticks.broker_day.iloc[0]
    try:
        with_manifest.save_daily_signal_state(day, result.ticks)
        with_manifest.save_daily_signals(day, result.signals)
        with_manifest.save_daily_windows(day, result.windows)
        pd.testing.assert_frame_equal(with_manifest.read_daily_signal_state(day), result.ticks)
        pd.testing.assert_frame_equal(with_manifest.read_daily_signals(day), result.signals)
        pd.testing.assert_frame_equal(with_manifest.read_daily_windows(day), result.windows)
    finally:
        with_manifest.close()


def test_async_source_snapshot_isolated_from_caller_mutation(tmp_path, monkeypatch):
    from infrastructure.result_processing import io
    from infrastructure.result_processing.io import ResultFilesManifest

    ticks, candles = data(bars=1, ticks_per_bar=3)
    original = ticks.copy(deep=True)
    started, release = Event(), Event()
    writer = io.write_parquet

    def blocked_write(frame, name, folder):
        started.set()
        assert release.wait(timeout=5)
        return writer(frame, name, folder)

    monkeypatch.setattr(io, "write_parquet", blocked_write)
    manifest = ResultFilesManifest(root=tmp_path)
    day = ticks.broker_day.iloc[0]
    try:
        manifest.save_daily_ticks(day, ticks)
        assert started.wait(timeout=5)
        ticks.loc[:, "bid"] = 999.0
        release.set()
        pd.testing.assert_frame_equal(manifest.read_daily_ticks(day), original)
    finally:
        release.set()
        manifest.close()


def test_export_preserves_interleaved_streams_with_duplicate_ticks(tmp_path, monkeypatch):
    from test_vectorized_tick_separation import inputs

    from application.xauusd_trading_strategy_1_vector.reporting import save_results_to_file
    from application.xauusd_trading_strategy_1_vector.runner import run_vectorized_strategy
    from infrastructure.result_processing import io

    a, ca = inputs()
    b, cb = inputs("SECOND", 100.0)
    ticks = pd.concat([a.iloc[:1], a, b.iloc[:1], b]).sort_index(
        level="precise_time", sort_remaining=False, kind="stable"
    )
    day = ticks.broker_day.iloc[0]
    zones = pd.DataFrame(
        {"lower": [100.0], "upper": [102.0], "priority": ["high"], "enabled": [True]},
        index=pd.MultiIndex.from_arrays([["15min"], pd.DatetimeIndex([day])], names=["timeframe", "date"]),
    )
    monkeypatch.setattr(io.app_config, "path_of_data", tmp_path)
    manifest = run_vectorized_strategy(ticks, pd.concat([ca, cb]), zones)
    output = tmp_path / "interleaved.parquet"
    save_results_to_file(manifest, str(output))
    actual = pd.read_parquet(output)
    assert actual.bid.tolist() == ticks.bid.tolist()
    assert actual.stream_tick.tolist() == ticks.groupby(level=["broker", "symbol"], sort=False).cumcount().tolist()


def test_native_export_rejects_missing_state_rows():
    from application.xauusd_trading_strategy_1_vector.reporting import _native_market_rows

    ticks, candles = data(bars=1, ticks_per_bar=3)
    state = process_columns(ticks, candles, ColumnarMarket(), ZONES).ticks
    with pytest.raises(SchemaErrors):
        _native_market_rows(ticks, state.iloc[:-1])
