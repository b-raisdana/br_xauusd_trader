import numpy as np
import pandas as pd
import pytest
from pandera.errors import SchemaErrors
from vectorized_fixtures import calculate_manifest, candles_from_ticks, prepared_ticks

from application.xauusd_trading_strategy_1_vector import VectorizedXauUsdStrategy
from application.xauusd_trading_strategy_1_vector.config.trend_points import trend_columns, trend_point_count
from application.xauusd_trading_strategy_1_vector.domain.schema import PerTickState
from application.xauusd_trading_strategy_1_vector.domain.state import (
    begin_trend_day,
    process_trend_tick,
    record_trend_candle,
    trend_references,
)
from application.xauusd_trading_strategy_1_vector.engagement import update_zone_engagement
from application.xauusd_trading_strategy_1_vector.trend import (
    compute_reference_high,
    compute_reference_low,
    compute_references,
)
from domain.xau_usd.models import XauZone
from infrastructure.result_processing.__main__ import (
    generate_order_management_columns,
    generate_position_tracking_columns,
)


class EmptyZones:
    def get_zones_for_day(self, day):
        return []


def test_initialized_state_satisfies_the_per_tick_contract():
    frame = ticks(["2026-09-18 00:00", "2026-09-18 00:15"], [100, 101])
    state = VectorizedXauUsdStrategy(EmptyZones())._initialize_per_tick_temp_state(frame)

    assert PerTickState.validate(state, lazy=True).equals(state)


@pytest.mark.parametrize("defect", ["missing_column", "extra_column"])
def test_state_column_guard_rejects_contract_breaks(defect):
    frame = ticks(["2026-09-18 00:00"], [100])
    state = VectorizedXauUsdStrategy(EmptyZones())._initialize_per_tick_temp_state(frame)
    broken = state.drop(columns="trend_count") if defect == "missing_column" else state.assign(unexpected=0)

    with pytest.raises(ValueError, match="violate the contract"):
        VectorizedXauUsdStrategy(EmptyZones())._process_day_boundaries(broken)


@prepared_ticks
def ticks(times, bids, broker="test", symbol="XAUUSD"):
    times = pd.DatetimeIndex(pd.to_datetime(times, utc=True)).as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [[broker] * len(times), [symbol] * len(times), times, times.normalize()],
        names=["broker", "symbol", "precise_time", "date"],
    )
    return pd.DataFrame({"bid": np.asarray(bids, dtype=float), "ask": np.asarray(bids, dtype=float) + 0.2}, index=index)


def calculate(frame, cache=None):
    strategy = VectorizedXauUsdStrategy(cache or EmptyZones())
    result, _ = calculate_manifest(strategy, frame, candles_from_ticks(frame))
    assert result.index.equals(frame.sort_index(kind="stable").index)
    return result


def scalar_trend(frame):
    previous_day = previous_bar = None
    reference = begin_trend_day()
    high = low = 0.0
    expected = []
    for (_, _, timestamp, _), row in frame.iterrows():
        day, bar = timestamp.date(), timestamp.floor("15min")
        if day != previous_day:
            reference = begin_trend_day()
        elif bar != previous_bar:
            record_trend_candle(reference, high, low)
        if bar != previous_bar:
            high = low = row.bid
        else:
            high, low = max(high, row.bid), min(low, row.bid)
        trend = process_trend_tick(reference, row.bid)
        _, reference_high, reference_low = trend_references(reference)
        expected.append((reference.count, reference_high, reference_low, trend.value))
        previous_day, previous_bar = day, bar
    return np.asarray(expected)


def test_trend_matches_scalar_contract_with_gaps_duplicates_and_day_reset():
    rng = np.random.default_rng(12)
    times = pd.date_range("2026-09-17 23:00", periods=650, freq="min", tz="UTC")
    times = times.delete(np.arange(75, 115)).insert(150, times[150 + 40])
    prices = 2000 + rng.normal(size=len(times)).cumsum()
    frame = ticks(times, prices)
    original = frame.copy(deep=True)
    per_tick_state = calculate(frame)
    actual = per_tick_state[["trend_count", "reference_high", "reference_low", "trend"]].to_numpy()
    np.testing.assert_array_equal(actual, scalar_trend(frame))
    pd.testing.assert_frame_equal(frame, original)
    assert per_tick_state.day_active.all() and per_tick_state.bar_active.all()


@pytest.mark.parametrize("length", [0, 1, 2, 15, 16, 30, 31, 60, 61])
def test_empty_singleton_and_bootstrap_have_causal_history(length):
    frame = ticks(pd.date_range("2026-09-18", periods=length, freq="min", tz="UTC"), np.arange(length) + 100)
    per_tick_state = calculate(frame)
    if length:
        np.testing.assert_array_equal(
            per_tick_state[["trend_count", "reference_high", "reference_low", "trend"]].to_numpy(), scalar_trend(frame)
        )


def test_future_ticks_do_not_change_past_state():
    frame = ticks(pd.date_range("2026-09-18", periods=100, freq="min", tz="UTC"), np.arange(100) + 100)
    prefix = calculate(frame.iloc[:38])
    frame.iloc[38:, 0] = 99999
    extended = calculate(frame)
    pd.testing.assert_frame_equal(prefix, extended.iloc[:38])


def test_broker_symbol_partitions_and_daily_zone_loading_are_isolated():
    class DailyZones:
        def __init__(self):
            self.days = []

        def get_zones_for_day(self, day):
            self.days.append(day)
            return EmptyZones().get_zones_for_day(day)

    times = ["2026-09-18 23:59", "2026-09-19 00:00"]
    frame = pd.concat([ticks(times, [100, 999]), ticks(times, [200, 1], symbol="OTHER")])
    cache = DailyZones()
    per_tick_state = calculate(frame, cache)
    assert cache.days == list(pd.to_datetime(["2026-09-18", "2026-09-18", "2026-09-19", "2026-09-19"], utc=True))
    assert per_tick_state.trend_count.eq(0).all()
    assert per_tick_state.reference_high.eq(0).all()


# def test_bar_processing_never_iterates_groupby_or_applies_rows(monkeypatch):
#     frame = ticks(pd.date_range("2026-09-18", periods=100, freq="min", tz="UTC"), np.arange(100) + 100)
#     strategy = VectorizedXauUsdStrategy(EmptyZones())
#     per_tick_state = strategy._initialize_per_tick_temp_state(frame)
#     per_candle_state = strategy._process_day_boundaries(per_tick_state)

#     def forbidden(*args, **kwargs):
#         raise AssertionError("Python iteration over rows or bars is forbidden")

#     candle_df = candles_from_ticks(per_tick_state)
#     monkeypatch.setattr(DataFrameGroupBy, "agg", forbidden)
#     monkeypatch.setattr(DataFrameGroupBy, "__iter__", forbidden)
#     monkeypatch.setattr(pd.DataFrame, "apply", forbidden)
#     strategy._update_trend(strategy._process_bar_boundaries(per_tick_state, candle_df))


def test_unsorted_input_is_rejected():
    frame = ticks(["2026-09-18 00:01", "2026-09-18 00:00"], [1, 2])
    with pytest.raises(ValueError, match="chronological"):
        calculate(frame)


def test_reference_reduction_ignores_unused_slots():
    counts = [0, 1, 2, 3]
    recorded = {"high": [100, 5, 5, 5], "low": [-100, 5, 5, 5]}
    fillers = {"high": 100.0, "low": -100.0}
    per_tick_state = pd.DataFrame({"trend_count": counts})
    for slot, filler in fillers.items():
        for index in range(trend_point_count()):
            per_tick_state[trend_columns(slot)[index]] = [
                value if count > index else filler for value, count in zip(recorded[slot], counts, strict=True)
            ]
    expected_high = [compute_reference_high(row) for _, row in per_tick_state.iterrows()]
    expected_low = [compute_reference_low(row) for _, row in per_tick_state.iterrows()]
    compute_references(per_tick_state)
    assert per_tick_state.reference_high.tolist() == expected_high
    assert per_tick_state.reference_low.tolist() == expected_low


def test_engagement_latches_within_bar_and_resets_at_next_open():
    frame = ticks(["2026-09-18 00:00", "2026-09-18 00:01", "2026-09-18 00:02", "2026-09-18 00:15"], [99, 100, 103, 103])
    strategy = VectorizedXauUsdStrategy(EmptyZones())
    per_tick_state, _ = strategy._process_bar_boundaries(
        frame, strategy._initialize_per_tick_temp_state(frame), candles_from_ticks(frame)
    )
    update_zone_engagement(frame, per_tick_state, [XauZone("z", 100, 102)])
    assert per_tick_state.buy_engaged.tolist() == [False, True, True, False]
    assert per_tick_state.sell_engaged.tolist() == [False] * 4


def test_snapshot_ids_are_preserved_with_duplicate_timestamps(tmp_path):
    from test_vectorized_execution import candidate, config

    from application.xauusd_trading_strategy_1_vector.actions import generate_actions
    from infrastructure.result_processing.__main__ import merge_results_with_candles
    from infrastructure.result_processing.io import ResultFilesManifest

    frame = ticks(["2026-09-24 00:00"] * 4, [103, 103, 103, 103])
    day = frame.broker_day.iloc[0]
    strategy = VectorizedXauUsdStrategy(EmptyZones())
    state = strategy._initialize_per_tick_temp_state(frame)
    state["bar_open"] = 101.0
    state["breakout_signals"] = pd.Series([(candidate(),), (), (), ()], index=frame.index)
    from test_vectorized_execution import ZONES

    state = generate_actions(frame, state, ZONES, config())
    manifest = ResultFilesManifest(root=tmp_path)
    try:
        manifest.save_daily_ticks(day, frame)
        manifest.save_daily_candles(day, candles_from_ticks(frame))
        manifest.save_daily_ticks_temp_state(day, state)
        merge_results_with_candles(manifest)
        generate_order_management_columns(manifest)
        generate_position_tracking_columns(manifest)
        positions = manifest.read_positions(day)
        assert positions.index.equals(frame.index)
        assert positions.order_id.nunique() == 1
        assert positions.position_id.nunique() == 1
        assert positions.position_current_price.tolist() == [103.0] * 4
    finally:
        manifest.close()


def test_daily_zone_dataframe_selection_and_strategy_adapter():
    from application.xauusd_trading_strategy_1_vector import ZoneCache

    dates = pd.to_datetime(["2026-09-18", "2026-09-18 23:59", "2026-09-19"], format="mixed", utc=True).as_unit("ns")
    index = pd.MultiIndex.from_arrays([["15min"] * 3, dates], names=["timeframe", "date"])
    zones = pd.DataFrame(
        {
            "lower": [99.0, 105.0, 199.0],
            "upper": [101.0, 107.0, 201.0],
            "priority": ["high", "normal", "normal"],
            "enabled": [True, False, True],
        },
        index=index,
    )
    cache = ZoneCache(zones)
    strategy = VectorizedXauUsdStrategy(cache)
    selected = strategy._get_zones_for_group(
        pd.DataFrame({"broker_day": pd.to_datetime(["2026-09-18"], utc=True).as_unit("ns")})
    )
    assert [(zone.low, zone.high, zone.priority) for zone in selected] == [(99.0, 101.0, 1)]
    selected[0].low = 0.0
    assert cache.get_zones_for_day("2026-09-18")[0].low == 99.0
    assert zones.iloc[0, 0] == 99.0
    empty = strategy._get_zones_for_group(
        pd.DataFrame({"broker_day": pd.to_datetime(["2026-09-20"], utc=True).as_unit("ns")})
    )
    assert empty == []
    assert len(cache.get_zones_for_day("2026-09-18")) == 1
    assert cache.get_zones_for_day("2026-09-20") == []
    frame = ticks(["2026-09-18", "2026-09-19"], [100, 200])
    per_tick_state = calculate(frame, cache)
    assert per_tick_state.buy_engaged.tolist() == [True, True]
    assert per_tick_state.sell_engaged.tolist() == [True, True]
    assert zones.lower.tolist() == [99.0, 105.0, 199.0]


@pytest.mark.parametrize("defect", ["missing_column", "wrong_dtype", "wrong_index_precision"])
def test_zone_group_rejects_invalid_frame(defect):
    from application.xauusd_trading_strategy_1_vector import ZoneCache

    zones = pd.DataFrame(
        {"lower": [99.0], "upper": [101.0], "priority": ["normal"], "enabled": [True]},
        index=pd.MultiIndex.from_arrays(
            [["15min"], pd.DatetimeIndex(["2026-09-18"], tz="UTC").as_unit("ns")],
            names=["timeframe", "date"],
        ),
    )
    if defect == "missing_column":
        zones = zones.drop(columns="lower")
    elif defect == "wrong_dtype":
        zones["lower"] = zones["lower"].astype(str)
    else:
        zones.index = zones.index.set_levels(zones.index.levels[1].as_unit("us"), level="date")

    with pytest.raises(SchemaErrors):
        ZoneCache(zones)


def test_supplied_candles_match_tick_history_with_gaps_and_day_reset():
    frame = ticks(pd.date_range("2026-09-17 23:00", periods=100, freq="min", tz="UTC"), np.arange(100) + 100)
    frame = frame.drop(frame.index[20:35])
    candles = candles_from_ticks(frame)
    strategy = VectorizedXauUsdStrategy(EmptyZones())
    state, _ = calculate_manifest(strategy, frame, candles.sample(frac=1, random_state=1))
    pd.testing.assert_frame_equal(state, calculate(frame))


def test_supplied_candle_ranges_are_used_only_after_close():
    frame = ticks(["2026-09-18 00:00", "2026-09-18 00:15", "2026-09-18 00:30"], [100, 101, 102])
    candles = candles_from_ticks(frame)
    candles["high"] = [110.0, 120.0, 9999.0]
    candles["low"] = [90.0, 80.0, 1.0]
    strategy = VectorizedXauUsdStrategy(EmptyZones())
    state, _ = calculate_manifest(strategy, frame, candles)
    np.testing.assert_array_equal(state.trend_high_0, [0, 110, 110])
    np.testing.assert_array_equal(state.trend_high_1, [0, 0, 120])
    prefix = state.copy()
    candles.iloc[2, candles.columns.get_indexer(["high", "low"])] = [99999.0, 0.0]
    state, _ = calculate_manifest(strategy, frame, candles)
    pd.testing.assert_frame_equal(state, prefix)
    with pytest.raises(ValueError, match="cover every observed tick bar"):
        calculate_manifest(strategy, frame, candles.iloc[:1])


def test_per_candle_state_preserves_all_days_and_resets_between_batches():
    frame = ticks(
        ["2026-09-17 23:30", "2026-09-17 23:31", "2026-09-17 23:45", "2026-09-18 00:00"],
        [100, 104, 102, 103],
    )
    strategy = VectorizedXauUsdStrategy(EmptyZones())
    state, per_candle_state = calculate_manifest(strategy, frame, candles_from_ticks(frame))
    assert per_candle_state.index.names == ["date", "timeframe", "broker", "symbol", "bar_time"]
    assert len(state) == 4
    assert len(per_candle_state) == 3
    np.testing.assert_array_equal(per_candle_state.high, [104, 102, 103])
    np.testing.assert_array_equal(per_candle_state.trend_count, [0, 1, 0])
    np.testing.assert_array_equal(per_candle_state.trend_high_0, [0, 104, 0])
    state, per_candle_state = calculate_manifest(strategy, frame.iloc[-1:], candles_from_ticks(frame.iloc[-1:]))
    assert len(per_candle_state) == 1
    assert per_candle_state.trend_count.iloc[0] == 0
    state, per_candle_state = calculate_manifest(strategy, frame.iloc[:0], candles_from_ticks(frame.iloc[:0]))
    assert state.empty
    assert per_candle_state.empty
