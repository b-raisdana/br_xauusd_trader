from copy import deepcopy

import numpy as np
import pandas as pd
from vectorized_fixtures import calculate_manifest, candles_from_ticks, prepared_ticks, with_native_bootstrap

from application.xauusd_trading_strategy_1_vector import VectorizedXauUsdStrategy

# from application.xauusd_trading_strategy_1_vector import VectorizedXauUsdStrategy
from domain.xau_usd.enums import XauDirection, XauSignalFamily, XauTrend
from domain.xau_usd.models import XauPullbackWindowState, XauSignalCandidate, XauZone


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
            [[symbol] * len(times), ["test"] * len(times), times.normalize(), times],
            names=["symbol", "broker", "date", "precise_time"],
        ),
    )


def run(frame, zones):
    strategy = VectorizedXauUsdStrategy(Zones(zones))
    result, _ = calculate_manifest(strategy, frame, candles_from_ticks(frame), legacy_objects=True)
    return result, result


def oracle(frame, zones):
    candles = with_native_bootstrap(candles_from_ticks(frame))
    candle_times = candles.index.get_level_values("bar_time")
    day = bar = None
    previous = None
    trend = XauTrend.NONE
    sequence = 0
    engaged = [[False, False] for _ in zones]
    windows, expected, snapshots = [], [], []
    for time, (_, tick) in zip(frame.index.get_level_values("precise_time"), frame.iterrows(), strict=True):
        candidates = []
        next_day, next_bar = str(time.date()), tick.bar_time
        history = candles.loc[candle_times < next_bar].tail(3)
        if next_bar != bar:
            for w in windows:
                if w.active:
                    w.bar_offset += 1
                    w.active = w.bar_offset <= 5
            if bar is not None:
                close = history.close.iloc[-1]
                for i, zone in enumerate(zones):
                    buy = engaged[i][0] and trend == XauTrend.UP and close > zone.high + 1
                    sell = engaged[i][1] and trend == XauTrend.DOWN and close < zone.low - 1
                    if not (buy or sell):
                        continue
                    sequence += 1
                    direction = XauDirection.BUY if buy else XauDirection.SELL
                    c = XauSignalCandidate(
                        candidate_id=f"BO#{sequence:02d}",
                        bar_id=str(bar),
                        zone_id=zone.id,
                        family=XauSignalFamily.BREAKOUT,
                        direction=direction,
                        signal_time=time,
                        entry_price=close,
                    )
                    candidates.append(c)
                    neighbor = i + (1 if buy else -1)
                    space = (
                        (zones[neighbor].low - zone.high if buy else zone.low - zones[neighbor].high)
                        if 0 <= neighbor < len(zones)
                        else float("inf")
                    )
                    if space >= 12 and not any(
                        w.active and w.zone.id == zone.id and w.direction == direction for w in windows
                    ):
                        windows.append(
                            XauPullbackWindowState(
                                c.candidate_id,
                                deepcopy(zone),
                                direction,
                                bar_offset=1,
                                active=True,
                                breakout_bar_time=bar,
                                broker_day=day,
                            )
                        )
            if next_day != day:
                sequence = 0
                for w in windows:
                    w.active = False
            opening = candles.loc[candle_times == next_bar].open.iloc[0]
            engaged = [[z.low <= opening <= z.high] * 2 for z in zones]
        if previous is None:
            previous = tick.bid
        if tick.bid > history.high.max():
            trend = XauTrend.UP
        elif tick.bid < history.low.min():
            trend = XauTrend.DOWN
        crosses = [(previous < z.low <= tick.bid, previous > z.high >= tick.bid) for z in zones]
        multi = sum(a or b for a, b in crosses) >= 2
        for i, (up, down) in enumerate(crosses):
            if multi:
                if zones[i].low <= tick.bid <= zones[i].high:
                    engaged[i] = [True, True]
            else:
                engaged[i][0] |= up
                engaged[i][1] |= down
        expected.append(tuple(candidates))
        snapshots.append((sequence, deepcopy(windows)))
        previous, day, bar = tick.bid, next_day, next_bar
    return expected, snapshots


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
        for window in [w for w in windows if w.active]:
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
    assert opened == ["BO#01", "BO#06", "BO#11"]
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
    assert [c.candidate_id for values in result.breakout_signals for c in values] == ["BO#01", "BO#01"]


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


def test_breakout_requires_matching_trend_even_when_engaged_and_beyond_buffer():
    frame = ticks(
        ["2026-09-18 00:00", "2026-09-18 00:15", "2026-09-18 00:16", "2026-09-18 00:30"],
        [110, 100, 104, 104],
    )
    result, per_tick_state = run(frame, [XauZone("z", 100, 102)])
    assert per_tick_state["buy_engaged:z"].iloc[2]
    assert per_tick_state.trend.iloc[2] == XauTrend.DOWN.value
    assert all(not values for values in result.breakout_signals)
