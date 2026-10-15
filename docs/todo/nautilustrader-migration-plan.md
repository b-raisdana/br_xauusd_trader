# NautilusTrader Migration Plan

## Objective and guardrails

Plan a full migration from the existing Python/VectorBT workflow to NautilusTrader while preserving the current system's behavior wherever it is valid. Compare functional results and runtime before selecting a production path. This document is planning only; implementation starts only after Project Leader approval of the plan.

- Treat current source behavior, confirmed project rules and reproducible VectorBT/replay outputs as the baseline. Do not assume either implementation is correct solely because it is current or because it is NautilusTrader.
- Match inputs, ordering, timestamps, strategy rules, execution assumptions, costs and configuration before comparing outputs.
- Correct a baseline behavior only when a reproducible defect is identified and its intended behavior is supported by confirmed rules or independently verified evidence. Document the defect, evidence, correction and effect on comparisons; do not silently fold a strategy change into the migration.
- Keep the existing path runnable as a comparison oracle until all gates pass. Do not remove VectorBT or switch defaults before explicit migration acceptance.
- This plan makes no profitability, native MT5 parity, or live-readiness claim. Live execution remains outside scope and requires its own approval.

## Current baseline to characterize

The active entrypoint in `src/application/xauusd_trading_strategy_1_vector/` is pandas-native and signals-only: `run_vectorized_strategy` builds `ZoneCache`, `VectorizedXauUsdStrategy.process_tick_data` groups broker/symbol streams and daily partitions, then `process_native_stream` delegates to `process_columns`. It emits source, tick/candle state, signal and window artifacts. State continues across daily partitions; duplicate timestamps retain `stream_tick` identity. The native runner rejects execution configuration and does not create orders or positions.

`ExecutionReplay` and `VectorizedExecutionReplay` are separate execution APIs; the latter currently calls scalar transitions for each market row. Its output covers replay-generated orders, fills, closes, events, rejections, modifications, cycle state and position snapshots. It is not currently connected to the default native run. The CLI requests the VectorBT report by default, but reporting requires persisted position artifacts, so the default signals-only run skips it. The report adapter consumes replay fills/closes and prices/costs rather than treating raw candidates as trades. The exact current requirements and partial replay status are in [execution replay](vectorized-execution-replay.md), [entrypoint flow](vectorized-entrypoint-flow.md), and the strategy README.

The repo has two distinct cache concerns to preserve and compare: source/derived-data persistence and the DuckDB/Iceberg `@duckdb_cache` data-generation flow, plus run-scoped `ResultFilesManifest` artifacts; and the trading engine's in-memory cache of market, order, position and account state. NautilusTrader's cache/catalog do not automatically replace the first concern or establish equivalence with the existing persistence contract.

Before coding, freeze a reproducible baseline bundle: code revision; Python/dependency lock and VectorBT version; exact source artifact hashes and row counts; broker, symbol, timezone/calendar, date range and stream partitioning; strategy/EA inputs; zone and candle inputs; execution/economics config when testing positions; cache state; command and environment; machine/OS; and output manifest. Include both signals-only runs and explicit execution runs where matching inputs/configuration are available. Missing position data/configuration is a documented baseline gap, not permission to synthesize trades.

## Target architecture and scope

Use NautilusTrader's backtest engine, typed market data, strategy callbacks, simulated venue, execution events, portfolio/account state, cache and reports where they reproduce the defined behavior. Keep strategy-domain calculations and zone logic independently testable; do not force all existing pandas-derived state into engine callbacks if that changes ordering or makes correct comparison impossible. Define an adapter boundary for the current input tables and manifest, and an output adapter that preserves stable source identity and can write the repo's required artifacts.

The migration covers the complete workflow:

| Stage | Inputs/outputs to preserve and compare |
| --- | --- |
| Acquisition and normalization | Tick quotes, source M15 candles, timestamps/timezones, broker calendar, instrument metadata/precision, zones and provenance; nulls, duplicates, sorting, day/stream partition behavior. |
| Derived market state | Candle alignment/bootstrap, trend/reference state, zone ordering/merging/cache lookup, per-tick and per-candle state, cross-partition carry and duplicate-time identity. |
| Signals | Candidate family, side, timestamp/tick ordinal, zone/window/cycle identity, ordering, eligibility/reason and all signal-state columns. |
| Orders and positions | Requests, order lifecycle, fill/reject/cancel/modify events, position lifecycle/snapshots, simultaneous events, stable identifiers, risk/session/restart/pullback behavior. |
| Economics | Fill/exit prices and quote side, spread, fees/commission, slippage, sizing, initial balance, margin, realized/unrealized PnL, equity/balance, drawdown, daily limits and all derived metrics. |
| Persistence/cache | Input and derived data caches, cache hit/miss/gap behavior, invalidation and refresh, catalog conversion, run manifest and artifact schemas, deterministic replay and provenance. |
| Reporting | Orders/fills/closes/positions/account/equity and trade-level/aggregate metrics; missing/empty data behavior and report serialization. |

For each stage, create a field-and-event mapping from current schemas to NautilusTrader types and back. Identify fields with no native equivalent and carry them through explicit custom data or sidecar artifacts; never drop them silently. Record unit/precision, timezone, nullability, enum mapping, identifier scope and event-order rules.

## Work plan and gates

| Outcome | Work and required evidence | Completion gate |
| --- | --- | --- |
| A. Baseline and contract | Inventory actual entrypoints, schemas, state reads/writes, caches, artifacts, configs, and existing tests. Produce representative frozen datasets and runs; list unavailable configs/artifacts. Characterize both signal and replay paths separately. | Baseline bundle is reproducible; all compared inputs/configs have hashes and known provenance; uncovered behavior is explicit. |
| B. Semantic mapping and feasibility | Select NautilusTrader API level and instrument/venue/account/data representations for this FX/CFD-style XAUUSD feed. Map input conversion, M15 and tick sequencing, quote side, zone custom data, strategy state, orders, fills, costs, risk, account and reports. Prototype only the smallest representative slice after plan approval. | Every baseline behavior has a mapped mechanism, an explicit unsupported/uncertain item, or a documented proposal. Confirm package/runtime compatibility on the target OS and Python before broad work. |
| C. Input and state parity | Convert the same frozen ticks, candles and zones; compare normalized source rows, derived state and cache results at exact stream/tick keys. Test duplicate timestamps, missing/empty days, timezone/day boundaries, bootstrap history, chunking and cache cold/warm paths. | Exact equality for discrete keys/enums/events and schema; numeric equality at defined precision. Any mismatch is explained and classified before advancing. |
| D. Signal parity | Compare candidate event tables and every public state output by `(broker, symbol, stream_tick, event_ordinal)` including ordering, family, side, zone/cycle/window references and reasons. | No unexplained differences; each known baseline defect has a separate approved correction record and its own expected-difference test. |
| E. Execution/economics parity | Using identical explicit replay configuration and data, compare requests, fills, closes, modifications, rejections, positions, balance/equity, risk and PnL event-by-event. Align engine phase ordering, same-tick command settlement, quote-side triggers, pending orders, stop/target collisions, session cutoffs, fees and precision. | Lifecycle event sequence and discrete outcomes match; numeric differences are within predeclared rounding tolerance and reconciled. If engine semantics prevent a match, document adapter/model needed or request a Leader decision before changing strategy behavior. |
| F. Cache and persistence parity | Compare source cache and derived cache keys, time ranges, hit/miss/gap fill, invalidation, regeneration, partition append, restart/reuse, schemas and content. Compare NautilusTrader catalog and engine cache separately; preserve `ResultFilesManifest` compatibility or define a reviewed replacement mapping. | Cold and warm runs produce identical logical data/artifacts; no stale, missing or duplicate rows; run provenance identifies code, inputs, configs and engine version. |
| G. Runtime/memory benchmark | Benchmark VectorBT report path and NautilusTrader path on the same machine and frozen workloads at small, representative and largest feasible data sizes. Time acquisition/read, normalization/conversion, derived state/signals, engine execution, artifact writes, report generation and total wall time separately. Record rows/events per second, peak RSS, output size, cache state, CPU, versions and repetitions. Separate first-run/JIT/import costs from steady state; alternate order and repeat runs. | Publish raw measurements and summary (median and spread), with warm/cold cache results and scaling. A faster engine-only segment does not count as a faster end-to-end workflow. No performance winner declared without reproducible runs. |
| H. Shadow comparison and cutover proposal | Run both paths on frozen historical slices and then a longer disjoint period; produce automated first-difference artifacts and a migration report. Preserve the VectorBT path and rollback route. | All gates A-G pass or have explicitly accepted residuals; no unexplained critical mismatch; runtime and operational tradeoffs are quantified. Submit cutover/removal proposal for approval. |

## Comparison and acceptance protocol

- Pair outputs only when input hashes, source revision, symbol/broker, calendar/timezone, strategy inputs, execution config, initial capital, cost model, data range and event-ordering contract match. Otherwise label the comparison unpaired and do not call it parity.
- Normalize only representation differences that are semantically lossless: IDs via a documented mapping, UTC timestamps at the source precision, decimals/units to canonical forms and column ordering. Do not normalize away event order, missing rows, changed signal/position outcomes, price-side differences or accounting differences.
- Use exact comparison for row counts, keys, booleans, enums, event types, order/position lifecycle and signal identity. Use exact decimal comparison where both sides preserve the same tick/lot precision; otherwise declare field-specific tolerance before results are viewed and report max/mean absolute error and mismatch count.
- Generate first-difference records with stage, identity key, field, VectorBT value, NautilusTrader value and source provenance. Summaries must include matched/unmatched counts, event counts by type, trade count, exposure, ending balance/equity, realized/unrealized PnL, costs, drawdown and metric differences.
- Keep functional parity and runtime as separate decisions. Report preprocessing/conversion overhead and cache/storage overhead, not only NautilusTrader engine runtime. Benchmark from identical persisted inputs and also end-to-end from source acquisition where feasible.
- Treat current report metrics as secondary until trade/event parity is established. Differences in metric libraries, annualization or empty-sample handling need an explicit metric definition comparison.

## Risks and decisions to resolve during the approved work

- NautilusTrader models venues, instruments, order execution and accounting explicitly. The repo's current execution API has custom lifecycle/risk/session rules and may not map one-to-one to default engine behavior; custom fill, fee, margin or execution models may be required.
- NautilusTrader backtests process data through engine phases and settle venue commands at defined points. Compare this with the current replay's phase order and same-tick transitions before selecting callback behavior.
- Existing tick/candle/zone artifacts may need custom data conversion; conversion, sorting and catalog writes can dominate runtime and memory even if the engine is faster.
- The repo's DuckDB/Iceberg cache and NautilusTrader `ParquetDataCatalog`/engine cache serve different roles. Any storage replacement must be based on measured behavior, schema/provenance needs, invalidation semantics and operational cost, not naming similarity.
- Price/quantity precision, instrument contract specifications, account currency, XAUUSD point value, leverage/margin and broker session rules must come from the same verified source on both paths. Unspecified values block execution parity claims.
- NautilusTrader documentation describes current APIs; pin the selected release and verify API details against that release before implementation. Official references: [Backtesting](https://nautilustrader.io/docs/latest/concepts/backtesting/), [execution flow](https://nautilustrader.io/docs/latest/concepts/backtesting/execution-flow/), [data catalog](https://nautilustrader.io/docs/latest/concepts/data/catalog/), [cache](https://nautilustrader.io/docs/latest/concepts/cache/), [fill models](https://nautilustrader.io/docs/latest/concepts/backtesting/fill-models/), and [reports](https://nautilustrader.io/docs/latest/concepts/reports/).

## Status

**PLAN ONLY - awaiting Project Leader confirmation.** No migration implementation, dependency change, benchmark run, or cutover is authorized by this document. On approval, begin with Outcome A and continue through the gates; update this plan with evidence and status without weakening the comparison criteria.
