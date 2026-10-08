# Vectorized Execution Replay TODO

Status: READY FOR DETAILED REVIEW; implementation not started.

## Objective

Connect native tick, M15 candle, range/zone, and signal inputs to execution orders, positions, and the existing Vectorbt report by reproducing `ExecutionReplay` behavior. Preserve all current entry, fill, close, pending-order, protection, session, restart, risk, cost, and pullback rules. Do not feed candidate signals directly to `Portfolio.from_signals()` or replace the replay with a simpler trade model.

The priority is pandas/NumPy state reconstruction. Use a compiled scan only for causal recurrence that cannot be represented efficiently and exactly by batched transformations. Production Python must not iterate ticks, rows, or M15 candles. Compiled kernels must use typed numeric arrays, avoid object mode, and return batched event/state arrays.

## Current flow and confirmed gaps

| Concern | Current evidence | Required change |
| --- | --- | --- |
| Native runner | [`runner.py`](../../src/application/xauusd_trading_strategy_1_vector/runner.py) rejects every non-null `ReplayConfig`; [`VectorizedXauUsdStrategy`](../../src/application/xauusd_trading_strategy_1_vector/the_strategy.py) does the same. | Add execution to the active batched path without restoring a Python market-row driver. |
| Native outputs | [`process_columns`](../../src/application/xauusd_trading_strategy_1_vector/columnar_process/__main__.py) persists signal state, candidates, windows and candle state. It does not emit execution events, orders, or positions, and execution feedback cannot affect later candidates. | Join native candidate/window events to a normalized execution state and persist execution artifacts. Preserve candidate identity, source order and feedback effects. |
| Replay lifecycle | [`replay.py`](../../src/application/xauusd_trading_strategy_1_vector/replay.py) contains active scalar transition methods, but its public `step` driver is commented out. [`market.py`](../../src/application/xauusd_trading_strategy_1_vector/market.py) also retains commented legacy tick phases. | Establish an active test-only scalar oracle from the current methods before replacing or removing behavior. No production scalar fallback. |
| Existing tests | [`test_vectorized_execution.py`](../../tests/test_vectorized_execution.py) has most lifecycle cases commented out. [`test_robust_mt5_parity.py`](../../tests/test_robust_mt5_parity.py) actively covers selected order-close ordering, risk and protection helpers, not a complete tick replay. | Restore or re-author deterministic lifecycle characterization and compare every exposed output at each tick. |
| Position artifacts | [`generate_position_tracking_columns`](../../src/infrastructure/result_processing/__main__.py) projects positions from saved order snapshots; it does not generate fills. [`ResultFilesManifest`](../../src/infrastructure/result_processing/io.py) already has `orders` and `positions` artifacts and read/write methods. | Have replay produce normalized orders/fills/closes, then use or replace the projection with a batch projection that preserves its contract. Persist `positions` before calling the existing report. |
| Backtest entrypoint | [`__main__.py`](../../src/application/xauusd_trading_strategy_1_vector/__main__.py) requests the report by default but skips it when the manifest has no positions. [`backtest.py`](../../src/application/xauusd_trading_strategy_1_vector/backtest.py) consumes positions and then calls `Portfolio.from_signals()`. | Keep Vectorbt downstream of replay-generated positions. Remove the skip only when the active runner successfully produces positions; retain a clear failure if execution inputs are missing. |
| Economics boundary | [`ReplayConfig`](../../src/application/xauusd_trading_strategy_1_vector/domain/replay.py) accepts an arbitrary `ReplayEconomics` callback protocol. `LinearReplayEconomics` includes currency multiplier, margin, costs, minimum stop distance and sessions. No production economics configuration is currently wired through the CLI. | Define and validate a batch economics interface, including broker acceptance outcomes. Do not copy synthetic test economics or infer live broker assumptions. |

## Replay phase contract to characterize

The commented `ExecutionReplay.step` body specifies this order; verify it against active helpers and tests before using it as the oracle contract:

1. Validate quotes and reset per-tick event buffers with `_begin_tick`.
2. Apply session windows, preclose cancellation/flattening, and operational locks with `_session`.
3. Roll candle/day state with `_roll`: age pullback cycles on bar change, reset daily zone/risk state on day change, then register new windows.
4. Apply restart cancellation/flattening with `_restart`. A locked tick skips ordinary settlement and candidate processing.
5. Settle previously submitted orders and open positions with `_settle`; process each order in insertion order. A pending stop can fill and then hit protection on the same tick. If stop and target both hit, stop wins because `_settle` checks it first.
6. Process breakout candidates in their emitted order. `_breakout` first closes opposing same-day reversals for the same zone; a rejected close aborts that breakout. It then submits the breakout and attempts to open its pullback cycle.
7. Submit reversal candidates in their emitted order.
8. Update active pullback cycles and submit newly triggered pending-stop requests.
9. Apply profit-protection modifications with `_manage`.
10. Snapshot events, orders, positions, feedback, attempts, rejections, balances, daily locks and operational locks.

Preserve event phase and within-phase order. Other important order-sensitive behavior includes reverse-order session closes and pending-risk cancellation, insertion-order order settlement, one-order-per-candle attempt consumption, rejected broker requests, fill-time risk/cap enforcement, and close-time daily-lock/pending-risk enforcement.

## Work plan

### Characterize before replacing

- Build a test-only scalar oracle that invokes the existing helpers in the phase order above. Its row iteration is test reference code only; it must not be imported by production.
- Reactivate or re-author coverage for market fills at ask/bid, static zone protection, pending stop submit/trigger/expiry, same-tick fill and stop/target, adverse gaps, stop-first ties, opposite breakout close rejection, reversal limits, pullback feedback, failed submit/cancel/close/modify, and duplicate candidate ordering.
- Cover session modes (`carry`, `pullback`, `all`), preclose cutoff boundaries, session rollover, restart-day locks, daily-loss reset, QA-discovery behavior, risk modes (`off`, `net`, `gross`), pending/open risk, margin, max positions, and same-candle order limits.
- Compare output per tick: ordered event/action IDs and reasons, request/order/position statuses, fill/close prices and times, stop/target, feedback, rejection codes, balance, costs, realized/unrealized PnL, risk totals, lock flags and pullback lifecycle state.
- Record exact phase ordering and tie-break behavior, including duplicate timestamps, multiple streams, day partitions, and a partition boundary inside an M15 bar.

### Normalize entities and batch-reconstruct state

- Introduce typed tables for streams, zones, candidate events, pullback cycles, requests/orders, fills, closes, modifications, rejections and positions. Key rows by stable `stream_id`, `stream_tick`, candidate/order/cycle identity, event ordinal and phase; preserve duplicate market timestamps with tick ordinals.
- Replace object snapshots and nested per-tick tuples on the active native path with primitive columns. Keep UTC nanosecond timestamps, nullable enum/integer dtypes, input order and exact ID-generation rules.
- Normalize zone ordering and precompute zone neighbors, protection candidates, priorities, family eligibility and free-space conditions with grouped shifts, joins and ordered selections. Match current ordering and ties; do not substitute a stable sort unless it is proven equivalent to `ZoneCache` ordering.
- Reconstruct independent or directly observable state in batches: bar/day boundaries, previous quotes, session membership/cutoffs, restart masks, pending trigger/expiry masks, first-touch stop/target candidates, candidate ranks, event phases, pullback penetration latches, bar ages, and closed-candle strict extrema used by `_structure_stop`.
- Use grouped `shift`, cumulative masks, cumulative sums, reductions, joins and interval/event tables to derive active requests/positions and exposure. Avoid a ticks × all-orders Cartesian expansion; use bounded per-stream partitions and event intervals.
- Derive fill/close economics and position snapshots from event tables with grouped calculations. Preserve quote side, spread, gap behavior, commission timing, cost-adjusted risk-free stops, and all decimal price normalization boundaries.
- Reconstruct sequential gates with batch state only where the dependency is associative or can be resolved from grouped prefix/event reductions. Prove exact equivalence for each such transformation before integrating it.

### Isolate the irreducible recurrence

- After the batch reconstruction attempt, list the remaining dependencies with source method, inputs, state read/write, event phase, and why grouped shifts/prefix reductions cannot express them efficiently.
- The expected candidates are admission after earlier same-tick closes/fills, order acceptance with stateful economics callbacks, overlapping position-risk budgets, pending-risk cancellation priority, daily locks triggered by realized close PnL, and trailing-stop modifications whose acceptance affects later settlement.
- If any remain irreducible, compile the smallest typed scan over precomputed arrays. Keep pandas/NumPy preparation and outputs outside it; no Python per-market-row callbacks, object mode, `np.vectorize`, `DataFrame.apply(axis=1)`, or hidden row iteration.
- Replace arbitrary per-operation `ReplayEconomics` callbacks with a documented batch contract that returns aligned profit, margin, cost, session, and accept/reject arrays. Preserve failure/rejection semantics. If a callback cannot provide batch-equivalent behavior, reject that configuration clearly instead of silently changing the strategy.
- Return complete primitive event/state arrays from the kernel, then reconstruct pandas tables by index and stable event keys. Verify state carry across day/file partitions and separate streams.

### Wire and persist the end-to-end path

- Pass explicit execution configuration through CLI/API, `main`, `run_vectorized_strategy`, and the strategy runner. Do not manufacture economics defaults; require a real config for execution mode.
- Feed the existing native signal/window candidate outputs into replay while applying replay feedback to later pullback eligibility and fills. Preserve breakout, reversal and pullback event generation; do not edit signal rules to make the report pass.
- Persist normalized order events and positions through `ResultFilesManifest` in the existing `data/strategy-results/` root. Ensure `generate_position_tracking_columns` is called only with actual replay order artifacts, or replace it with an equivalent batch projection.
- Run `print_backtest_report()` only after successful position persistence. Keep `Portfolio.from_signals()` as the downstream report/metric adapter over replay-generated positions; do not pass raw candidate signals as entries/exits.
- Confirm the requested source artifact `data/strategy-results/.26-07-29.i3AsXyv.parquet` and its backtest report/trades artifacts are written, nonempty, and traceable to the same input data/configuration. Do not claim success if the source artifact or required execution config is absent.

## Acceptance criteria

- Differential oracle comparison passes for all characterized cases, with exact categorical/ID/event ordering and explicit floating-point tolerance only where arithmetic order differs; normalized prices and threshold decisions must match exactly.
- Production reachability contains no Python iteration, callbacks, `iterrows`, `itertuples`, row-wise `apply`, or per-tick/per-candle comprehensions. Any compiled recurrence is narrow, typed, documented and exercised against the oracle.
- Every expected manifest day has completed `orders` and `positions` artifacts; schema, UTC ns indexes, duplicate tick identity, empty collections and continuation state are preserved.
- The CLI completes tick → candle/range → signals → replay → positions → Vectorbt report without the current “no position artifacts” skip and writes the requested report and trades files under `data/strategy-results/`.
- Benchmark representative large inputs against the characterized scalar oracle for wall time and peak memory. Record row counts, signal/order/position counts, configuration, data range, machine/runtime, and measured results; make no unsupported general speed or profitability claim.
- Run focused execution, native pipeline, manifest and report regressions, then repository gates appropriate to the implementation milestone. Python oracle equivalence is not MT5 parity evidence.

## Review decisions before implementation

- Confirm the replay phase contract from source/history and restore the test-only oracle while `step` is commented out.
- Decide the batch form for custom economics and broker acceptance; preserve injected test callbacks without using them per market row in production.
- Resolve whether execution state carries across output days exactly as `ColumnarMarket` does and how the configured session calendar covers every tick.
- Confirm the target Parquet file corresponds to the current market inputs and execution config before running it; old signals-only artifacts are not backtest evidence.
- Keep the separate [VectorBT code-reduction plan](vectorbt-code-reduction.md) from replacing execution with direct signal-to-portfolio mapping; that would violate this task’s strategy-preservation requirement.
