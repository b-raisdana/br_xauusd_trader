from datetime import datetime
from functools import lru_cache

import pandas as pd

from config import app_config

from .tz_utils import TZAware, fix_tz


def get_floor(ts: pd.Timestamp, timeframe: str) -> TZAware:
    """The open-time label of the `timeframe` candle that contains `ts`, anchored exactly as
    domain.ohlcv.multi_timeframe.aggregate_multi_timeframe_ohlcv's pd.Grouper bins:

    - "1W"  -> the Monday 00:00 UTC on/before `ts` (open of the week; "W-MON", closed/label "left").
    - else  -> epoch-anchored fixed grid (00:00, 04:00, ... for "4h"; every minute for "1min").

    Exchanges label a candle by its open time, so this is the single anchoring definition the
    gap detector and the fetch-window widener both build on.
    """
    if timeframe == "1W":
        out = ts.normalize() - pd.Timedelta(days=int(ts.weekday()))
        assert isinstance(out, pd.Timestamp)
        return out
    return ts.floor(timeframe_to_pandas_freq(timeframe))


@lru_cache(maxsize=1024 * 1024)
def get_ceil(ts: pd.Timestamp, timeframe: str) -> TZAware:
    return fix_tz(ts.to_period(freq=timeframe_to_pandas_freq(timeframe)).end_time)


def timeframe_to_grouper_freq(timeframe: str) -> str:
    """pandas offset alias for calendar-aligned pd.Grouper / pd.date_range bins, mirroring
    get_floor's anchoring rules. "1W" -> "W-MON" (Monday-start week; closed/label "left"
    is applied at the Grouper call site). Every other configured timeframe is epoch-anchored
    and maps to itself. No "M"/"MS" monthly case: "M" is not in app_config.timeframes
    (Config.py), so the former dead branch is dropped here."""
    return "W-MON" if timeframe == "1W" else timeframe


timeframe_to_pandas_freq = timeframe_to_grouper_freq


def shift_timeframe(timeframe: str, shifter: str | int) -> str:
    index = app_config.timeframes.index(timeframe)
    if type(shifter) is int:
        return app_config.timeframes[index + shifter]
    elif type(shifter) is str:
        if shifter not in app_config.timeframe_shifter:
            raise ValueError(f"Shifter expected be in [{app_config.timeframe_shifter.keys()}]")
        return app_config.timeframes[index + app_config.timeframe_shifter[shifter]]
    else:
        raise TypeError(f"shifter expected be int or str got type({type(shifter)}) in {shifter}")


def trigger_timeframe(timeframe: str) -> str:
    if app_config.timeframes.index(timeframe) < -app_config.timeframe_shifter["trigger"]:
        raise ValueError(f"{timeframe} has not a trigger time!")
    return shift_timeframe(timeframe, app_config.timeframe_shifter["trigger"])


def pattern_timeframe(timeframe: str) -> str:
    if app_config.timeframes.index(timeframe) < -app_config.timeframe_shifter["pattern"]:
        raise ValueError(f"{timeframe} has not a pattern time!")
    return shift_timeframe(timeframe, app_config.timeframe_shifter["pattern"])


def anti_pattern_timeframe(timeframe: str) -> str:
    if (
        app_config.timeframes.index(timeframe)
        > len(app_config.timeframes) + app_config.timeframe_shifter["pattern"] - 1
    ):
        raise ValueError(f"{timeframe} has not an anti-pattern time!")
    return shift_timeframe(timeframe, -app_config.timeframe_shifter["pattern"])


def anti_trigger_timeframe(timeframe: str) -> str:
    if (
        app_config.timeframes.index(timeframe)
        > len(app_config.timeframes) + app_config.timeframe_shifter["trigger"] - 1
    ):
        raise ValueError(f"{timeframe} has not an anti-trigger time!")
    return shift_timeframe(timeframe, -app_config.timeframe_shifter["trigger"])


def all_timestamps(start: datetime, end: datetime, timeframe: str) -> pd.DatetimeIndex:
    """Candle-label timestamps for `timeframe` within [start, end], anchored per
    `candle_open_label` (open-time labels, matching the aggregator's pd.Grouper bins).

    The generator produces exactly these labels for a request, then trims to [start, end];
    this mirrors that so MultiIndex.difference finds only genuinely-missing (timeframe, ts) pairs.

    RETAINED (dead code, superseded 2026-08-30): the full-grid gap path
    (`multi_timeframe_timestamps` -> `all_timestamps` -> `_find_gapped_timeframes_indexes` ->
    `merge_to_ranges`) is replaced by the per-timeframe cached-row scan
    `_per_timeframe_missing_time_ranges` / `_tf_gap_ranges`. Kept, not deleted, per project
    convention -- the anchoring rules here (first label on/before start, epoch grid, W-MON)
    are the reference the new scan re-implements. Still imported by unit tests.
    """
    from .tz_utils import _as_tz_aware

    start_ts, end_ts = _as_tz_aware(start), _as_tz_aware(end)
    grid = pd.date_range(
        start=get_floor(start_ts, timeframe),
        end=end_ts,
        freq=timeframe_to_grouper_freq(timeframe),
        tz="UTC",
    )
    return grid[grid >= start_ts]
