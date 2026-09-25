import pandas as pd
import pytest
from pandera.errors import SchemaErrors

from application.xauusd_trading_strategy_1_vector.signals import generate_reversal_signals
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily, XauTrend
from domain.xau_usd.models import XauZone


def frame(prices, trend=XauTrend.UP):
    times = pd.date_range("2026-09-24", periods=len(prices), freq="s", tz="UTC").as_unit("ns")
    return pd.DataFrame(
        {
            "bid": pd.Series(prices, dtype=float).to_numpy(),
            "bar_time": times.floor("15min"),
            "trend": int(trend),
            "multi_zone_tick_gap": False,
        },
        index=times.rename("datetime"),
    )


@pytest.mark.parametrize(
    "prices,trend,direction",
    [
        ([99, 100, 99, 101], XauTrend.UP, XauDirection.SELL),
        ([103, 102, 103, 101], XauTrend.DOWN, XauDirection.BUY),
    ],
)
def test_reversal_emits_first_touch_with_tick_metadata(prices, trend, direction):
    data = frame(prices, trend)
    result = generate_reversal_signals(data, [XauZone("z", 100, 102)])
    assert result.reversal_signals.map(len).tolist() == [0, 1, 0, 0]
    candidate = result.reversal_signals.iloc[1][0]
    assert candidate.candidate_id == f"{data.bar_time.iloc[1]}:R:z:{direction.value}"
    assert candidate.direction == direction
    assert candidate.family == XauSignalFamily.REVERSAL
    assert candidate.order_type == XauOrderType.MARKET
    assert candidate.signal_time == data.index[1].to_pydatetime()
    assert candidate.entry_price == prices[1]
    assert candidate.zone_id == "z"
    assert generate_reversal_signals(result, [XauZone("z", 100, 102)]).equals(result)


@pytest.mark.parametrize(
    "prices,trend",
    [
        ([100, 101], XauTrend.UP),
        ([99, 100], XauTrend.NONE),
        ([99, 100], XauTrend.DOWN),
        ([float("nan"), 100], XauTrend.UP),
    ],
)
def test_reversal_requires_directional_touch(prices, trend):
    result = generate_reversal_signals(frame(prices, trend), [XauZone("z", 100, 102)])
    assert result.reversal_signals.tolist() == [(), ()]


def test_gap_does_not_consume_duplicate_key_and_new_bar_resets_detection():
    data = frame([99, 100, 99, 100, 99, 100, 99, 100])
    data.iloc[1, data.columns.get_loc("multi_zone_tick_gap")] = True
    data.iloc[5:, data.columns.get_loc("bar_time")] += pd.Timedelta(minutes=15)
    result = generate_reversal_signals(data, [XauZone("z", 100, 102)])
    assert result.reversal_signals.map(len).tolist() == [0, 0, 0, 1, 0, 0, 0, 1]


def test_multiple_zones_and_directions_are_independent():
    data = frame([99, 100, 103, 102])
    data.iloc[3, data.columns.get_loc("trend")] = XauTrend.DOWN.value
    result = generate_reversal_signals(data, [XauZone("a", 100, 102), XauZone("b", 100, 102)])
    assert result.reversal_signals.map(len).tolist() == [0, 2, 0, 2]
    assert [c.zone_id for c in result.reversal_signals.iloc[1]] == ["a", "b"]


@pytest.mark.parametrize("prices,zones", [([], []), ([], [XauZone("z", 100, 102)]), ([99, 100], [])])
def test_empty_outputs_are_tuples(prices, zones):
    result = generate_reversal_signals(frame(prices), zones)
    assert result.reversal_signals.tolist() == [()] * len(prices)


def test_reversal_rejects_missing_input():
    with pytest.raises(SchemaErrors):
        generate_reversal_signals(frame([99, 100]).drop(columns="trend"), [])
