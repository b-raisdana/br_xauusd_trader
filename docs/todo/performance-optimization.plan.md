# Performance Optimization Plan — Vectorized XAUUSD Strategy Replay

Profile: `data/profile.pstats` (generated 2026-10-10 08:37 UTC)
Entry point: `src/application/xauusd_trading_strategy_1_vector/__main__.py:74` (`cli`)

## 1. Executive summary

- **Total runtime: 2640.2 s** (44 min), 78,673,065 calls, 10,108 profiled functions.
- **The strategy is I/O-bound, not compute-bound.** The strategy's own numpy/pandas
  compute (`process_columns` tottime 2.4 s, `_windows` 3.0 s, `_breakouts` 0.6 s) is
  **< 1 %** of runtime.
- **~58 % of runtime is spent in the persistence + type-conversion layer:**
  - Parquet write path: **~906 s (34 %)** — `pyarrow.parquet.core.write_table` 733 s +
    `pyarrow.pandas_compat.convert_column` 201 s.
  - Datetime→string formatting: **632 s (24 %)** — `pandas.core.arrays.datetimes._format_native_types`.
  - Filename content-hashing: **~148 s (5.6 %)** — `pd.util.hash_pandas_object`.
  - Final `pd.concat` in `save_results_to_file`: **196 s (7.4 %)**.
- **Two P0 fixes recover the majority of the runtime** (see §6):
  1. Defer two full-length `bar_time.astype("str")` conversions to the selected event rows
     only → eliminates ~632 s (24 %).
  2. Stop persisting per-tick per-zone engagement/pullback columns (305 of 328 columns in
     the final export are day-specific, mostly-NaN audit columns) → cuts the final parquet
     write ~3× → recovers ~400–490 s.
- **Realistic target: 2640 s → ~1000–1200 s (> 2× speedup)** with P0 items alone, before
  compression/parallelism tuning.

## 2. Profiling methodology (read before acting)

- Ranked by `tottime` (internal time, no double-counting) and `cumtime`; caller/callee graph
  built directly from the raw `pstats.Stats.stats` dict.
- **Caveat — cProfile caller edges through `@pandera_validate`/`@profile_it` wrappers are
  unreliable.** The profile attributes ~305 s of `astype` to
  `pandera/typing/common.py:225(is_generic_model)`, which is a pure `@property` that never
  calls `astype`. This is a wrapper-frame mis-attribution artifact.
- **Ground truth obtained by monkeypatching** `pandas.core.arrays.datetimes.DatetimeArray.astype`
  to log `(nrows, real-caller-stack)` and running the actual `run_vectorized_strategy` +
  `save_results_to_file` on one real day (`ticks.26-07-29`, 902,975 ticks, 12 zones).
  Empirical micro-benchmarks used the project's own `pandas 3.0.5` build
  (`C:\Code\venv-shared-pandas`).
- Confirmed dead code (absent from profile): the legacy per-tick path
  (`the_strategy._process_tick_operations`, `signals.generate_*`, `engagement.update_zone_engagement`,
  `trend.update_trend`). Only the columnar path (`columnar_process.process_columns`) runs.

## 3. Hotspot ranking (by `tottime`)

| # | Function | tottime | % | ncalls | Subsystem |
|---|----------|---------|-----|--------|-----------|
| 1 | `pyarrow/parquet/core.py:1191 write_table` | 733.3 s | 27.8 % | 141 | Parquet write |
| 2 | `pandas/core/arrays/datetimes.py:769 _format_native_types` | 632.8 s | 23.9 % | 970 | Datetime→string |
| 3 | `pyarrow/pandas_compat.py:629 convert_column` | 201.2 s | 7.6 % | 5,161 | Parquet write |
| 4 | `pandas/core/algorithms.py:590 factorize_array` | 94.3 s | 3.6 % | 4,568 | Hashing / groupby |
| 5 | `numpy.ndarray.astype` | 49.5 s | 1.9 % | 92,394 | Type conversion |
| 6 | `pandas/core/dtypes/concat.py:52 concat_compat` | 40.1 s | 1.5 % | 891 | Concat |
| 7 | `pyarrow/compute.py:256 wrapper` | 37.0 s | 1.4 % | 7,417 | Arrow compute |
| 8 | `pandas/core/util/hashing.py:299 _hash_ndarray` | 35.4 s | 1.3 % | 5,208 | Hashing |
| 9 | `pyarrow ... ArrowExtensionArray._values_for_factorize` | 32.9 s | 1.2 % | 1,003 | Hashing |
| 10 | `pyarrow/compute.py:467 take` | 30.0 s | 1.1 % | 20,041 | Arrow compute |
| 11 | `pandas/core/algorithms.py:459 unique_with_mask` | 28.7 s | 1.1 % | 3,766 | Hashing / unique |
| 12 | `numpy.isclose` | 26.9 s | 1.0 % | 2,676 | Numeric |
| 13 | `pandera/decorators.py:949 _wrapper` | 25.2 s | 1.0 % | 697 | Validation |

Top 13 ≈ 1,990 s ≈ **75 % of runtime**, all in I/O / type-conversion / hashing.

## 4. Subsystem budget

| Subsystem | Time | % | Key evidence |
|-----------|------|-----|--------------|
| Parquet write I/O | ~906 s | 34 % | `to_parquet` cumtime 906 s (141 calls); `write_table` 733 s; `convert_column` 201 s |
| Datetime→string | 632 s | 24 % | `_format_native_types` 632 s; 2 full-length `.astype("str")` per stream (instrumented) |
| Final `pd.concat` | 196 s | 7.4 % | `reporting.save_results_to_file` → `concat` 196 s (3 calls) |
| Filename hashing | ~148 s | 5.6 % | `hash_pandas_object` 148 s (138 calls) via `io.hash_df` |
| Parquet reads | ~200 s | 7.6 % | `table_to_dataframe` 73 s; `read_daily_signal_state` 78 s; `read_daily_ticks` 48 s |
| Pandera validation | ~25 s+ | ~1 %+ | `_wrapper` tottime 25 s (validation of large frames on top) |
| Strategy compute | < 26 s | < 1 % | `process_columns`/`_windows`/`_breakouts` tottime |

## 5. Data volume (calibration)

- Final export `strategy_results.parquet`: **18,157,826 rows × 328 columns** (SNAPPY,
  325,959,365 bytes). **305 of 328 columns are per-zone engagement/pullback columns.**
- Per-day artifacts (one broker_symbol): ticks 902,975 × 9; candles 2,100 × 7;
  signal_state 902,975 × **93** (12 zones → 24 engagement + 48 pullback + 21 core).
- The 328-column final frame is the **union of day-specific per-zone columns across ~20 days**
  (zone IDs differ per day), so most per-zone cells are NaN.
- ~23 `process_columns` calls (day × broker_symbol); ~902,975 ticks each.

## 6. Findings

### F1 — Datetime→string: two full-length `bar_time.astype("str")` per stream (632 s, 24 %) [P0]

`_format_native_types` (632 s) is triggered by `DatetimeArray.astype` → string dtype
(`datetimelike.py:487-493`). Empirically, `Series.astype("str")` on a 2 M-row tz-aware
datetime column takes **5.4–7.0 s** and routes through
`blocks.py:578(Block.astype) → astype_array → datetimes.astype → _format_native_types`
(confirmed with the project's pandas 3.0.5).

Instrumented ground truth (one day, 902,975 ticks) — **only 3 source sites**, and two of
them are full-length:

| Site | Rows/day | Calls/day | Notes |
|------|----------|-----------|-------|
| `columnar_process/__main__.py:126` `bar_ids = data.bar_time.astype("str")` | 902,975 | 1 | **full-length** |
| `columnar_process/windows.py:102` `bar_ids = data.bar_time.astype("str")` | 902,975 | 1 | **full-length** |
| `columnar_process/breakouts.py:37` `bars.bar_time...astype("str")` | 25 | 16 | tiny (eligible events) |
| `zone_cache.py:31` / `output_dump.py:185` | 529 / 18 | 23 / 2 | negligible |

The two full-length conversions are **99.97 %** of all converted rows (1,805,950 of
1,806,522 rows/day). **`bar_ids` is passed to `_signal_rows`, which only ever uses
`value.loc[mask]`** (the selected event rows — hundreds, not 902,975). Converting the entire
tick-length column is wasted work.

`save_results_to_file` performs **zero** datetime→string conversions (instrumented), so the
final export path is clean.

### F2 — Parquet write: 328-column wide frame + per-day round-trip (~906 s, 34 %) [P0]

- `write_table` (733 s) is dominated by the **final 325 MB export** (`save_results_to_file`
  → 3 `to_parquet` calls = 612 s), plus 138 daily writes (~121 s).
- The final frame is 18 M × 328 columns; **305 columns are per-tick per-zone
  engagement/pullback audit columns** that are day-specific and mostly NaN in the union.
- `save_results_to_file` does a **save→read→concat→re-write round trip**: it reads all daily
  `signal_state`/`ticks` parquet (`read_daily_*`), concatenates them (196 s), and writes one
  large parquet. The data already existed in memory during the run.
- `convert_column` (201 s) is pyarrow converting each pandas column to an Arrow array —
  proportional to column count × rows, so the 328-column width directly inflates it.

### F3 — Filename content-hashing (148 s, 5.6 %) [P1]

`io.hash_df` (`io.py:196`) computes `pd.util.hash_pandas_object(df, index=False).sum()` on
**every save** (138 calls) to build a unique filename. This hashes every cell of every frame,
including the wide 93-column signal_state. The hash is used only for a filename suffix.

### F4 — Pandera validation overhead [P2]

`@pandera_validate` (`br_pre_commit/src/br_pandera/__main__.py:321`) wraps hot functions with
`pa.check_types(lazy=True, inplace=True)`. `_wrapper` tottime is 25 s; validation of large
frames adds more. `br_pandera_config.environment == "production"` already short-circuits to
`return func` (`__main__.py:315-316`) — ensure the performance run uses production mode.

### F5 — Write executor serialization [P2]

`ResultFilesManifest._submit_write` (`io.py:137`) calls `_complete_pending_write` (blocking
`Future.result()`) for the **same category** before submitting the next write, so writes within
a category are fully serialized. Only 4 `ThreadPoolExecutor` workers exist. The main thread
blocks on `.result()` instead of submitting ahead.

### F6 — Redundant full-length string ops in `_windows` per-zone loop [P2]

`windows.py:148` does `matched.parent_breakout_id.where(active_mask, "").astype("str")` on a
~902 K-row Series, 24×/day (12 zones × 2 directions). `parent_breakout_id` is already `str`,
so the `.astype("str")` is redundant; the `.where` on full-length rows is also avoidable.
Shows up as `string_arrow.astype` (cheap, but not free at 902 K × 24 × 23).

### F7 — Minor: freq inference (22 s) [P3]

`pandas/tseries/frequencies.py deltas_asi8`/`deltas` (11.7 s + 10.5 s, 132 calls) from
DatetimeIndex operations. Small; address only if P0–P2 are exhausted.

## 7. Optimization plan (prioritized)

### P0-1 — Defer datetime→string conversion to selected event rows (F1)

**Target:** `columnar_process/__main__.py:126` and `columnar_process/windows.py:102`.
**Change:** do not materialize `bar_ids = data.bar_time.astype("str")` at full length.
Pass `data.bar_time` (datetime) into `_signal_rows` and convert only the masked rows, e.g.
compute `bar_id` as `data.bar_time.loc[mask].astype("str")` inside/after masking
(`_signal_rows` already selects via `value.loc[mask]` at `helpers.py:46`). Reuse one
conversion per stream where both `process_columns` and `_windows` need it.
**Impact:** eliminates ~632 s (24 %). **Effort:** small. **Risk:** low — output `bar_id`
strings are identical; verify with the state-contract tests and a parquet sha256 comparison.

### P0-2 — Stop persisting per-tick per-zone audit columns in the final export (F2)

**Target:** `reporting.save_results_to_file` + `io._submit_write`.
**Change:** the final `NativeStrategyResult` should contain only the primitive schema columns
(~102: ticks + core `SignalTickState`), not the 305 day-specific per-zone
`buy_engaged:{id}` / `pullback:{id}:{dir}:{parent,offset}` columns. Either
(a) select `SignalTickState.to_schema().columns` (plus ticks) before the final concat/write, or
(b) persist per-zone per-tick state as a separate compact per-day artifact if an audit trail is
required. The per-zone columns are still computed in-memory for signal logic; only the
persistence changes.
**Impact:** final write 328 → ~102 columns (~3× smaller); final parquet write ~600 s → ~200 s;
daily `signal_state` write 93 → ~21 columns (~4×). **Recovers ~400–490 s.** **Effort:** medium.
**Risk:** medium — **must verify no downstream consumer** (backtest `print_backtest_report`,
`print_strategy_summary`, provenance, replay) reads the per-zone columns before dropping;
if audit is required, use option (b).

### P0-3 — Stream the final parquet write instead of read→concat→rewrite (F2)

**Target:** `reporting.save_results_to_file`.
**Change:** accumulate the per-day result frames in memory during the run (they are already
built) and write the final parquet once via `pyarrow.parquet.ParquetWriter`, appending one
row group per day — avoiding the 196 s `pd.concat` of all days and the redundant daily
parquet read-back. Alternatively, write the final file incrementally per day.
**Impact:** removes ~196 s concat + reduces peak RAM (no 18 M × 328 materialization).
**Effort:** medium. **Risk:** low-medium (row-group/schema consistency).

### P1-1 — Replace per-save content hash with a cheap deterministic ID (F3)

**Target:** `io.hash_df` (`io.py:196`).
**Change:** build the filename suffix from a lightweight fingerprint — e.g.
`hash((day, category, len(df), df.index[0], df.index[-1]))` or a monotonic per-run sequence —
instead of `pd.util.hash_pandas_object(df)` over every cell.
**Impact:** ~148 s → ~0. **Effort:** small. **Risk:** low (filename uniqueness only; keep a
collision-safe tuple).

### P1-2 — Write parquet via pyarrow directly with tuned compression (F2)

**Target:** `io._write_columnar`, `infrastructure.result_processing.parquet.write_parquet`,
`reporting.save_results_to_file`.
**Change:** use `pa.Table.from_pandas(df, schema=...)` + `pq.write_table` with an explicit
schema (avoids the 201 s `convert_column` inference), and benchmark `compression` ∈
{`snappy`, `zstd`, `none`} and `row_group_size` for the wide frame. For intermediate daily
files that are read back exactly once, `compression="none"` may be faster end-to-end.
**Impact:** variable (10–40 % of the write path). **Effort:** medium. **Risk:** low (verify
byte-for-byte readability).

### P2-1 — Enable production mode for the perf run; sample-validate hot frames (F4)

**Target:** `br_pandera_config.environment`.
**Change:** run with `environment="production"` (already supported) to skip runtime
`check_types` on hot per-stream functions; keep full validation in CI/unit tests.
**Impact:** ~25 s+ plus validation-of-large-frames overhead. **Effort:** trivial. **Risk:**
low (validation moves to tests).

### P2-2 — Decouple write submission from completion (F5)

**Target:** `io._submit_write` / `_complete_pending_write`.
**Change:** submit all writes first, then `wait_for_writes()` once; raise
`ThreadPoolExecutor(max_workers)`; avoid blocking `Future.result()` inside `_submit_write`.
**Impact:** better write/compute overlap; reduces wall-clock tail. **Effort:** small.
**Risk:** medium (ordering/consistency of pending writes).

### P2-3 — Drop redundant `.astype("str")` / full-length `.where` in `_windows` loop (F6)

**Target:** `columnar_process/windows.py:148`.
**Change:** remove the redundant `.astype("str")` on the already-string `parent_breakout_id`;
compute the latch parent only for `active_mask` rows.
**Impact:** small (string ops, not the 632 s datetime path). **Effort:** trivial. **Risk:** low.

## 8. Expected cumulative impact

| Change | Savings | Cumulative |
|--------|---------|------------|
| P0-1 defer datetime→string | ~632 s | ~2008 s |
| P0-2 drop per-zone persist | ~400–490 s | ~1520–1608 s |
| P0-3 stream final write | ~196 s + RAM | ~1324–1412 s |
| P1-1 cheap hash | ~148 s | ~1176–1264 s |
| P1-2 pyarrow direct + tuning | ~100–250 s | ~930–1164 s |
| P2 items | ~50–100 s | ~830–1114 s |

**Target: ~1000–1200 s (≈ 2–2.6× faster), dominated by P0.** P0-1 and P0-2 alone roughly
halve the runtime.

## 9. Verification plan

1. **Correctness gate (must pass before/after every change):**
   - `python -m pytest` (project test suite; state-contract and schema tests).
   - Re-run the strategy on the same input and compare the final `strategy_results.parquet`
     **sha256** (P0-1 must be byte-identical; P0-2 changes the column set, so compare the
     retained primitive columns and the separate `_signals`/`_windows` artifacts).
2. **Measurement:** re-profile with `python -m cProfile -o data/profile.pstats -m
   application.xauusd_trading_strategy_1_vector ...` on the same input; confirm
   `_format_native_types` tottime drops from 632 s to ~0 and `write_table` drops with the
   narrower frame.
3. **Regression:** ensure `print_strategy_summary`, `print_backtest_report`, and provenance
   still pass after P0-2 (the per-zone column removal).

## 10. Non-goals / out of scope

- Strategy logic correctness, signal semantics, and risk rules are unchanged.
- No change to MT5 data ingestion (`get_ticks`/`get_ohlcv` were ~11 s, negligible).
- No live-trading implications; this is offline replay/export performance only.
- `legacy_reference/` and the dead legacy per-tick path are not touched.

## 11. Suggested execution order

1. P0-1 (largest, lowest-risk, byte-identical) → verify sha256 + tests.
2. P1-1 (small, independent) → verify.
3. P0-2 (verify downstream consumers first) → verify retained-column sha256 + tests.
4. P0-3, P1-2, P2-1, P2-2, P2-3 → verify.
5. Re-profile and update this plan with measured deltas.
