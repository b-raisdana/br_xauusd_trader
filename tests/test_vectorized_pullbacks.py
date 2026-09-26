from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
from pandera.errors import SchemaErrors
from vectorized_fixtures import prepared_ticks

from application.xauusd_trading_strategy_1_vector.domain.schema import (
    PullbackFeedback,
    XauPullbackWindowState,
)
from application.xauusd_trading_strategy_1_vector.signals import generate_breakout_signals, generate_pullback_signals
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily
from domain.xau_usd.models import XauZone


def state(prices, times=None):
    times = (
        pd.date_range("2026-09-24", periods=len(prices), freq="min", tz="UTC")
        if times is None
        else pd.to_datetime(times, utc=True, format="mixed")
    )
    times = times.as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [["broker"] * len(prices), ["XAUUSD"] * len(prices), times, times.normalize()],
        names=["broker", "symbol", "precise_time", "date"],
    )
    ticks = pd.DataFrame(
        {"bid": np.asarray(prices, dtype=float), "ask": np.asarray(prices, dtype=float) + 0.1}, index=index
    )
    ticks = prepared_ticks(lambda: ticks)()
    return ticks, VectorizedXauUsdStrategy(None)._initialize_per_tick_temp_state(ticks)


def open_window(data, row=0, direction=XauDirection.BUY, priority=0, parent="BO1", zone_id="z"):
    window = XauPullbackWindowState(
        parent_breakout_id=parent,
        zone=XauZone(zone_id, 100, 102, priority),
        direction=direction,
        active=True,
        bar_offset=1,
    )
    column = data.columns.get_loc("pullback_windows_opened")
    data.iat[row, column] += (window,)
    return window


def feedback(data, updates):
    data["pullback_feedback"] = pd.Series([()] * len(data), index=data.index, dtype=object)
    for row, events in updates.items():
        data.iat[row, data.columns.get_loc("pullback_feedback")] = events


@pytest.mark.parametrize(
    "direction,prices,edge",
    [
        (XauDirection.BUY, [101.81, 101.8, 102.5], 102),
        (XauDirection.SELL, [100.19, 100.2, 99.5], 100),
    ],
)
def test_penetration_latches_edge_candidates_and_retries(direction, prices, edge):
    ticks, data = state(prices)
    opening = open_window(data, direction=direction)
    original = deepcopy(opening)
    result = generate_pullback_signals(ticks, data)
    assert result.pullback_signals.map(len).tolist() == [0, 1, 1]
    candidates = [value[0] for value in result.pullback_signals.iloc[1:]]
    assert [c.candidate_id for c in candidates] == ["BO1:PB1", "BO1:PB2"]
    for row, candidate in enumerate(candidates, start=1):
        assert candidate.entry_price == edge
        assert candidate.parent_breakout_id == "BO1"
        assert candidate.zone_id == "z"
        assert candidate.family == XauSignalFamily.PULLBACK
        assert candidate.order_type == XauOrderType.PENDING_STOP
        assert candidate.direction == direction
        assert candidate.signal_time == data.index.get_level_values("precise_time")[row]
    assert opening == original
    assert generate_pullback_signals(ticks, result).equals(result)


def test_window_expires_after_fifth_observed_bar_and_trend_flip_does_not_cancel():
    ticks, data = state([101.8] * 6, pd.date_range("2026-09-24", periods=6, freq="15min", tz="UTC"))
    open_window(data)
    data["trend"] = [1, 2, 1, 2, 1, 2]
    result = generate_pullback_signals(ticks, data)
    assert result.pullback_signals.map(len).tolist() == [1, 1, 1, 1, 1, 0]


def test_day_change_clears_windows_and_usage():
    ticks, data = state([101.8] * 3, ["2026-09-24 23:59", "2026-09-25 00:00", "2026-09-25 00:01"])
    open_window(data)
    open_window(data, row=2, parent="BO2")
    feedback(data, {0: (PullbackFeedback("z", XauDirection.BUY, 1, False),)})
    result = generate_pullback_signals(ticks, data)
    assert result.pullback_signals.map(len).tolist() == [0, 0, 1]


@pytest.mark.parametrize("priority,expected", [(0, [1, 0, 0, 0, 0]), (1, [1, 0, 0, 0, 1])])
def test_pending_and_fill_feedback_controls_usage_and_repenetration(priority, expected):
    ticks, data = state([101.8, 101.8, 102.1, 102.1, 101.8])
    open_window(data, priority=priority)
    feedback(
        data,
        {
            1: (PullbackFeedback("z", XauDirection.BUY, 0, True),),
            2: (PullbackFeedback("z", XauDirection.BUY, 1, False, filled=True),),
        },
    )
    result = generate_pullback_signals(ticks, data)
    assert result.pullback_signals.map(len).tolist() == expected


def test_cancelled_pending_can_retry_without_fresh_penetration():
    ticks, data = state([101.8, 102.1, 102.1])
    open_window(data)
    feedback(
        data,
        {
            1: (PullbackFeedback("z", XauDirection.BUY, 0, True),),
            2: (PullbackFeedback("z", XauDirection.BUY, 0, False),),
        },
    )
    result = generate_pullback_signals(ticks, data)
    assert result.pullback_signals.map(len).tolist() == [1, 0, 1]


def test_daily_usage_is_shared_between_directions_but_not_zones():
    ticks, data = state([101.0])
    open_window(data)
    open_window(data, direction=XauDirection.SELL, parent="BO2")
    open_window(data, zone_id="other", parent="BO3")
    feedback(data, {0: (PullbackFeedback("z", XauDirection.BUY, 1, False),)})
    result = generate_pullback_signals(ticks, data)
    assert [c.zone_id for c in result.pullback_signals.iloc[0]] == ["other"]


def test_active_window_retains_parent_and_new_parent_opens_after_expiry():
    ticks, data = state([101.8] * 7, pd.date_range("2026-09-24", periods=7, freq="15min", tz="UTC"))
    open_window(data)
    open_window(data, row=1, parent="ignored")
    open_window(data, row=6, parent="BO3")
    result = generate_pullback_signals(ticks, data)
    assert result.pullback_signals.iloc[1][0].parent_breakout_id == "BO1"
    assert result.pullback_signals.iloc[5] == ()
    assert result.pullback_signals.iloc[6][0].candidate_id == "BO3:PB1"


def test_streams_do_not_share_windows_or_daily_usage():
    first_ticks, first = state([101.8, 101.8])
    second_ticks, second = state([101.8, 101.8])
    second.index = second.index.set_levels(["other"], level="broker")
    second_ticks.index = second.index
    ticks = pd.concat([first_ticks, second_ticks]).iloc[[0, 2, 1, 3]]
    open_window(first)
    open_window(second)
    feedback(first, {0: (PullbackFeedback("z", XauDirection.BUY, 1, False),)})
    feedback(second, {})
    data = pd.concat([first, second]).iloc[[0, 2, 1, 3]]
    result = generate_pullback_signals(ticks, data)
    assert result.pullback_signals.map(len).tolist() == [0, 1, 0, 1]


@pytest.mark.parametrize("prices", [[], [101.8]])
def test_no_windows_returns_empty_tuples(prices):
    result = generate_pullback_signals(*state(prices))
    assert result.pullback_signals.tolist() == [()] * len(prices)


@pytest.mark.parametrize("offset,active", [(0, True), (6, True), (1, False)])
def test_inactive_or_out_of_range_opening_is_ignored(offset, active):
    ticks, data = state([101.8])
    window = open_window(data)
    window.bar_offset, window.active = offset, active
    assert generate_pullback_signals(ticks, data).pullback_signals.iloc[0] == ()


@pytest.mark.parametrize("counts", [[-1], [1, 0]])
def test_invalid_daily_counts_are_rejected(counts):
    ticks, data = state([101.8] * len(counts))
    open_window(data)
    feedback(data, {i: (PullbackFeedback("z", XauDirection.BUY, count, False),) for i, count in enumerate(counts)})
    with pytest.raises(ValueError, match="Invalid pullback daily fill count"):
        generate_pullback_signals(ticks, data)


# def test_missing_input_and_output_columns_are_rejected():
#     ticks, data = state([101.8])
#     with pytest.raises(SchemaErrors):
#         generate_pullback_signals(data.drop(columns="pullback_windows_opened"))
#     with pytest.raises(SchemaErrors):
#         PullbackResult.validate(data, lazy=True)


def test_breakout_openings_feed_pullback_generation():
    ticks, data = state([101, 104, 101.8], ["2026-09-24 00:00", "2026-09-24 00:01", "2026-09-24 00:15"])
    data["trend"] = 1
    data["buy_engaged:z"] = True
    data["sell_engaged:z"] = False
    result = generate_pullback_signals(ticks, generate_breakout_signals(ticks, data, [XauZone("z", 100, 102)]))
    assert result.pullback_signals.map(len).tolist() == [0, 0, 1]
    candidate = result.pullback_signals.iloc[2][0]
    assert candidate.parent_breakout_id == result.breakout_signals.iloc[2][0].candidate_id


@pytest.mark.parametrize("column,value", [("bid", "invalid"), ("pullback_feedback", ("invalid",))])
def test_wrong_input_types_are_rejected(column, value):
    ticks, data = state([101.8])
    target = ticks if column == "bid" else data
    target[column] = pd.Series([value], index=data.index, dtype=object)
    with pytest.raises(SchemaErrors):
        generate_pullback_signals(ticks, data)
