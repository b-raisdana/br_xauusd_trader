from datetime import UTC

import pandas as pd
import pandera
import pytest

from domain.schemas.xau_usd.strategy_v1 import M15TrendResult, ZeroLagMacdResult
from domain.xau_usd.strategy_v1 import m15_trend, rsi, unique_zone_membership, zero_lag_macd
from domain.xau_usd.strategy_v1.config import StrategyV1Config


def candles(high: list[float], low: list[float], start: str = "2026-07-29") -> pd.DataFrame:
    index = pd.date_range(start, periods=len(high), freq="15min", tz=UTC)
    return pd.DataFrame({"high": high, "low": low}, index=index)


def test_m15_trend_uses_three_closed_candles_and_strict_same_candle_conditions():
    result = m15_trend(candles([10, 12, 11, 11], [8, 6, 9, 6]), StrategyV1Config())
    assert result.trend.tolist() == [0, 0, 1, 0]
    assert result.eligible.tolist() == [False, False, True, True]


def test_m15_trend_is_none_if_both_directions_or_neither_direction_match():
    both = m15_trend(candles([10, 12, 9], [8, 9, 7]), StrategyV1Config())
    neither = m15_trend(candles([10, 11, 9], [8, 7, 9]), StrategyV1Config())
    assert both.trend.iloc[-1] == 0
    assert neither.trend.iloc[-1] == 0


def test_m15_trend_resets_reference_window_at_utc_day_boundary():
    index = pd.DatetimeIndex(
        ["2026-07-29 23:30Z", "2026-07-29 23:45Z", "2026-07-30 00:00Z"],
    )
    data = pd.DataFrame({"high": [10, 11, 20], "low": [8, 9, 1]}, index=index)
    result = m15_trend(data, StrategyV1Config())
    assert result.trend.tolist() == [0, 0, 0]
    assert result.eligible.tolist() == [False, False, False]


def test_rsi_uses_only_close_series_and_returns_expected_extreme_values():
    config = StrategyV1Config(rsi_period=2)
    index = pd.date_range("2026-07-29", periods=5, freq="5min", tz=UTC)
    rising = rsi(pd.Series([1, 2, 3, 4, 5], index=index), config)
    falling = rsi(pd.Series([5, 4, 3, 2, 1], index=index), config)
    assert rising.iloc[-1] == 100.0
    assert falling.iloc[-1] == 0.0


def test_rsi_is_undefined_for_a_flat_market():
    config = StrategyV1Config(rsi_period=2)
    index = pd.date_range("2026-07-29", periods=5, freq="5min", tz=UTC)
    result = rsi(pd.Series([1.0, 1.0, 1.0, 1.0, 1.0], index=index), config)
    assert pd.isna(result.iloc[-1])


def test_strategy_configuration_rejects_inconsistent_thresholds():
    with pytest.raises(ValueError, match="RSI buy threshold"):
        StrategyV1Config(rsi_buy_max=70.0, rsi_sell_min=30.0)


def test_zone_overlap_interior_has_no_match_and_unique_outer_regions_match():
    prices = pd.Series([100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 104.0])
    zone_index = pd.MultiIndex.from_arrays(
        [
            pd.to_datetime(["2026-07-29T00:00Z"] * 2).astype("datetime64[ns, UTC]"),
            ["A", "B"],
        ],
        names=["date", "zone_id"],
    )
    zones = pd.DataFrame(
        {
            "lower": [100.0, 101.0],
            "upper": [102.0, 103.0],
            "importance_class": ["normal"] * 2,
            "direction": [0] * 2,
            "note": [None, None],
        },
        index=zone_index,
    )
    result = unique_zone_membership(prices, zones)
    assert result.fillna("").tolist() == ["A", "A", "", "", "", "B", "B", ""]


def test_zero_lag_macd_returns_signal_histogram_and_previous_closed_histogram():
    config = StrategyV1Config(
        zero_lag_macd_fast_period=2,
        zero_lag_macd_slow_period=3,
        zero_lag_macd_signal_period=2,
    )
    index = pd.date_range("2026-07-29", periods=20, freq="5min", tz=UTC)
    close = pd.Series([100.0 + (step % 5) for step in range(20)], index=index)
    result = zero_lag_macd(close, config)
    assert result.columns.tolist() == ["macd", "signal", "histogram", "histogram_previous"]
    assert result.histogram.iloc[-1] == pytest.approx(result.macd.iloc[-1] - result.signal.iloc[-1])
    assert result.histogram_previous.iloc[-1] == pytest.approx(result.histogram.iloc[-2])


def test_indicator_inputs_require_monotonic_unique_timezone_aware_times():
    close = pd.Series([1.0, 2.0], index=pd.DatetimeIndex(["2026-07-29", "2026-07-28"]))
    with pytest.raises(ValueError, match="UTC-aware"):
        rsi(close, StrategyV1Config())


def test_m15_trend_schema_rejects_missing_price_column():
    bad = candles([10, 11, 12], [8, 9, 10]).drop(columns="high")
    with pytest.raises(pandera.errors.SchemaErrors):
        m15_trend(bad, StrategyV1Config())


def test_m15_trend_schema_rejects_uncoercible_price_dtype():
    bad = candles([10, 11, 12], [8, 9, 10])
    bad["high"] = "invalid"
    with pytest.raises(pandera.errors.SchemaErrors):
        m15_trend(bad, StrategyV1Config())


def test_m15_trend_output_schema_rejects_missing_column():
    result = m15_trend(candles([10, 11, 12], [8, 9, 10]), StrategyV1Config())
    with pytest.raises(pandera.errors.SchemaErrors):
        M15TrendResult.validate(result.drop(columns="eligible"), lazy=True)


def test_m15_trend_output_schema_rejects_microsecond_index():
    result = m15_trend(candles([10, 11, 12], [8, 9, 10]), StrategyV1Config())
    result.index = result.index.astype("datetime64[us, UTC]")
    with pytest.raises(pandera.errors.SchemaErrors):
        M15TrendResult.validate(result, lazy=True)


def test_zero_lag_macd_output_schema_rejects_missing_column():
    index = pd.date_range("2026-07-29", periods=20, freq="5min", tz=UTC)
    close = pd.Series([100.0 + (step % 5) for step in range(20)], index=index)
    result = zero_lag_macd(close, StrategyV1Config())
    with pytest.raises(pandera.errors.SchemaErrors):
        ZeroLagMacdResult.validate(result.drop(columns="histogram_previous"), lazy=True)


def test_zero_lag_macd_output_schema_rejects_microsecond_index():
    index = pd.date_range("2026-07-29", periods=20, freq="5min", tz=UTC)
    close = pd.Series([100.0 + (step % 5) for step in range(20)], index=index)
    result = zero_lag_macd(close, StrategyV1Config())
    result.index = result.index.astype("datetime64[us, UTC]")
    with pytest.raises(pandera.errors.SchemaErrors):
        ZeroLagMacdResult.validate(result, lazy=True)
