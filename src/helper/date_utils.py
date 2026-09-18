from datetime import datetime, timedelta, timezone, tzinfo
from functools import lru_cache
from typing import Annotated, Literal

import numpy as np
import pandas as pd
import pytz
from br_py_log_n_profile import log_d, log_exception

from config import app_config
from helper.pandera import pandera_validate


def time_range_to_string(
    end: datetime | pd.Timestamp | None = None,
    days: float = 60,
    start: datetime | pd.Timestamp | None = None,
) -> str:
    if end is None:
        end = today_morning() if start is None else start + timedelta(days=days) - timedelta(minutes=1)
    if start is None:
        start = end - timedelta(days=days) + timedelta(minutes=1)
    time_range_str = f"{start.strftime('%y-%m-%d.%H-%M')}T{end.strftime('%y-%m-%d.%H-%M')}"
    if end < start:
        raise RuntimeError(
            f'End:"{end}" of requested_boundary:"{time_range_str}" should be later than it\'s Start:"{start}"'
        )
    return time_range_str


@lru_cache(maxsize=1024)
def time_range(time_range_str: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    try:
        start_string, end_date_string = time_range_str.split("T")
    except ValueError as e:
        log_exception(f"T not found in {time_range_str}. err:{str(e)}", ValueError)

    start = datetime.strptime(start_string, "%y-%m-%d.%H-%M")
    start = start.replace(tzinfo=pytz.utc)
    end = datetime.strptime(end_date_string, "%y-%m-%d.%H-%M")
    end = end.replace(tzinfo=pytz.utc)
    if end < start:
        log_exception(
            f'End:"{end}" of requested_boundary:"{time_range_str}" should be later than it\'s Start:"{start}"',
            RuntimeError,
        )
    return pd.Timestamp(start), pd.Timestamp(end)


@pandera_validate(allow_pandas_dataframe=True)
def time_range_of_data(data: pd.DataFrame) -> str:
    """
    Generate a formatted date range string based on the first and last timestamps in the DataFrame's index.

    This function calculates and returns a formatted string representing the date range of the provided DataFrame.
    The string format is 'yy-mm-dd.HH-MMTyy-mm-dd.HH-MM', where the first timestamp corresponds to the start of the
    date range and the last timestamp corresponds to the end of the date range.

    Parameters:
        data (pd.DataFrame): The DataFrame for which to generate the date range string.

    Returns:
        str: The formatted date range string.

    Example:
        # Assuming you have a DataFrame 'data' with an index containing timestamps
        time_range = range_of_data(data)
        log_d(date_range)  # Output: 'yy-mm-dd.HH-MMTyy-mm-dd.HH-MM'
    """
    return (
        f"{data.index.get_level_values('date').min().strftime('%y-%m-%d.%H-%M')}T"
        f"{data.index.get_level_values('date').max().strftime('%y-%m-%d.%H-%M')}"
    )


EPSILON_TIME = timedelta(seconds=1)


def today_morning(tz: tzinfo = pytz.utc) -> datetime:
    return morning(datetime.now(tz)) - timedelta(minutes=1)


def morning(date_time: datetime, tz: tzinfo = pytz.utc) -> datetime:
    date_time = date_time.replace(tzinfo=tz) if date_time.tzinfo is None else date_time.astimezone(tz)
    return date_time.replace(hour=0, minute=0, second=0)


def yesterday(reference: datetime | None = None) -> str:
    if reference is None:
        reference = datetime.now(timezone.utc)
    start = pd.to_datetime(reference.replace(hour=0, minute=0, second=0, microsecond=0).date() - timedelta(days=1))
    end = start + timedelta(days=1) - EPSILON_TIME
    return time_range_to_string(start=start, end=end)


def _as_tz_aware(value: datetime, convert: bool = False) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if not convert:
        assert ts.tzinfo
        return ts
    log_d("Not tested")
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


TZAware = Annotated[pd.Timestamp, "timezone-aware"]


@lru_cache
def timeframe_to_period(timeframe: str) -> pd.Timedelta:
    """Fixed duration of one `timeframe` candle. All configured timeframes are fixed-length
    (crypto trades 24/7, no DST), so a plain Timedelta is exact -- including "1W" -> 7 days."""
    return pd.Timedelta(days=7) if timeframe == "1W" else pd.Timedelta(timeframe)


@lru_cache(maxsize=1024 * 1024)
def fix_tz(timestamp: pd.Timestamp) -> TZAware:
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp


@lru_cache(maxsize=1024 * 1024)
def get_floor(ts: pd.Timestamp, timeframe: str) -> TZAware:
    """The open-time label of the `timeframe` candle that contains `ts`, anchored exactly as
    domain.ohlcv.multi_timeframe.aggregate_multi_timeframe_ohlcv's pd.Grouper bins:

    - "1W"  -> the Monday 00:00 UTC on/before `ts` (open of the week; "W-MON", closed/label "left").
    - else  -> epoch-anchored fixed grid (00:00, 04:00, ... for "4h"; every minute for "1min").

    Exchanges label a candle by its open time, so this is the single anchoring definition the
    gap detector and the fetch-window widener both build on.
    """
    if timeframe == "1W":
        return ts.normalize() - pd.Timedelta(days=int(ts.weekday()))
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
    start_ts, end_ts = _as_tz_aware(start), _as_tz_aware(end)
    grid = pd.date_range(
        start=get_floor(start_ts, timeframe),
        end=end_ts,
        freq=timeframe_to_grouper_freq(timeframe),
        tz="UTC",
    )
    return grid[grid >= start_ts]


def _union_time_ranges(
    spans: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Merge overlapping / minute-adjacent [start, end] spans into a minimal set, dropping the
    timeframe dimension: _fetch_one_window regenerates every configured freq per gap anyway."""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda span: span[0])
    merged: list[tuple[pd.Timestamp, pd.Timestamp]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + pd.Timedelta(minutes=1):
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def multi_timeframe_timestamps(effective_freqs: list[str], requested_boundary: str) -> pd.MultiIndex:
    """RETAINED (dead code, superseded 2026-08-30 by `_per_timeframe_missing_time_ranges`).
    Materialises the whole expected `(timeframe, timestamp)` label grid -- cost scales with the
    theoretical grid size, not the cached row count. Kept, not deleted, per project convention."""
    start, end = time_range(requested_boundary)

    freq_parts = []
    dt_parts = []
    for frq in normalize_timeframes(effective_freqs):
        timestamps = all_timestamps(start, end, frq)
        freq_parts.append(np.full(len(timestamps), frq, dtype=object))
        dt_parts.append(np.asarray(timestamps))

    return pd.MultiIndex.from_arrays(
        [np.concatenate(freq_parts), np.concatenate(dt_parts)],
        names=["timeframe", "date"],
    )


def _clean_df_nans(df: pd.DataFrame, nan_means: Literal["not-cached", "not-available"] = "not-cached") -> pd.DataFrame:
    if nan_means != "not-cached" or df.empty:
        return df
    subset = [c for c in df.columns if c not in ("timeframe", "date")]
    return df.dropna(subset=subset, how="any") if subset else df


def normalize_timeframes(
    timeframes: tuple[str, ...] | list[str] | set[str] | None,
    freqs_to_drop: tuple[str, ...] = (),
    all_if_empty: bool = False,
    allowed_timeframes: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    if allowed_timeframes is None:
        allowed_timeframes = app_config.timeframes
    if timeframes is None or len(timeframes) == 0:
        timeframes = allowed_timeframes if all_if_empty else ()
        if not freqs_to_drop:
            return timeframes
    return _normalize_freqs(tuple(timeframes), freqs_to_drop, allowed_timeframes)


@lru_cache
def _normalize_freqs(
    timeframes: tuple[str, ...],
    freqs_to_drop: tuple[str, ...],
    allowed_timeframes: tuple[str, ...],
) -> tuple[str, ...]:
    invalid_freqs = set(timeframes) - set(allowed_timeframes)

    # if allow_one_second_freq:
    one_second = {"1second", "1s", "1sec"} - {timeframes}
    timeframes = {timeframes} - {"1second", "1s", "1sec"}
    if one_second:
        timeframes |= {"1s"}
    #     invalid_freqs -= {"1second", "1s", "1sec"}

    if invalid_freqs:
        raise ValueError(f"@duckdb_cache: freqs={timeframes!r} contains unknown timeframes {invalid_freqs!r}")

    return tuple(sorted(timeframes - set(freqs_to_drop), key=timeframe_to_period, reverse=True))


def _first_label_on_or_after(ts: pd.Timestamp, timeframe: str) -> pd.Timestamp:
    """First `timeframe` candle open-label that is >= `ts` -- the anchored lower bound the
    retained `all_timestamps` produced via `grid[grid >= start]` (epoch grid, or Monday for 1W)."""
    floored = get_floor(ts, timeframe)
    return floored if floored == ts else floored + timeframe_to_period(timeframe)


def _tf_gap_ranges(  # type: ignore[explicit-any]  # bare pd.Series, per repo convention
    cached_ts: pd.Series,
    period: pd.Timedelta,
    expected_start: pd.Timestamp,
    expected_end: pd.Timestamp,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Missing candle-label runs for one timeframe, scanning only that timeframe's cached labels.

    `cached_ts` holds the cached open-time labels (any order, tz-aware or naive-UTC). `expected_start`
    / `expected_end` are the anchored first / last labels the request covers. Returns
    `[first_missing_label, last_missing_label]` pairs:

    - empty cache          -> the whole `[expected_start, expected_end]`
    - first cached > start  -> `[expected_start, first_cached - period]`
    - last cached  < end    -> `[last_cached + period, expected_end]`
    - interior              -> `[cur + period, nxt - period]` wherever two consecutive cached
                               labels are more than one `period` apart (vectorised `shift(-1)`)
    """
    if expected_end < expected_start:
        # No `timeframe` candle open-label falls inside the request window (common for a coarse
        # timeframe on a narrow / unaligned request) -- nothing is expected, so nothing is missing.
        return []

    ordered = pd.to_datetime(pd.Series(cached_ts), utc=True).sort_values()
    ordered = ordered[(ordered >= expected_start) & (ordered <= expected_end)].reset_index(drop=True)
    if ordered.empty:
        return [(expected_start, expected_end)]

    ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    if ordered.iloc[0] > expected_start:
        ranges.append((expected_start, ordered.iloc[0] - period))

    next_ts = ordered.shift(-1)
    interior = next_ts > ordered + period  # NaT at the tail compares False -> no spurious run
    gap_starts = (ordered[interior] + period).to_list()
    gap_ends = (next_ts[interior] - period).to_list()
    ranges.extend((cur, nxt) for cur, nxt in zip(gap_starts, gap_ends, strict=True))

    if ordered.iloc[-1] < expected_end:
        ranges.append((ordered.iloc[-1] + period, expected_end))

    return ranges


ONE_NS = pd.Timedelta(nanoseconds=1)


def _per_timeframe_missing_time_ranges(
    fetched_df: pd.DataFrame,
    requested_boundary: str,
    effective_freqs: tuple[str, ...],
    nan_means: Literal["not-cached", "not-available"],
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """Per-timeframe replacement for `_find_gapped_timeframes_indexes` + `merge_to_ranges`: scan
    each configured freq's cached labels with `_tf_gap_ranges` and emit
    `[timeframe, first_missing_label, last_missing_label]` triples (the shape `merge_to_ranges`
    produced). Cost scales with the cached row count, not the theoretical label-grid size.

    Every timeframe is scanned independently. Coarse coverage cannot prove that all finer
    labels are cached, so skipping a finer scan would hide real gaps.

    `_clean_df_nans` (nan_means handling) is applied to `fetched_df` once, before the per-timeframe
    filter, exactly as the retained full-grid path did.
    """
    requested_start, requested_end = time_range(requested_boundary)
    cleaned = _clean_df_nans(fetched_df, nan_means)
    has_indexed_cache = not cleaned.empty and {"timeframe", "date"}.issubset(cleaned.index.names)
    has_flat_cache = not cleaned.empty and {"timeframe", "date"}.issubset(cleaned.columns)
    if has_indexed_cache:
        cached_ts = pd.Series(pd.to_datetime(cleaned.index.get_level_values("date"), utc=True))
        cached_tf = cleaned.index.get_level_values("timeframe").to_numpy()
    elif has_flat_cache:
        cached_ts = pd.Series(pd.to_datetime(cleaned["date"], utc=True))
        cached_tf = cleaned["timeframe"].to_numpy()
    else:
        cached_ts = pd.Series(pd.to_datetime([], utc=True))
        cached_tf = np.empty(0, dtype=object)

    ranges: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    for timeframe in sorted(effective_freqs, key=timeframe_to_period, reverse=True):
        tf_ts = cached_ts[cached_tf == timeframe]
        period = timeframe_to_period(timeframe)
        expected_start = _first_label_on_or_after(requested_start, timeframe)
        expected_end = get_floor(requested_end, timeframe)
        tf_gaps = _tf_gap_ranges(tf_ts, period, expected_start, expected_end)
        ranges.extend((timeframe, gap_start, gap_end) for gap_start, gap_end in tf_gaps)
    return ranges


@pandera_validate(allow_pandas_dataframe=True)
def find_gaped_ranges(
    fetched_df: pd.DataFrame,
    requested_boundary: str,
    effective_freqs: tuple[str, ...],
    nan_means: Literal["not-cached", "not-available"],
) -> list[str]:
    """Precise gap windows for `requested_boundary`: the minimal set of time_range_strs the
    generator must be called with so that every genuinely-missing (timeframe, timestamp) pair
    gets produced. Widening to full-candle coverage is applied per-gap in the fetch loop,
    not here, so the unioned window is widened once after all timeframes are merged.
    """
    effective_freqs = normalize_timeframes(effective_freqs)
    # An empty cache is not special-cased: `_per_timeframe_missing_time_ranges` yields one
    # full-span gap per timeframe, which `_union_time_ranges` collapses back to the request
    # window -- while still dropping coarse timeframes that have no candle label in range.
    per_timeframe_ranges = _per_timeframe_missing_time_ranges(
        fetched_df, requested_boundary, effective_freqs, nan_means
    )
    if not per_timeframe_ranges:
        return []
    combined = _union_time_ranges([(start, end) for _, start, end in per_timeframe_ranges])
    return [time_range_to_string(start=start, end=end) for start, end in combined]


def merge_to_ranges(indexes: pd.MultiIndex) -> list[tuple[object, pd.Timestamp, pd.Timestamp]]:
    """RETAINED (dead code, superseded 2026-08-30 by `_tf_gap_ranges`). Python loop over the
    whole missing-label array to collapse contiguous runs. Kept, not deleted, per project
    convention -- `_tf_gap_ranges` reproduces its `[timeframe, first_label, last_label]` output."""
    if indexes.empty:
        return []
    ranges: list[tuple[object, pd.Timestamp, pd.Timestamp]] = []
    for timeframe, group in indexes.to_frame(index=False).groupby("timeframe"):
        timestamps = group["date"].sort_values().to_numpy()
        step = timeframe_to_period(str(timeframe))
        start = prev = pd.Timestamp(timestamps[0])
        for current in timestamps[1:]:
            current_ts = pd.Timestamp(current)
            if current_ts != prev + step:
                ranges.append((timeframe, start, prev))
                start = current_ts
            prev = current_ts
        ranges.append((timeframe, start, prev))
    return ranges
