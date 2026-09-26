from copy import deepcopy

import numpy as np
import pandas as pd
from scalar_coordinator_reference import (
    begin_coordinator_bar,
    begin_coordinator_day,
    close_coordinator_bar,
    process_coordinator_tick,
)
from vectorized_fixtures import candles_from_ticks, prepared_ticks

from application.xauusd_trading_strategy_1_vector import VectorizedXauUsdStrategy

# from application.xauusd_trading_strategy_1_vector import VectorizedXauUsdStrategy
from domain.xau_usd.enums import XauDirection, XauTrend
from domain.xau_usd.models import XauMarketCoordinator, XauZone


class Zones:
    def __init__(self, zones):
        self.zones = zones

    def get_zones_for_day(self, day):
        return deepcopy(self.zones)


@prepared_ticks
def ticks(times, bids, symbol="XAUUSD"):
    times = pd.DatetimeIndex(pd.to_datetime(times, utc=True, format="mixed"))
    return pd.DataFrame(
        {"bid": np.asarray(bids, dtype=float), "ask": np.asarray(bids, dtype=float) + 0.2},
        index=pd.MultiIndex.from_arrays(
            [["test"] * len(times), [symbol] * len(times), times, times.normalize()],
            names=["broker", "symbol", "precise_time", "date"],
        ),
    )


def run(frame, zones):
    strategy = VectorizedXauUsdStrategy(Zones(zones))
    result = strategy.process_tick_data(frame, candles_from_ticks(frame))
    return result, strategy._per_tick_temp_state


def oracle(frame, zones):
    coordinator = XauMarketCoordinator()
    day = bar = None
    high = low = 0.0
    expected = []
    snapshots = []
    for (_, _, time, _), tick in frame.iterrows():
        candidates = []
        next_day, next_bar = str(time.date()), time.floor("15min")
        if next_day != day:
            assert begin_coordinator_day(coordinator, next_day, deepcopy(zones))
            bar = None
        elif next_bar != bar:
            ok, candidates = close_coordinator_bar(
                coordinator, next_bar.to_pydatetime(), high, low, coordinator.last_bid
            )
            assert ok
        if next_bar != bar:
            ok, _ = begin_coordinator_bar(coordinator, str(next_bar), tick.bid, tick.ask)
            assert ok
            high = low = tick.bid
        high, low = max(high, tick.bid), min(low, tick.bid)
        ok, _ = process_coordinator_tick(coordinator, time.to_pydatetime(), tick.bid, tick.ask)
        assert ok
        expected.append(tuple(candidates))
        snapshots.append((coordinator.breakout_sequence, deepcopy(coordinator.pullbacks)))
        day, bar = next_day, next_bar
    return expected, snapshots


# @pytest.mark.parametrize(
#     "direction,close,expected",
#     [
#         ("buy", 103.0, False),
#         ("buy", 103.001, True),
#         ("sell", 99.0, False),
#         ("sell", 98.999, True),
#     ],
# )
# def test_strict_buffer_and_closed_bar_availability(direction, close, expected):
#     prices = [100, 101, 100, close, 100] if direction == "buy" else [101, 102, 102, close, 102]
#     frame = ticks(
#         ["2026-09-18 00:00", "2026-09-18 00:01", "2026-09-18 00:15", "2026-09-18 00:16", "2026-09-18 00:30"], prices
#     )
#     result, per_tick_state = run(frame, [XauZone("z", 100, 102)])
#     assert all(not values for values in result.breakout_signals.iloc[:-1])
#     assert bool(result.breakout_signals.iloc[-1]) == expected
#     assert per_tick_state.breakout_sequence.iloc[-1] == int(expected)
#     assert result.action.isna().all()
#     if expected:
#         candidate = result.breakout_signals.iloc[-1][0]
#         assert candidate.entry_price == close
#         assert candidate.signal_time == pd.Timestamp("2026-09-18 00:30", tz="UTC")
#         assert candidate.direction == (XauDirection.BUY if direction == "buy" else XauDirection.SELL)
#         window = result.pullback_windows_opened.iloc[-1][0]
#         assert window.parent_breakout_id == candidate.candidate_id == "BO1"
#         assert window.active and window.bar_offset == 1


def test_scalar_parity_for_candidates_sequence_and_window_ownership():
    rng = np.random.default_rng(14)
    times = pd.DatetimeIndex(
        np.concatenate(
            [
                pd.date_range(day, periods=80, freq="min", tz="UTC").to_numpy()
                for day in pd.date_range("2026-09-18", periods=10, freq="D")
            ]
        )
    )
    times = times.delete(np.arange(20, 35))
    times = times.insert(100, times[100])
    frame = ticks(times, 104 + rng.normal(0, 2, len(times)).cumsum())
    zones = [XauZone("a", 100, 102), XauZone("b", 106, 108)]
    expected, snapshots = oracle(frame, zones)
    result, per_tick_state = run(frame, zones)
    assert result.breakout_signals.tolist() == expected
    assert sum(map(len, expected)) > 0
    assert per_tick_state.breakout_sequence.tolist() == [sequence for sequence, _ in snapshots]
    for row, (_, windows) in enumerate(snapshots):
        assert bool(per_tick_state.pullback_active.iloc[row]) == any(window.active for window in windows)
        for window in windows:
            prefix = f"pullback:{window.zone.id}:{window.direction.value}"
            assert per_tick_state[f"{prefix}:parent"].iloc[row] == (window.parent_breakout_id if window.active else "")
            assert per_tick_state[f"{prefix}:offset"].iloc[row] == (window.bar_offset if window.active else 0)


def test_repeated_breakouts_preserve_active_parent_and_reopen_after_expiry():
    times = []
    prices = []
    for bar in range(14):
        start = pd.Timestamp("2026-09-18", tz="UTC") + pd.Timedelta(minutes=15 * bar)
        times.extend([start, start + pd.Timedelta(minutes=1)])
        prices.extend([100, 101 if bar == 0 else 104])
    frame = ticks(times, prices)
    zones = [XauZone("z", 100, 102)]
    expected, snapshots = oracle(frame, zones)
    result, per_tick_state = run(frame, zones)
    assert result.breakout_signals.tolist() == expected
    opened = [window.parent_breakout_id for values in result.pullback_windows_opened for window in values]
    assert opened == ["BO1", "BO7"]
    for row, (_, windows) in enumerate(snapshots):
        expected_parent = next((w.parent_breakout_id for w in windows if w.active), "")
        assert per_tick_state[f"pullback:z:{XauDirection.BUY.value}:parent"].iloc[row] == expected_parent


def test_engagement_is_per_zone_and_multi_zone_gap_does_not_engage_skipped_zone():
    frame = ticks(
        [
            "2026-09-18 00:00",
            "2026-09-18 00:01",
            "2026-09-18 00:15",
            "2026-09-18 00:16",
            "2026-09-18 00:17",
            "2026-09-18 00:30",
        ],
        [95, 96, 95, 101, 110, 110],
    )
    zones = [XauZone("a", 100, 102), XauZone("b", 106, 108)]
    result, per_tick_state = run(frame, zones)
    assert [c.zone_id for c in result.breakout_signals.iloc[-1]] == ["a", "b"]
    skipped = frame.drop(frame.index[3])
    result, per_tick_state = run(skipped, zones)
    assert all(not values for values in result.breakout_signals)
    assert per_tick_state.multi_zone_tick_gap.iloc[3]


def test_unengaged_zone_cannot_borrow_another_zones_engagement():
    frame = ticks(
        ["2026-09-18 00:00", "2026-09-18 00:01", "2026-09-18 00:15", "2026-09-18 00:16", "2026-09-18 00:30"],
        [104, 105, 107, 110, 110],
    )
    result, _ = run(frame, [XauZone("a", 100, 102), XauZone("b", 106, 108)])
    assert [c.zone_id for c in result.breakout_signals.iloc[-1]] == ["b"]


def test_prefix_invariance_and_no_final_bar_or_cross_day_signal():
    frame = ticks(
        [
            "2026-09-18 23:00",
            "2026-09-18 23:01",
            "2026-09-18 23:15",
            "2026-09-18 23:16",
            "2026-09-18 23:30",
            "2026-09-19 00:00",
        ],
        [100, 101, 100, 104, 100, 104],
    )
    zones = [XauZone("z", 100, 102)]
    result, per_tick_state = run(frame, zones)
    for length in range(1, len(frame) + 1):
        prefix_result, prefix_state = run(frame.iloc[:length], zones)
        pd.testing.assert_frame_equal(prefix_result, result.iloc[:length])
        pd.testing.assert_frame_equal(prefix_state, per_tick_state.iloc[:length])
    assert result.breakout_signals.iloc[-1] == ()
    assert per_tick_state.breakout_sequence.iloc[-1] == 0
    assert not per_tick_state.pullback_active.iloc[-1]


def test_empty_no_zones_and_symbol_isolation():
    frame = ticks(
        ["2026-09-18 00:00", "2026-09-18 00:15", "2026-09-18 00:16", "2026-09-18 00:30"], [100, 100, 104, 100]
    )
    zones = [XauZone("z", 100, 102)]
    assert run(frame.iloc[:0], zones)[0].empty
    assert all(not values for values in run(frame, [])[0].breakout_signals)
    other = ticks(frame.index.get_level_values("precise_time"), [100, 100, 104, 100], symbol="OTHER")
    combined = pd.concat([frame, other])
    result, _ = run(combined, zones)
    assert [c.candidate_id for values in result.breakout_signals for c in values] == ["BO1", "BO1"]


def test_gap_uses_observed_new_bar_time_and_advances_window_once():
    frame = ticks(
        ["2026-09-18 00:00", "2026-09-18 00:15", "2026-09-18 00:16", "2026-09-18 01:00", "2026-09-18 02:00"],
        [100, 100, 104, 104, 104],
    )
    result, per_tick_state = run(frame, [XauZone("z", 100, 102)])
    candidate = result.breakout_signals.iloc[3][0]
    assert candidate.signal_time == pd.Timestamp("2026-09-18 01:00", tz="UTC")
    assert candidate.bar_id == str(pd.Timestamp("2026-09-18 00:15", tz="UTC"))
    assert per_tick_state[f"pullback:z:{XauDirection.BUY.value}:offset"].tolist() == [0, 0, 0, 1, 2]


# def test_window_expires_at_sixth_observed_bar_without_new_breakout():
#     frame = ticks(
#         pd.date_range("2026-09-18", periods=9, freq="15min", tz="UTC").insert(
#             2, pd.Timestamp("2026-09-18 00:16", tz="UTC")
#         ),
#         [100, 101, 104, 104, 104, 104, 104, 104, 104, 104],
#     )
#     result, per_tick_state = run(frame, [XauZone("z", 100, 102)])
#     assert sum(map(len, result.breakout_signals)) == 1
#     assert per_tick_state[f"pullback:z:{XauDirection.BUY.value}:offset"].tolist() == [0, 0, 0, 1, 2, 3, 4, 5, 0, 0]
#     assert not per_tick_state.pullback_active.iloc[-1]


# def test_close_time_trend_not_following_tick_trend_controls_candidate():
#     frame = ticks(
#         ["2026-09-18 00:00", "2026-09-18 00:01", "2026-09-18 00:15", "2026-09-18 00:16", "2026-09-18 00:30"],
#         [100, 101, 100, 104, 90],
#     )
#     result, per_tick_state = run(frame, [XauZone("z", 100, 102)])
#     assert result.breakout_signals.iloc[-1][0].direction == XauDirection.BUY
#     assert per_tick_state.trend.iloc[-1] == XauTrend.DOWN.value


def test_breakout_requires_matching_trend_even_when_engaged_and_beyond_buffer():
    frame = ticks(
        ["2026-09-18 00:00", "2026-09-18 00:15", "2026-09-18 00:16", "2026-09-18 00:30"],
        [110, 100, 104, 104],
    )
    result, per_tick_state = run(frame, [XauZone("z", 100, 102)])
    assert per_tick_state["buy_engaged:z"].iloc[2]
    assert per_tick_state.trend.iloc[2] == XauTrend.DOWN.value
    assert all(not values for values in result.breakout_signals)
