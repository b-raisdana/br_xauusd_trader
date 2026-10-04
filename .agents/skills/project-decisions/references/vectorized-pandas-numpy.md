# Vectorized pandas / NumPy policy

Trigger: writing or reviewing Python data processing, including strategy,
replay, indicators, labels, OHLCV, persistence and reporting. Use pandas
DataFrames first and NumPy ndarrays second throughout the project.

## Red flags to eliminate

- `for i in range(len(df))`, `df.iterrows()`, `df.apply(..., axis=1)`.
- `while remained > 0: ... .append(...)` sample-generation loops that recompute
  one slice at a time. Prefer precomputing all boundaries at once
  (`np.random.randint(size=n)`) and slicing in one vectorized pass.
- Repeated `np.array(df[cols])` conversion inside a hot loop. Convert once,
  slice after.
- Growing a list of DataFrames/arrays and calling `pd.concat`/`np.array` at the
  end when boundaries could have been precomputed.
- Scalar-by-scalar column assignment in a loop over columns.

## Preferred patterns

Boolean masking (`df.loc[mask, col] = value`); `np.where(cond, a, b)` and
`np.select([...], [...], default=c)`; broadcasting across the whole array or
DataFrame; `.groupby(...).transform(...)` and `.rolling(...).agg(...)`; batch
`.loc`/`pd.IndexSlice` or
`numpy.lib.stride_tricks.sliding_window_view` for windowed extraction at many
offsets; `.to_numpy()` (not bare `.values`) for hot-path ndarray drops.

## Hard prohibition

No Python per-tick or per-candle iteration, including closed/previous-candle
history scans. Stateful dependencies and MT5 parity do not permit a Python outer
loop. This includes `for`/`while`, `iterrows`, `itertuples`, row
comprehensions, `zip`/`enumerate` over market rows, row-wise `apply`, and `map`
with a Python callback over tick or candle values. `np.vectorize`, generators and
moving the loop into a helper do not vectorize it.

## Operation priority

Choose the first applicable operation; compose where required.

1. `groupby` + `transform` / `agg`.
2. `shift` / `diff` / `pct_change`.
3. `rolling` / `expanding` / `ewm`.
4. `resample`.
5. `cumsum` / `cumprod` / `cummin` / `cummax`.
6. `rank` / `nunique` / `value_counts`.
7. `where` / `mask` / `clip`.
8. `eval` / `query`.
9. `merge` / `join` / `concat` for vectorized DataFrame combination.
10. `sort_values` / `sort_index`.
11. `diff` / `shift` boolean conditions + `cumsum` for regime/segment detection.
12. NumPy ndarray operations for calculations naturally expressed at array
    level; convert once with `to_numpy()` and preserve index/dtypes at the
    DataFrame boundary.
13. Numba only when pandas/NumPy cannot efficiently express the required
    computation; isolate a typed ndarray kernel, compile its sequential
    recurrence, and verify output/order/state equivalence. No Python object-mode
    or interpreted fallback for market-row processing.
14. Python iteration as a last resort **only over non-tick/non-candle units**,
    such as files, daily I/O partitions, independent instruments or fixed
    configuration fields. Each partition's calculation remains batched. Never
    use this fallback to process market rows, even in replay or validation tools.

## Recurrence

First derive grouped segments, latches and cumulative reductions. If they cannot
express the dependency efficiently, use the compiled ndarray fallback and
document why the higher-priority operations fail.

Preserve causal closed-candle windows, chronological callback order, cross-day
state, duplicate-tick identity and stream isolation. Do not approximate state
transitions, and do not claim native parity from Python-only fixtures.

## Review checklist

- Any row/element/sample loop replaceable by a mask, `np.where`/`np.select`,
  `groupby`/`rolling`, or a fully vectorized index computation?
- Any repeated array conversion of the same columns to hoist out of a loop?
- Any column-by-column loop collapsible to one vectorized expression over the
  selected columns?
- Does the vectorized version's shape/dtype match what downstream code expects
  (upcasting, index alignment) before replacing the loop?

## Known open gap

`the_strategy.py:process_native_stream` currently uses `zip`/`enumerate`/
`itertuples` over market rows and candle-derived lists. This is recorded
**technical debt against a confirmed rule**, not an exception to it. It is
tracked in [docs/todo/vectorized-operation-improment.plan.md](../../../../docs/todo/vectorized-operation-improment.plan.md)
and must not be treated as compliant until an ordered, state-equivalent
pandas/NumPy or compiled-kernel implementation lands with regression evidence.