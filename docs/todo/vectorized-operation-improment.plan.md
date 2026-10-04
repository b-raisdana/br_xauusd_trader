# Native columnar signals migration

## Active contract

The Project Leader narrowed the contract on 2026-10-04 to pandas-native, signals-only processing with columnar outputs. Execution replay, economics callbacks, order/position projections and per-tick nested JSON are outside this entrypoint. `ExecutionReplay` and recorded replay remain separate APIs; their presence does not provide native MT5 parity evidence.

- **DONE:** `VectorizedXauUsdStrategy.process_native_stream` returns `ColumnarResult(ticks, candles, signals, windows)`; all four frames have runtime Pandera contracts. Tick state contains primitive columns; signals/windows are separate event tables with original stream indexes and a stable `stream_tick` ordinal to distinguish duplicate timestamps.
- **DONE:** No Python tick/candle iteration, `iterrows`, `itertuples`, row-wise `apply`, Python `map` callback, `np.vectorize`, scalar `MarketState.step` call, compiled kernel or ndarray conversion remains in the native algorithm. Fixed zone/direction/schema loops and logarithmic passes over complete event Series are allowed; each pass processes every event through native operations.
- **DONE:** Closed native M15 high/low slots use `shift(3/2/1)`; references reduce those columns. The current candle is excluded. Native adjacency, missing bars, startup with three closed candles, first-observed candle order and UTC nanosecond indexes are preserved.
- **DONE:** `shift`, grouped `cummax`/`cumsum`, masked forward fills and joins implement trend persistence, previous-bid crossings, multi-zone suppression, per-bar engagement initialization and first reversal per zone/direction/bar.
- **DONE:** Breakouts read the previous observed bar's terminal trend/engagement and the last native closed candle's close before day reset. Daily sequence numbering and zone order are preserved, including an outgoing-day breakout at the first new-day tick.
- **DONE:** Pullback admission uses a forward `merge_asof` successor table and batched binary lifting to select the earliest admissible candidate and its successors at least `window_bars` observed boundaries apart. Both depth calculation and root reachability take logarithmic whole-table passes; there is no candle driver. Existing active windows seed admission. Age, expiry, penetration latches, repeated pullback signals, opening-tick snapshots and creation-order signal priority match the scalar reference.
- **DONE:** `ColumnarMarket` carries terminal primitive references, trend, previous bid, daily sequence, fixed zone state and only active window rows across partitions. Opening events remain in persisted tables; inactive window history and JSON traces do not accumulate in continuation memory.
- **DONE:** The manifest stores `signal_state`, `signals`, `windows` and `per_candle_states`; native state/event reads/writes use primitive Parquet directly. Async writes use pandas 3 Copy-on-Write snapshots instead of deep-copying tick frames or invoking row serializers. Source tick/candle artifacts remain distinct; their generic writer and Parquet encoder also use shallow Copy-on-Write snapshots. Legacy nested object cells retain explicit deep copies for async isolation.
- **DONE:** The runner consumes native artifacts directly. Export joins interleaved streams on native index keys plus a grouped duplicate occurrence ordinal, preserving original tick order without Cartesian duplication. Export writes `<output>.parquet`, `<stem>_signals.parquet` and `<stem>_windows.parquet`; summary counts signal-table rows by family. Replay configuration and backtesting requests fail explicitly before fetch/write; the CLI requires Parquet.

## Source map

| Responsibility | Source |
| --- | --- |
| Stream orchestration and continuation | `src/application/xauusd_trading_strategy_1_vector/the_strategy.py`, `runner.py` |
| Whole-stream state calculation | `src/application/xauusd_trading_strategy_1_vector/columnar.py` |
| Breakout events and sequence | `src/application/xauusd_trading_strategy_1_vector/columnar_breakouts.py` |
| Greedy windows, aging and latches | `src/application/xauusd_trading_strategy_1_vector/columnar_windows.py` |
| Aligned gathers and primitive event construction | `src/application/xauusd_trading_strategy_1_vector/columnar_helpers.py` |
| Typed native outputs/continuation | `src/application/xauusd_trading_strategy_1_vector/domain/columnar.py` |
| Primitive persistence and export | `src/infrastructure/result_processing/io.py`, `src/application/xauusd_trading_strategy_1_vector/reporting.py` |
| Independent scalar characterization and row-operation guard | `tests/test_native_columnar.py`; existing breakout/state/manifest regressions remain active |

## Acceptance evidence

- Scalar-oracle tests compare every exposed tick-state column, candidate fields/order, opening snapshots and terminal active window state across randomized prices, window widths 1/3/5/10, pullback controls, day resets and multiple zones.
- Chunked processing, including a split inside a bar and duplicate timestamps, must match whole-stream processing in values, order, indexes and dtypes.
- Invalid columns/dtypes/timestamp precision are rejected. Production execution is tested with scalar `step`, `iterrows` and `itertuples` forbidden; primitive persistence is tested with Python `Series.map` forbidden. AST guards cover every native algorithm module.
- Test-only adapters reconstruct scalar candidate/window objects to retain existing assertions; they are not imported by production.
- Final full regression suite: 291 passed (72.05 s, two pytest workers), including nanosecond bar IDs, changed candle inputs during same-bar continuation, new-day zone replacement, asynchronous snapshot isolation and export of interleaved streams with duplicate timestamps. After the source-I/O Copy-on-Write change, 23 affected persistence/pipeline tests pass, including a writer blocked until after caller mutation to prove snapshot isolation. Greedy-window mutation (`window_bars + 1`) was caught by the scalar comparison and reverted. Final `pre-commit run`: PASS, including unit tests, ratchet, decorator check, formatting and object-annotation guard. Scoped mypy passes for the five native source files with missing third-party stubs ignored. Synthetic seed 91, 20,000 ticks/100 observed bars/32,935 signals, one run with tracemalloc enabled and preparation/I/O excluded: native 3.111 s / 17.85 MiB traced peak; scalar object/JSON reference 24.444 s / 196.56 MiB. The narrowed output contract contributes to the memory difference; these are workload-specific measurements, not general performance guarantees. Python characterization does not establish native MT5 execution parity.

## Separate future scope

These items remain **NOT IMPLEMENTED** and do not block the approved signals-only contract:

- Execution replay (former F7/F8): replace order/admission/fill/protection/risk feedback with a defined batch economics interface and a native or compiled numeric state machine. Preserve same-tick effects, pending expiration, fees, failed operations, balance, daily locks and strict structure-stop scan bounds; no interpreted tick/candle fallback.
- Legacy snapshot/JSON projections (former F9-F12): normalize execution snapshots, orders, positions and trace fragments before reconnecting replay to a columnar runner. These legacy functions remain callable outside the native signals path.
- Recorded-native playback (former F13): migrate init/tick/deal playback and checkpoint comparison to shared batch interfaces; require complete matching native recordings/source identity and first-difference checks before claiming parity.
- Zone normalization (former F14): migrate configuration-row loading/merging to typed zone columns while preserving priority/tie order, strict `< 1.5` merge gaps, IDs, neighbor space and target selection. Current fixed zone loops are independent of tick/candle cardinality.
- Broad legacy AST audit: extend the native guard when another execution/compatibility entrypoint is migrated; do not classify a callback wrapper as vectorization.
