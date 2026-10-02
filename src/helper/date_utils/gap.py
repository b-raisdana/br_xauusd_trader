from functools import lru_cache
from typing import Literal

import numpy as np
import pandas as pd

from br_pre_commit import pandera_validate
from config import app_config

from .core import time_range, time_range_to_string
from .timeframe import all_timestamps, get_floor
from .tz_utils import timeframe_to_period


def _clean_df_nans(df: pd.DataFrame, nan_means: Literal["not-cached", "not-available"] = "not-cached") -> pd.DataFrame:
    if nan_means != "not-cached" or df.empty:
        return df
    subset = [c for c in df.columns if c not in ("timeframe", "date")]
    return df.dropna(subset=subset, how="any") if subset else df


def normalize_timeframes(
    timeframes: tuple[str, ...] | list[str] | set[str] | None,
    freqs_to_drop: tuple[str, ...] | None = None,
    all_if_empty: bool = False,
    allowed_timeframes: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    if allowed_timeframes is None:
        allowed_timeframes = app_config.timeframes
    if timeframes is None or len(timeframes) == 0:
        timeframes = allowed_timeframes if all_if_empty else ()
        if not freqs_to_drop:
            return timeframes
    return _normalize_timeframes(tuple(timeframes), freqs_to_drop or (), allowed_timeframes)


@lru_cache
def _normalize_timeframes(
    timeframes: tuple[str, ...],
    freqs_to_drop: tuple[str, ...],
    allowed_timeframes: tuple[str, ...],
) -> tuple[str, ...]:
    invalid_freqs = set(timeframes) - set(allowed_timeframes)

    # if allow_one_second_freq:
    one_second = {"1second", "1s", "1sec"}.intersection({timeframes})
    if one_second:
        timeframes = set(timeframes) - one_second
        timeframes |= {"1s"}
    else:
        timeframes = set(timeframes)

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
