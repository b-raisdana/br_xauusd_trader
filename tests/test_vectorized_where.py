from itertools import product

import numpy as np
import pandas as pd
import pytest
from vectorized_fixtures import candles_from_ticks, complete_tick_state

from application.xauusd_trading_strategy_1_vector.engagement import update_zone_engagement
from application.xauusd_trading_strategy_1_vector.signals import generate_reversal_signals
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
from application.xauusd_trading_strategy_1_vector.trend import (
    compute_reference_high,
    compute_reference_low,
    compute_references,
)
from domain.xau_usd.models import XauZone


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_references_match_scalar_with_nan_infinity_and_signed_zero(count):
    values = np.array(list(product([np.nan, -np.inf, -2.0, -0.0, 0.0, 3.0, np.inf], repeat=3)))
    per_tick_state = pd.DataFrame(values, columns=[f"trend_high_{i}" for i in range(3)])
    per_tick_state[[f"trend_low_{i}" for i in range(3)]] = values
    per_tick_state["trend_count"] = count
    expected_high = per_tick_state.apply(compute_reference_high, axis=1).to_numpy()
    expected_low = per_tick_state.apply(compute_reference_low, axis=1).to_numpy()

    assert compute_references(per_tick_state) is per_tick_state

    for side, expected in (("high", expected_high), ("low", expected_low)):
        actual = per_tick_state[f"reference_{side}"].to_numpy()
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(np.signbit(actual), np.signbit(expected))


def test_empty_reference_columns_remain_float():
    per_tick_state = pd.DataFrame(
        columns=["trend_count", *[f"trend_{side}_{i}" for side in ("high", "low") for i in range(3)]]
    )
    compute_references(per_tick_state)
    assert per_tick_state.reference_high.dtype == per_tick_state.reference_low.dtype == np.dtype(float)
    assert per_tick_state.empty


@pytest.mark.parametrize("length", [0, 1, 5])
def test_engagement_without_zones_stays_false(length):
    per_tick_state = pd.DataFrame(
        {"bid": np.arange(length, dtype=float), "bar_time": pd.date_range("2026-09-18", periods=length)}
    )
    per_tick_state["bid"] = per_tick_state["bid"].astype(float)
    per_tick_state["bar_time"] = pd.to_datetime(per_tick_state["bar_time"], utc=True).dt.as_unit("ns")
    per_tick_state[["buy_engaged", "sell_engaged", "multi_zone_tick_gap"]] = False
    per_tick_state = complete_tick_state(per_tick_state)
    update_zone_engagement(per_tick_state, per_tick_state, [])
    assert not per_tick_state[["multi_zone_tick_gap", "buy_engaged", "sell_engaged"]].to_numpy().any()


@pytest.mark.parametrize(
    "bids,expected",
    [
        (
            [99, 100, 103, 106, 99, 102, 105, 104],
            [[0, 0, 0], [0, 1, 0], [0, 1, 0], [0, 1, 0], [1, 1, 0], [0, 1, 0], [0, 1, 1], [0, 1, 1]],
        ),
        (
            [106, 105, 104, 99, 106, 104, 102, 100],
            [[0, 0, 0], [0, 0, 1], [0, 0, 1], [0, 0, 1], [1, 0, 1], [0, 0, 1], [0, 1, 1], [0, 1, 1]],
        ),
    ],
)
def test_engagement_matches_captured_cross_gap_and_bar_reset_state(bids, expected):
    per_tick_state = pd.DataFrame(
        {
            "bid": bids,
            "bar_time": pd.to_datetime(["2026-09-18"] * 6 + ["2026-09-18 00:15"] * 2, format="mixed", utc=True),
        },
        index=[0, 0, 1, 2, 3, 3, 4, 4],
    )
    per_tick_state["bid"] = per_tick_state["bid"].astype(float)
    per_tick_state["bar_time"] = pd.to_datetime(per_tick_state["bar_time"], utc=True).dt.as_unit("ns")
    per_tick_state[["buy_engaged", "sell_engaged", "multi_zone_tick_gap"]] = False
    per_tick_state = complete_tick_state(per_tick_state)
    update_zone_engagement(per_tick_state, per_tick_state, [XauZone("a", 100, 102), XauZone("b", 104, 105)])
    np.testing.assert_array_equal(per_tick_state[["multi_zone_tick_gap", "buy_engaged", "sell_engaged"]], expected)


def test_previous_prices_reset_at_bar_and_day_boundaries():
    from vectorized_fixtures import prepared_ticks

    times = pd.to_datetime(
        ["2026-09-18 23:30", "2026-09-18 23:30", "2026-09-18 23:30", "2026-09-18 23:45", "2026-09-19 00:00"], utc=True
    ).as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [["test"] * 5, ["XAUUSD"] * 5, times, times.normalize()], names=["broker", "symbol", "precise_time", "date"]
    )
    ticks = prepared_ticks(
        lambda: pd.DataFrame(
            {"bid": [99.0, 100.0, 101.0, 105.0, 106.0], "ask": [99.2, 100.2, 101.2, 105.2, 106.2]}, index=index
        )
    )()
    strategy = VectorizedXauUsdStrategy(None)
    state = strategy._initialize_per_tick_temp_state(ticks)
    result, _ = strategy._process_bar_boundaries(ticks, state, candles_from_ticks(ticks))
    assert result.bar_open.tolist() == [99.0, 99.0, 99.0, 105.0, 106.0]
    assert result.trend_count.tolist() == [0, 0, 0, 1, 0]


def test_reversal_scaffold_preserves_rows_with_duplicate_index():
    per_tick_state = pd.DataFrame(
        {
            "bid": [98.0, 99.0, 97.0],
            "trend": [1, 1, 2],
            "multi_zone_tick_gap": False,
            "bar_time": pd.to_datetime(["2026-09-18"] * 3, utc=True),
        },
        index=[0, 0, 1],
    )
    per_tick_state["bar_time"] = per_tick_state.bar_time.dt.as_unit("ns")
    per_tick_state = complete_tick_state(per_tick_state)
    expected = per_tick_state.assign(
        bar_time=per_tick_state.bar_time.dt.as_unit("ns"),
        reversal_signals=pd.Series([(), (), ()], index=per_tick_state.index, dtype=object),
    )
    result = generate_reversal_signals(per_tick_state, per_tick_state, [XauZone("a", 100, 102)])
    pd.testing.assert_frame_equal(result, expected)
