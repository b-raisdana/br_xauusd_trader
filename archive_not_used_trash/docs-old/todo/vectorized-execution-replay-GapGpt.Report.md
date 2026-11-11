# Vectorized execution replay — GapGPT audit report

Audit date: 2026-10-08. Scope: [the execution-replay plan](vectorized-execution-replay.md), current implementation, tests, and locally available artifacts.

## Verdict

**The plan is partially implemented and is not complete or demonstrated correct end to end.** Native candidates/windows reach an execution replay, execution artifacts are persisted, and selected synthetic replay-to-Vectorbt cases pass. The main objective—a production path without Python iteration over market rows—is still absent. Several correctness defects remain despite all collected tests passing.

Of the four work-plan packages, **none is fully complete**: characterization and end-to-end wiring are partial; batch state reconstruction and the typed recurrence/economics contract are largely unimplemented. Of the six acceptance criteria, **none is fully met**. A percentage would misrepresent the substantially different sizes of these packages.

This audit examines the working tree, including pre-existing staged and unstaged changes, rather than only commit `d864818`. Implementation files were not changed by this audit. The standard `CURRENT_STATE`, `RULES`, `DECISIONS`, `TODO`, `TEST_STATUS`, and `EXPERIMENTS` documents are absent; README explicitly acknowledges removal of former project-control documents. The requested plan and actual executable behavior therefore supplied the audit evidence.

## Verification performed

| Check | Result | Meaning / limitation |
| --- | --- | --- |
| Focused replay, oracle, report, CLI, tick separation and helper parity tests | **60 passed in 37.55 s** | Proves covered cases only; does not establish full lifecycle or MT5 parity. |
| Full collected repository test suite | **238 passed in 154.72 s** | No failures in the collected suite. Commented tests are not collected. |
| Ruff check of nine relevant implementation/test files | **Passed** | Read-only lint check; no autofix. Not the complete repository pre-commit gate. |
| Independent synthetic report/cash/history/schema probes | **Defects reproduced**, detailed below | These exercise gaps outside the passing suite. |
| Exact requested source artifact | **Absent** | `Test-Path data/strategy-results/.26-07-29.i3AsXyv.parquet` returned false. |
| Real-data CLI/report/trades acceptance, representative benchmark, full pre-commit/MT5 gates | **Not performed / not established** | Exact artifact and a matching explicit execution configuration are unavailable; there is no completed batch engine to benchmark. |

Commands used for tests:

```powershell
python -m pytest -o addopts='' tests/test_oracle_scalar_replay.py tests/test_vectorized_replay_integration.py tests/test_vectorized_tick_separation.py tests/test_backtest_cli_option.py tests/test_backtest_import_isolation.py tests/test_backtest_signals.py tests/test_robust_mt5_parity.py --tb=short -q
python -m pytest -o addopts='' --tb=short -q
```

The lint scope was `vectorized_replay.py`, `replay.py`, `backtest.py`, `the_strategy.py`, `domain/execution_schema.py`, `domain/replay.py`, `__main__.py`, and the oracle/integration test modules. Installed environment: Python 3.14; pandas 3.0.6, NumPy 2.5.3, Vectorbt 1.1.1, Numba 0.67.0, Pandera 0.33.1, pytest 9.1.1, Ruff 0.14.14. Several installed versions differ from `pyproject.toml`; these results establish behavior in this environment, not reproducibility in the declared dependency environment.

## Plan coverage

| Plan package | Implemented and verified | Remaining |
| --- | --- | --- |
| Characterize before replacing | Test-only phase driver calls the existing scalar helpers. Oracle module contains 18 test functions, producing the plan's 21 parameterized cases. Selected quote-side pricing, costs, pending expiry, protection, risk, restart, session flattening, daily reset and broker rejection cases pass. | Complete coverage matrix; accurate same-tick/tie cases; all session/risk modes and failure operations; every per-tick output/state; independent differential comparisons; multi-stream execution and partition-inside-bar coverage. |
| Normalize entities and batch-reconstruct state | Input schemas for streams, zones and candidates; source tick identity; primitive output columns; fill/close/event ordinals; coded rejection persistence. | Batch boundary/session/trigger/expiry/protection/economics/gate reconstruction, proven zone/tie ordering, normalized cycles/modifications/accounts/feedback, matching validated output schemas, explicit phases and complete state history. Existing tables are groundwork, not the required batch state reconstruction. |
| Isolate irreducible recurrence | Existing scalar helpers preserve a causal phase sequence. Explicit linear economics exists for JSON configuration. | Document irreducible dependencies after a batch attempt; typed numeric compiled scan; aligned batch economics/session/acceptance contract; rejection of unsupported callbacks; complete primitive event/state arrays; no production Python market-row callbacks. |
| Wire and persist end-to-end path | CLI/API configuration reaches runner and strategy; native candidates/windows reach replay; cached replay instances retain state between day calls; orders/fills/closes/positions/events/rejections persist through the manifest; initial balance reaches reporting. Synthetic event projection tests preserve selected sizing, costs, quote sides, overlapping positions, stream identity and same-tick fill/close ordering. | Execution-feedback integration with native signal/window generation, report correctness fixes below, real multi-stream/day execution verification, empty-result behavior, exact requested source/report/trades artifacts, and durable input/config provenance. |

Implemented portions with useful passing evidence are the configuration plumbing, ordinal candidate matching with duplicate timestamps, same-tick candidate admission order/rejection persistence, one focused day-continuation replay test, candidate-to-artifact wiring, and selected event-to-trade projections. These are bounded successes, not completion of their enclosing packages.

## Correctness findings

### 1. Production replay still iterates every market row — acceptance blocker

Source: `src/application/xauusd_trading_strategy_1_vector/vectorized_replay.py`, `_run_state_machine`.

The active path contains `for row in streams.itertuples(index=False)` and invokes `_begin_tick`, `_session`, `_roll`, `_restart`, `_settle`, candidate submission, `_pullbacks`, `_manage`, and `_snapshot` in Python for each tick. It also converts candidates/windows/zones into Python objects and collects nested snapshot dictionaries. No batch replacement or typed compiled replay recurrence exists on this path. The class name does not establish vectorized execution.

### 2. Structural trailing protection has no populated candle history — confirmed defect

Source: `replay.py`, constructor, `_roll`, `_structure_stop`; `vectorized_replay.py`, `_run_state_machine`.

`closed_bars` is initialized to an empty list. Its only other active use is reading it in `_structure_stop`; nothing populates it. The adapter supplies bar open/time, not the closed-bar high/low history needed for strict extrema. Consequently the structural stage cannot obtain a stop from real replay history and falls back to the earlier protection stage.

Probe: six ticks in six consecutive M15 bars were passed through the oracle phase driver; `len(replay.closed_bars)` remained **0**. This also exposes a shared-helper limitation: the oracle and production both inherit this defect. Passing their current assertions cannot prove the missing structural behavior correct.

### 3. Vectorbt cash constraints can change replay fills — confirmed defect

Source: `backtest.py`, `_extract_replay_signals`, `run_vectorbt_backtest`.

The adapter converts linear lot volume into `volume × cash_per_price_unit_per_lot`, then feeds that amount at the execution price into a cash-funded `Portfolio.from_signals`, using the replay initial balance. Replay instead admits trades using configured margin per lot. These are different funding models. Vectorbt can partially fill or reject an order already fully filled by replay; there is no order-size/PnL reconciliation to detect this.

Probe using the same adapter funding settings: price **2500**, amount **1**, initial cash **200**, `size_type='amount'`, `cash_sharing=True`. Vectorbt generated entry/exit sizes **0.08 / 0.08**, rather than 1 / 1. Under valid linear replay economics, 0.01 lot with cash multiplier 100 produces amount 1 while margin per lot 100 requires only 1 cash unit. Thus the existing small-price/high-cash synthetic report test does not establish leveraged account parity.

Remaining: make reporting preserve accepted replay quantities, costs, realized PnL and account equity, with explicit margin/funding semantics and reconciliation checks. Merely changing report cash to a large arbitrary balance would not establish account parity.

### 4. Time-based report metrics use synthetic elapsed time — confirmed defect

Source: `backtest.py`, `_extract_replay_signals`, `run_vectorbt_backtest`.

Projection constructs a `RangeIndex`, expands one tick into multiple lifecycle rows, and ultimately supplies NumPy arrays to Vectorbt with default `freq='1min'`. Original market times are not retained in the portfolio index. Every event row therefore becomes another artificial minute, even when events share one timestamp. Tick spacing, duplicate timestamps, session gaps and the number of same-tick events distort elapsed-time statistics.

Annualized return, Sharpe, durations and other frequency-sensitive metrics are not established correct. Real elapsed time must be represented consistently without losing within-tick execution order; acceptance needs irregular-tick and same-time-event checks.

### 5. Multi-stream report printing crashes before output files are saved — confirmed defect

Source: `backtest.py`, `print_backtest_report`.

The report assumes scalar statistics. For multiple stream groups, `portfolio.init_cash` is a Series, and `f'{portfolio.init_cash:,.2f}'` raises **`TypeError: unsupported format string passed to Series.__format__`**. The later final-value conversion and return formatting also assume scalars.

Probe: constructed genuine Vectorbt portfolios with the adapter's array/grouping settings and passed each into the actual print function by temporarily replacing only the portfolio-producing function. One group printed successfully; two groups raised the error above. `save_backtest_report` and `save_backtest_trades` occur later and are not reached. The passing multi-stream test verifies projection, not complete report printing/export.

### 6. Declared execution output schemas do not match actual tables — confirmed defect

Source: `domain/execution_schema.py`, `vectorized_replay.py`, manifest execution writers.

`OrderEvents`, `FillEvents`, `CloseEvents`, `PositionSnapshots` and `ExecutionEvents` are strict schemas, but most omit the stream/tick keys and other fields now emitted by replay. Production output construction and persistence do not apply these schemas. Empty tables are created from column names without the declared dtypes.

Probe: ran a valid one-tick breakout replay and validated its outputs. **OrderEvents, FillEvents, CloseEvents and PositionSnapshots all raised SchemaErrors.** `ExecutionEvents` has the same inspected strict-extra-column mismatch. `RejectionEvents` already includes stream identity, so this finding does not imply every schema is equally stale.

Execution events retain kind/time/reason/ordinal but discard the per-event order snapshot generated by `_event`, including stop/target state. There is no dedicated modification or cycle table, explicit phase, or persisted complete account/risk/lock/feedback state. End-of-tick snapshots cannot reconstruct every within-tick transition.

### 7. Zero-fill execution is not handled as a successful empty report — confirmed control-flow gap

Source: `__main__.py`, `_print_backtest_if_positions`; `the_strategy.py`, `_run_execution_replay`; `backtest.py`, `_extract_replay_signals`.

Execution writes a positions artifact even when its table is empty. The CLI guard checks only for successful positions files, so it invokes reporting. `_extract_replay_signals` then rejects empty fills with `ValueError('Replay backtest requires at least one filled position')`. A valid execution run with no fills therefore has no defined successful report behavior. Tests cover absent position artifacts, not successfully persisted empty positions/fills.

### 8. Partition and stream guarantees are only partially verified

Source: `VectorizedXauUsdStrategy.process_tick_data`, `_execution_replays`, `VectorizedExecutionReplay.run`, integration tests.

State is cached per stream and one direct replay test continues an open position into the next day. This is real implemented continuity, but it is not an actual multi-day manifest/CLI acceptance test. Available multi-symbol native tests use signals-only execution; multi-stream report projection does not prove multi-stream replay isolation.

Tick ordinals are checked for uniqueness/increase within each call, not against previous calls. Repeating a previously processed partition was **accepted** in a probe. That probe did not duplicate the existing entry because the same-candle guard rejected it, but out-of-order/repeated partition processing is not safely validated. Arbitrary file partitions inside one M15 bar, replay restart/resume policy and empty streams still need explicit tests.

## Test coverage limitations

There is no batch-vs-oracle implementation comparison. The test driver imports the same `ExecutionReplay` helpers as production, which is useful for characterization but cannot independently detect shared helper bugs. Complete ordered actions/events, prices/statuses, feedback, attempt state, risk totals, balances/locks and pullback lifecycle are not compared at every tick.

Two oracle test names overstate what their bodies verify:

- `test_oracle_same_tick_fill_and_stop_with_stop_winning` fills a market order on one tick and stops it on the next; it does not trigger and close a pending stop on one tick.
- `test_oracle_same_tick_stop_and_target_with_stop_first` moves toward the target and later below the stop; it does not construct a simultaneous stop/target hit.

The report's same-tick fill/close tests use synthetic fill/close artifacts. They verify report event ordering, not production generation of that lifecycle. The existing commented lifecycle tests in `test_vectorized_execution.py` remain uncollected.

Further characterization is needed for all session modes/cutoff boundaries and rollover; failed submit/cancel/close/modify paths; net/gross/off risk combinations; fill-time risk/cap enforcement; pending cancellation priority; reversal limits; structural trailing history; nanosecond identity/price-normalization boundaries; and exact partition/stream behavior.

## Acceptance assessment

| Acceptance criterion | Audit result |
| --- | --- |
| Differential oracle comparison for all characterized cases | **Not met**: characterization is partial; no replacement-engine differential suite. |
| Production reachability without Python market-row iteration | **Not met**: active scalar tick loop. |
| Artifacts preserve identity and work across streams/partitions/empty streams | **Partial**: identity and selected continuation/projection cases pass; output schemas, full state, empty cases and actual multi-stream replay remain incomplete. |
| Complete requested-data CLI-to-Vectorbt verification | **Not met**: missing exact input/config evidence and confirmed reporting defects. |
| Representative runtime and peak-memory benchmark | **Not met**: no replay benchmark. Test durations are not a benchmark. Report projection also allocates dense timeline-by-position arrays; peak memory needs measurement. |
| Focused tests plus full project/repository gates | **Partial**: focused and full collected tests now pass; scoped Ruff passes. Complete pre-commit/build/platform gates and acceptance regressions remain unestablished. |

The plan's statement that the full project tests had not been rerun after report changes is superseded by this audit's **238-pass** run. This improves verification evidence; it does not close the newly reproduced gaps.

## Remaining work in recommended order

1. **Finish characterization and add regressions for the findings above.** Establish real pending-fill/protection same-tick and tie fixtures; complete session/risk/rejection/structural-history cases; specify every observable per-tick field and ordering rule.
2. **Repair report parity and failure paths.** Reconcile actual replay/Vectorbt quantities and PnL under low-cash leveraged examples, retain correct elapsed-time semantics, support per-stream printing/export and zero-fill runs, and assert that report orders equal replay events.
3. **Align and enforce normalized tables.** Include stable identity, phase/ordinal, consistent UTC/dtypes, cycles, modifications, feedback and account/risk/lock state. Populate closed candle history without look-ahead. Validate persisted populated and empty tables against the same schemas.
4. **Implement batch reconstruction, then the smallest necessary typed recurrence.** Document each unresolved dependency; remove production market-row Python iteration; define aligned batch economics/session/acceptance behavior and reject incompatible callbacks clearly.
5. **Integrate execution feedback and partition behavior.** Preserve native signal rules while applying accepted/failed fills and lifecycle feedback; prove day/file/inside-bar continuity and independent stream state; define repeated/out-of-order partition handling.
6. **Complete real-data acceptance and provenance.** Supply/identify the exact requested input and matching economics/session configuration; run the real CLI through report/trades export; verify nonempty required files, shared provenance and numerical reconciliation. Available 2026-07-29 artifacts are ticks/candles/signals/windows/state with different names/hashes and do not substitute for the requested artifact.
7. **Benchmark and complete final gates.** Compare batch replay with the retained scalar oracle on representative input counts; record runtime, warmup, machine, peak memory, event counts and equality. Run the final relevant repository/platform gates after implementation.

No strategy fixes, model changes, commits or remote operations were performed for this audit. Findings and prioritized remaining work are the deliverable.

## Recheck started — 2026-10-08

The repository has changed since the original audit (HEAD `3155a5b`). The current plan describes eight replay artifact tables, grouped reports and expanded differential coverage, but the checked-in active adapter still returns six tables, its fill schema omits event ordinals/Vectorbt size, and its report projection returns five matrices without execution sizing/costs. Those plan claims are ahead of the executable code. The previous audit evidence is historical and must not be treated as validation of this checkout. Implementation and new acceptance evidence are being recorded below as work progresses. The exact requested source artifact/config remain unresolved; no substitute hash will be relabeled as that input.
