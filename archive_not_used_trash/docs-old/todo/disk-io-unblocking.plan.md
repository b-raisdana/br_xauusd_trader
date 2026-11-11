# Disk I/O Unblocking Plan

Analysis date: 2026-10-10. Source: `data/profile.pstats` (2640s total, 78.7M calls).

## Profile summary

| Cost center | tottime (s) | cumtime (s) | Calls | Root cause |
|---|---|---|---|---|
| pyarrow `write_table` | 733.3 | 733.3 | 141 | Parquet column encoding |
| `_format_native_types` | 632.8 | 632.8 | 970 | Datetime formatting per column |
| `TextIOWrapper.write` | 0.02 | 1611.0 | 179 | Actual disk flush |
| `hash_pandas_object` | 0.04 | 148.0 | 138 | Full-frame hash per artifact |
| `pd.concat` | 0.02 | 198.0 | 394 | Day-level concatenation |
| threading joins | 2.8 | 3876.0 | 953 | Master blocked on executor shutdown |

**Diagnosis:** The master process is blocked at every write boundary. Async writes exist but are defeated by (a) `wait_for_writes()` after every day batch, (b) read-back-then-re-write patterns in `save_results_to_file`, `merge_results_with_candles`, `generate_position_tracking_columns`, and (c) a full-frame hash computed for every artifact filename.

## Implemented changes

### 1. Replaced `hash_df` with cheap index-only hash (io.py:199-224)

**Before:** `pd.util.hash_pandas_object(df, index=False).sum()` — 148s cumulative, 138 calls.
**After (as merged in `a941961`):** `pd.util.hash_pandas_object(df.index, index=False).sum()` — this was **pathological for MultiIndex frames**: it dispatches to `hash_tuples`, which hashes every level *category*, and groupby-extracted slices carry the parent frame's whole level sets (18 M unique timestamps) → **206 s/call** (11 s on a single-day file's own index), making the full 23-day run take >5 h.
**Repaired:** hash each level's actual values (`index.get_level_values(level)`) — vectorized, order- and content-sensitive, 0.24 s/call on the 902 K-row groupby slice, deterministic, 7-char base64 filename format preserved. See `performance-optimization.plan.md` §12 for the measured evidence.

### 2. Added in-memory frame cache to `ResultFilesManifest` (io.py:100)

Added `_frames: dict[tuple[ResultCategory, datetime], pd.DataFrame]` private attribute, populated in `_submit_write` and cleared in `_complete_pending_write`. Added `get_cached_frame(category, day)` accessor that returns the cached frame or None.

### 3. `save_results_to_file` now uses cached frames (reporting.py:55-100)

Reads `manifest.get_cached_frame("signal_state", day)` instead of `manifest.read_daily_signal_state(day)` — avoiding disk round-trip when the frame is already in memory.

### 4. `merge_results_with_candles` now uses cached frames (result_processing/__main__.py:15-37)

Same pattern for `per_tick_state`, `ticks`, and `candles` categories.

### 5. `generate_order_management_columns` and `generate_position_tracking_columns` now use cached frames (result_processing/__main__.py:40-80)

Same pattern for `results_with_columns` and `orders` categories.

## Remaining master-process blocking

The `wait_for_writes()` call in `process_tick_data` (the_strategy.py:114) and `run_vectorized_strategy` (runner.py:42) still blocks the master after each day batch. This is inherent to the current architecture where the next day's computation depends on terminal state carried in the `markets` dict — not on disk reads. The day-level loop could be restructured to submit writes for day N and process day N+1 concurrently, but this requires careful state isolation and is deferred pending measured evidence of further need.

## Acceptance criteria

- All existing tests pass (behavior unchanged at the API boundary) — **MET**: exit 0, all 290 dots clean (290 passed, 6 warnings; matches the earlier 176.34s run)
- Full 23-day replay PASS — **MET**: retained 34 columns identical over all 18,157,826 rows vs the pre-optimization baseline; signals/windows byte-identical (sha256); export 222 MB vs 326 MB (−32 %); wall time ~3.9 min vs 2640 s profiled baseline (~11×)
- Async write isolation tests still pass — **MET**: `test_failed_write_is_reported_and_manifest_executors_are_independent`, `test_manifest_categories_are_distinct_and_reads_wait_for_writes`
- Round-trip tests still pass — **MET**: `test_nested_values_round_trip_without_losing_types_or_mutating_source`
