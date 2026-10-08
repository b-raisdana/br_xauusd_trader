# Vectorized Execution Replay TODO

Status: INCOMPLETE; native candidates and windows now reach replay, but production still uses the scalar row driver and is not release-ready.

## Implementation status

| Segment | Status | Evidence / remaining work |
| --- | --- | --- |
| Characterization | PARTIAL | A test-only scalar oracle has 21 lifecycle tests. Integration tests compare each tick’s event/position/modification outputs against the oracle for a fill-modify-close scenario and cover same-tick admission order, duplicate timestamps, independent two-stream continuation across day partitions and continuation across a partition inside one M15 bar. Full lifecycle-wide per-tick differential coverage remains absent. |
| Event schemas | PARTIAL | Replay output tables retain `stream_id` and `stream_tick`; fills, closes, execution events, stop modifications and pullback-cycle state changes retain tick ordinals, and entry rejections are persisted with candidate/code/ordinal. Accepted and rejected stop modifications have dedicated typed rows with previous/requested/resulting stop levels. Cycle state rows are typed, persisted only when values change and keyed by stable cycle ID; explicit cycle-transition reason events remain absent. |
| Native signal/window integration | PARTIAL | Candidate rows join by `stream_tick`, native windows are passed, stream/day state is kept between day runs, and output artifacts retain source stream/tick identity. Feedback does not alter native signal generation, and the active replay implementation still iterates market rows in Python. |
| Batch replay / recurrence | NOT IMPLEMENTED | `VectorizedExecutionReplay` invokes the scalar state machine for every tick. No typed compiled recurrence or batch-equivalent economics contract exists. |
| Artifacts / report | PARTIAL | Orders, fills, closes, execution events, coded entry rejections, stop modifications, changed cycle state and position snapshots are persisted with stream/tick identity. Synthetic manifest tests run Vectorbt from replay events, preserving same-tick fill/close order, stream-isolated positions, execution prices, linear-economics sizing and recorded costs; grouped report metrics print and save for multiple streams. Independent stream adapters also retain positions across partition continuation, and empty-stream results are explicitly verified. Requested real-data CLI/report artifacts remain unavailable; annualized metric parity is unverified. |
| CLI / economics | PARTIAL | CLI/API configuration is wired and JSON uses explicit `LinearReplayEconomics`; the CLI passes replay initial balance to reporting. Native replay now rejects custom callback economics until they implement a batch-equivalent contract, and report projection refuses unknown sizing rather than assuming a unit. The aligned batch economics API and valid production config are still absent. |
| Differential tests / benchmark | NOT IMPLEMENTED | Regressions cover duplicate-timestamp matching, day-partition continuation, out-of-partition candidate rejection, and coded rejection persistence. No batch-vs-oracle comparison or representative benchmark exists. |
| Requested output evidence | BLOCKED | `data/strategy-results/.26-07-29.i3AsXyv.parquet` is absent; available 2026-07-29 artifacts use a different hash. No matching report/trades artifacts or execution config were supplied. |

## Objective

Connect native tick, M15 candle, range/zone, and signal inputs to execution orders, positions, and the existing Vectorbt report by reproducing `ExecutionReplay` behavior. Preserve all current entry, fill, close, pending-order, protection, session, restart, risk, cost, and pullback rules. Do not feed candidate signals directly to `Portfolio.from_signals()` or replace the replay with a simpler trade model.

The priority is pandas/NumPy state reconstruction. Use a compiled scan only for causal recurrence that cannot be represented efficiently and exactly by batched transformations. Production Python must not iterate ticks, rows, or M15 candles. Compiled kernels must use typed numeric arrays, avoid object mode, and return batched event/state arrays.

## Current flow and confirmed gaps

| Concern | Current evidence | Required change |
| --- | --- | --- |
| Native runner | [`runner.py`](../../src/application/xauusd_trading_strategy_1_vector/runner.py) passes optional `ReplayConfig` to [`VectorizedXauUsdStrategy`](../../src/application/xauusd_trading_strategy_1_vector/the_strategy.py), which now accepts it. | Replace the currently reachable Python per-tick state machine with the required batch path. |
| Native outputs | [`process_columns`](../../src/application/xauusd_trading_strategy_1_vector/columnar_process/__main__.py) produces signals and window openings; strategy converts candidates and passes windows to replay. | Apply execution feedback to later pullback eligibility and fills without changing signal rules. Preserve source identity and order through every event/output table. |
| Replay lifecycle | [`replay.py`](../../src/application/xauusd_trading_strategy_1_vector/replay.py) holds the scalar transitions; [`vectorized_replay.py`](../../src/application/xauusd_trading_strategy_1_vector/vectorized_replay.py) currently calls them once per market row. The test oracle reproduces the phase sequence. | Implement pandas/NumPy reconstruction and a narrow typed kernel for proven irreducible recurrences. Remove production row iteration; retain the scalar oracle only in tests. |
| Existing tests | [`test_vectorized_execution.py`](../../tests/test_vectorized_execution.py) has most lifecycle cases commented out. [`test_robust_mt5_parity.py`](../../tests/test_robust_mt5_parity.py) actively covers selected order-close ordering, risk and protection helpers, not a complete tick replay. | Restore or re-author deterministic lifecycle characterization and compare every exposed output at each tick. |
| Position artifacts | Replay assembles and persists order/fill/close/event rows and position snapshots. Position snapshots are not the `PositionTrackingResult` shape consumed by [`backtest.py`](../../src/application/xauusd_trading_strategy_1_vector/backtest.py); a tested event projection now feeds Vectorbt directly from replay fills/closes. | Validate report semantics on representative multi-stream replay artifacts, including time-based metrics and actual configured economics. |
| Backtest entrypoint | [`__main__.py`](../../src/application/xauusd_trading_strategy_1_vector/__main__.py) skips the report when no replay position artifacts exist and otherwise runs the tested fill/close projection; replay initial balance is forwarded. | Verify the complete requested-data CLI/report/trades output when the exact input Parquet and execution config are available. |
| Economics boundary | [`ReplayConfig`](../../src/application/xauusd_trading_strategy_1_vector/domain/replay.py) accepts arbitrary callbacks; JSON config exposes explicit `LinearReplayEconomics`. | Define and validate an aligned batch economics API for profit, margin, cost, sessions and broker acceptance; reject callbacks without batch-equivalent behavior. |

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

### Characterize before replacing — PARTIAL

- Build a test-only scalar oracle that invokes the existing helpers in the phase order above. Its row iteration is test reference code only; it must not be imported by production.
- Reactivate or re-author coverage for market fills at ask/bid, static zone protection, pending stop submit/trigger/expiry, same-tick fill and stop/target, adverse gaps, stop-first ties, opposite breakout close rejection, reversal limits, pullback feedback, failed submit/cancel/close/modify, and duplicate candidate ordering.
- Cover session modes (`carry`, `pullback`, `all`), preclose cutoff boundaries, session rollover, restart-day locks, daily-loss reset, QA-discovery behavior, risk modes (`off`, `net`, `gross`), pending/open risk, margin, max positions, and same-candle order limits.
- Compare output per tick: ordered event/action IDs and reasons, request/order/position statuses, fill/close prices and times, stop/target, feedback, rejection codes, balance, costs, realized/unrealized PnL, risk totals, lock flags and pullback lifecycle state.
- Record exact phase ordering and tie-break behavior, including duplicate timestamps, multiple streams, day partitions, and a partition boundary inside an M15 bar.

### Normalize entities and batch-reconstruct state — NOT IMPLEMENTED

- Introduce typed tables for streams, zones, candidate events, pullback cycles, requests/orders, fills, closes, modifications, rejections and positions. Key rows by stable `stream_id`, `stream_tick`, candidate/order/cycle identity, event ordinal and phase; preserve duplicate market timestamps with tick ordinals.
- Replace object snapshots and nested per-tick tuples on the active native path with primitive columns. Keep UTC nanosecond timestamps, nullable enum/integer dtypes, input order and exact ID-generation rules.
- Normalize zone ordering and precompute zone neighbors, protection candidates, priorities, family eligibility and free-space conditions with grouped shifts, joins and ordered selections. Match current ordering and ties; do not substitute a stable sort unless it is proven equivalent to `ZoneCache` ordering.
- Reconstruct independent or directly observable state in batches: bar/day boundaries, previous quotes, session membership/cutoffs, restart masks, pending trigger/expiry masks, first-touch stop/target candidates, candidate ranks, event phases, pullback penetration latches, bar ages, and closed-candle strict extrema used by `_structure_stop`.
- Use grouped `shift`, cumulative masks, cumulative sums, reductions, joins and interval/event tables to derive active requests/positions and exposure. Avoid a ticks × all-orders Cartesian expansion; use bounded per-stream partitions and event intervals.
- Derive fill/close economics and position snapshots from event tables with grouped calculations. Preserve quote side, spread, gap behavior, commission timing, cost-adjusted risk-free stops, and all decimal price normalization boundaries.
- Reconstruct sequential gates with batch state only where the dependency is associative or can be resolved from grouped prefix/event reductions. Prove exact equivalence for each such transformation before integrating it.

### Isolate the irreducible recurrence — NOT IMPLEMENTED

- After the batch reconstruction attempt, list the remaining dependencies with source method, inputs, state read/write, event phase, and why grouped shifts/prefix reductions cannot express them efficiently.
- The expected candidates are admission after earlier same-tick closes/fills, order acceptance with stateful economics callbacks, overlapping position-risk budgets, pending-risk cancellation priority, daily locks triggered by realized close PnL, and trailing-stop modifications whose acceptance affects later settlement.
- If any remain irreducible, compile the smallest typed scan over precomputed arrays. Keep pandas/NumPy preparation and outputs outside it; no Python per-market-row callbacks, object mode, `np.vectorize`, `DataFrame.apply(axis=1)`, or hidden row iteration.
- Replace arbitrary per-operation `ReplayEconomics` callbacks with a documented batch contract that returns aligned profit, margin, cost, session, and accept/reject arrays. Preserve failure/rejection semantics. If a callback cannot provide batch-equivalent behavior, reject that configuration clearly instead of silently changing the strategy.
- Return complete primitive event/state arrays from the kernel, then reconstruct pandas tables by index and stable event keys. Verify state carry across day/file partitions and separate streams.

### Wire and persist the end-to-end path — PARTIAL

- Pass explicit execution configuration through CLI/API, `main`, `run_vectorized_strategy`, and the strategy runner. Do not manufacture economics defaults; require a real config for execution mode.
- Feed the existing native signal/window candidate outputs into replay while applying replay feedback to later pullback eligibility and fills. Preserve breakout, reversal and pullback event generation; do not edit signal rules to make the report pass.
- Persist normalized order events and positions through `ResultFilesManifest` in the existing `data/strategy-results/` root. Ensure `generate_position_tracking_columns` is called only with actual replay order artifacts, or replace it with an equivalent batch projection.
- Run `print_backtest_report()` only after successful position persistence. Keep `Portfolio.from_signals()` as the downstream report/metric adapter over replay-generated positions; do not pass raw candidate signals as entries/exits.
- Confirm the requested source artifact `data/strategy-results/.26-07-29.i3AsXyv.parquet` and its backtest report/trades artifacts are written, nonempty, and traceable to the same input data/configuration. Do not claim success if the source artifact or required execution config is absent.

## Acceptance criteria

- **NOT MET:** Differential oracle comparison for all characterized cases. Integration tests compare per-tick event, position and modification outputs for one fill/modify/close scenario and cover selected candidate-ordering, duplicate-timestamp and partition-continuity cases, not full lifecycle equivalence.
- **NOT MET:** Production reachability without Python market-row iteration. Replay currently loops over `itertuples()` and calls scalar transition methods.
- **PARTIAL:** Artifacts persist with stream/tick identity, including typed cycle state changes and stop-modification outcomes; synthetic report tests preserve repeated position IDs, isolate accounts by source stream, and print/save grouped metrics. Independent stream adapters retain replay state across day partitions and partitions inside one M15 bar; empty stream results return all eight empty artifact tables. Other complete output schemas remain unestablished.
- **NOT MET:** Complete requested-data CLI-to-Vectorbt report verification. A synthetic manifest proves event-to-trade sizing, costs, same-tick sequencing and fill/close pricing, but requested source/report/trades files are unavailable and time-based metric parity is unverified.
- **NOT MET:** Representative runtime and peak-memory benchmark.
- **PARTIAL:** Focused replay/native/report tests pass, including tick-by-tick scalar comparison for fill/modify/close, persisted cycle snapshots and accepted/rejected stop modifications, empty-stream handling, grouped reports and independent multi-stream continuation across day partitions and partitions inside one M15 bar. The full suite and changed-file pre-commit gate must be rerun after the cycle-artifact changes.

## Remaining verification

- Replace the production row driver with a batch engine and retain the scalar oracle only in tests.
- Define a batch economics contract or reject non-batch callback implementations explicitly.
- Run the CLI only after the exact input Parquet and explicit execution config are available; validate persisted manifest partitions and session-calendar coverage.
- Benchmark against the scalar oracle and record machine/runtime and input/output counts.
- Keep the separate [VectorBT code-reduction plan](vectorbt-code-reduction.md) from replacing execution with direct signal-to-portfolio mapping; that would violate this task’s strategy-preservation requirement.
