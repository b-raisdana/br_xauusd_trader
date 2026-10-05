from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest
from pandera.errors import SchemaErrors
from test_vectorized_execution import candidate, window
from test_vectorized_tick_separation import Zones, inputs

from application.xauusd_trading_strategy_1_vector.domain.schema import PullbackFeedback
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
from domain.xau_usd.enums import XauDirection
from infrastructure.result_processing import io
from infrastructure.result_processing.io import ResultFilesManifest
from infrastructure.result_processing.parquet import read_parquet, write_parquet


def test_nested_values_round_trip_without_losing_types_or_mutating_source(tmp_path):
    signal = candidate()
    feedback = PullbackFeedback("z", XauDirection.BUY, 1, False, True)
    source = pd.DataFrame(
        {
            "breakout_signals": [(signal,)],
            "pullback_windows_opened": [(window(),)],
            "pullback_feedback": [(feedback,)],
            "action": [{"candidate": {"signal_time": signal.signal_time}, "direction": XauDirection.BUY}],
            "text": ["[ordinary text]"],
        }
    )
    before = source.copy(deep=True)
    path = write_parquet(source, "nested.parquet", tmp_path)
    assert path.name == "nested.parquet"
    actual = read_parquet(path)
    pd.testing.assert_frame_equal(source, before)
    pd.testing.assert_frame_equal(actual, source)
    assert isinstance(actual.breakout_signals.iloc[0][0], type(signal))
    assert isinstance(actual.pullback_feedback.iloc[0][0], PullbackFeedback)
    assert isinstance(actual.action.iloc[0]["direction"], XauDirection)


def test_manifest_categories_are_distinct_and_reads_wait_for_writes(tmp_path):
    ticks, candles = inputs()
    day = ticks.broker_day.iloc[0]
    manifest = ResultFilesManifest(root=tmp_path)
    try:
        assert manifest.save_daily_ticks(day, ticks) is manifest
        manifest.save_daily_candles(day, candles)
        assert VectorizedXauUsdStrategy(Zones()).process_tick_data(manifest) is manifest
        categories = ["ticks", "candles", "signal_state", "per_candle_states", "signals", "windows"]
        paths = [manifest.get_path(category, day) for category in categories]
        assert len(set(paths)) == 6
        assert all(path.exists() for path in paths)
        pd.testing.assert_frame_equal(manifest.read_daily_ticks(day), ticks)
        pd.testing.assert_frame_equal(manifest.read_daily_candles(day), candles)
        assert len(manifest.read_daily_signal_state(day)) == len(ticks)
        assert len(manifest.read_daily_candles_temp_state(day)) == ticks.bar_time.nunique()
    finally:
        manifest.close()


@pytest.mark.parametrize("defect", ["missing", "dtype", "precision"])
@pytest.mark.parametrize("boundary", ["save", "read"])
def test_typed_manifest_boundaries_reject_invalid_frames(tmp_path, defect, boundary):
    ticks, _ = inputs()
    day = ticks.broker_day.iloc[0]
    broken = ticks.copy()
    if defect == "missing":
        broken = broken.drop(columns="ask")
    elif defect == "dtype":
        broken["bid"] = "invalid"
    else:
        level = broken.index.names.index("precise_time")
        broken.index = broken.index.set_levels(broken.index.levels[level].as_unit("us"), level=level)
    manifest = ResultFilesManifest(root=tmp_path)
    try:
        with pytest.raises(SchemaErrors):
            if boundary == "save":
                manifest.save_daily_ticks(day, broken)
            else:
                path = write_parquet(broken, "broken", tmp_path)
                manifest.ticks[day] = (path, True)
                manifest.read_daily_ticks(day)
    finally:
        manifest.close()


def test_failed_write_is_reported_and_manifest_executors_are_independent(tmp_path, monkeypatch):
    ticks, _ = inputs()
    day = ticks.broker_day.iloc[0]
    first = ResultFilesManifest(root=tmp_path)
    second = ResultFilesManifest(root=tmp_path)
    first.close()
    second.save_daily_ticks(day, ticks)
    assert second.is_write_successful("ticks", day)
    second.close()

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr(io, "write_parquet", fail)
    failed = ResultFilesManifest(root=tmp_path)
    failed.save_daily_ticks(day, ticks)
    with pytest.raises(OSError, match="disk failure"):
        failed.read_daily_ticks(day)
    assert not failed.ticks[day][1]
    with pytest.raises(OSError, match="disk failure"):
        failed.close()


def test_manifest_survives_serialization(tmp_path):
    ticks, _ = inputs()
    day = ticks.broker_day.iloc[0]
    original = ResultFilesManifest(root=tmp_path)
    original.save_daily_ticks(day, ticks)
    original.close()
    restored = ResultFilesManifest.model_validate_json(original.model_dump_json())
    try:
        pd.testing.assert_frame_equal(restored.read_daily_ticks(day), ticks)
    finally:
        restored.close()


def test_schema_columns_have_one_declaration():
    path = Path("src/application/xauusd_trading_strategy_1_vector/domain/schema.py")
    tree = ast.parse(path.read_text())
    columns = []
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        for field in cls.body:
            if (
                isinstance(field, ast.AnnAssign)
                and isinstance(field.annotation, ast.Subscript)
                and ast.unparse(field.annotation.value) == "pt.Series"
            ):
                columns.append(field.target.id)
    assert len(columns) == len(set(columns))


def test_process_tick_data_rejects_dataframe_handoff():
    ticks, _ = inputs()
    with pytest.raises((TypeError, AttributeError)):
        VectorizedXauUsdStrategy(Zones()).process_tick_data(ticks)


def test_empty_bar_processing_returns_both_typed_frames():
    from application.xauusd_trading_strategy_1_vector.domain.schema import PerCandleState, PerTickState

    ticks, candles = inputs()
    strategy = VectorizedXauUsdStrategy(Zones())
    empty_ticks = ticks.iloc[:0]
    state = strategy._initialize_per_tick_temp_state(empty_ticks)
    output, candle_state = strategy._process_bar_boundaries(empty_ticks, state, candles.iloc[:0])
    assert output.empty and candle_state.empty
    PerTickState.validate(output, lazy=True)
    PerCandleState.validate(candle_state, lazy=True)


def test_runner_does_not_silently_sort_nonchronological_ticks(tmp_path, monkeypatch):
    from application.xauusd_trading_strategy_1_vector.runner import run_vectorized_strategy

    ticks, candles = inputs()
    zones = pd.DataFrame(
        {"lower": [100.0], "upper": [102.0], "priority": ["high"], "enabled": [True]},
        index=pd.MultiIndex.from_arrays(
            [["15min"], pd.DatetimeIndex([ticks.broker_day.iloc[0]]).as_unit("ns")],
            names=["timeframe", "date"],
        ),
    )
    # monkeypatch.setattr(io.app_config, "path_of_data", tmp_path)
    with pytest.raises(ValueError, match="chronological"):
        run_vectorized_strategy(ticks.iloc[::-1], candles, zones)
