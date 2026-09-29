# Vectorized XAUUSD strategy

Batch M15 signals with optional offline execution replay. Current MT5 reference: [XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5](../../../mt5/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5). **This Python implementation is not a behaviorally equivalent port.** See [divergence report](../../../docs/Divergence%20Report%20-%20MT5%20vs%20Python%20vs%20Documentation.md) and [state glossary](../../../docs/State-Variables.Glossary.csv).

## Entry points and modes

`__main__.py` loads zones/ticks/M15 candles, derives bar/day keys and calls `runner.run_vectorized_strategy`. The runner persists daily artifacts through `ResultFilesManifest`, passes the manifest through calculation/enrichment, waits for writes and closes the writer. `process_tick_data` accepts a manifest, not raw frames.

- Default CLI: signals-only. No `ReplayConfig` is passed; candidate emission does not create orders or positions.
- Programmatic `run_vectorized_strategy(..., execution=ReplayConfig(...))`: chronological replay with explicit economics, acceptance and session assumptions; no terminal order I/O.
- CLI `--backtest`: separate vectorbt reporting from scalar position fields; does not enable execution replay. Default CLI execution therefore supplies no simulated positions. Vectorbt's independent cash/fee/slippage defaults and lack of short/multi-position ledger fidelity do not reproduce replay/native accounting.
- `debug` is accepted/passed but unused by the current runner. Output suffix must be CSV or Parquet. Current acquisition ends at last zone day + 2 hours−epsilon, not a full final day.

## Calculation flow

Daily artifacts are partitioned by broker/symbol; timestamps must be nondecreasing. `ZoneCache` validates the supplied frame and returns deep-copied, daily merged zones. Its cache key is date only. Merge gap is strictly below 1.5; High dominates; IDs are assigned after merge.

`_process_bar_boundaries` requires unique native M15 candles covering observed tick bars. It uses candle open and gathers preceding observed same-day extrema, up to `TREND_POINTS_N=3`. The first observed bar has no history; current-bar highs/lows do not enter its own references. `trend.py` computes references and forward-fills strict threshold changes per day. No bootstrap or cross-day trend carry exists.

`engagement.py` creates per-zone cumulative latches and aggregate buy/sell columns. At bar starts, previous Bid is replaced with current Bid and containment uses the first observed tick. This differs from the EA's native-open seed and quote continuity.

`signals.py` emits tuple collections:

- BO: old observed tick close, engagement and close trend; emitted on next observed same-day bar with BO1... IDs. No terminal/day-boundary close. Precomputed per-zone/direction opening cooldown retains parent independently of fill outcomes.
- Reversal: updated trend and directional touch, no multi-zone gap; first candidate per bar/zone/side.
- PB: ordered scan over windows; offsets1–5, inclusive 0.20 penetration, exact broken-edge pending candidate. Without feedback, no pending acceptance/fills are assumed and retries can recur. Feedback counts must be nonnegative/nondecreasing; fills clear penetration. Normal cap 1, High unlimited; windows survive fills.

Per-tick fields are initialized anew daily. Per-candle state contains native OHLC and preceding-reference columns. Aggregate PB lineage fields are diagnostic projections, not authoritative replay lifecycle state.

## Optional replay

`actions.generate_actions` calls `ExecutionReplay.step` per tick. One replay per broker/symbol persists across manifest days. Ordered phases: rollover → session/settlement → daily lock → management → BO submissions → PB evaluation → reversal/PB submissions → snapshots. Rollover cancels pending and closes positions, raising if exposure remains unresolved.

Replay models submits/rejects/fills/cancels/closes/modifications, daily P&L, risk/concurrency/margin and session/restart gates. It uses fixed 0.01 lots, 15% gross budget, 200/300 capital profiles, unconditional candidate-bar attempt slots and fixed 6-unit protection. It retains strict PB TP extension/restoration and target-touch reversal blocking, absent from the visible new EA body. These are implemented differences, not missing placeholders. Native broker fills, partial deals, calendar/fee assumptions and missing MT5 release envelope remain outside parity evidence.

## Output and reporting

Result processing checks tick/state index agreement, joins only previous M15 context with many-to-one validation, and persists order/position stages. Collections retain all snapshots; scalar order/position columns take the last record, while `action` takes the first action. Use event collections when analyzing simultaneous activity. Export/report functions consume the manifest.

## Performance and validation boundary

Bar/reference/trend/engagement calculations use pandas/NumPy batches. Sparse signal object creation, PB feedback and execution replay contain ordered Python loops; the whole pipeline is not loop-free. Earlier benchmark/test counts describe their recorded revisions and are not current EA parity evidence. No new trading run or performance claim accompanies the 2026-09-29 source audit.

Dependencies include pandas/NumPy, Pandera schemas, shared domain models/enums, result-manifest I/O, configured MT5 acquisition and optional vectorbt. Use the repository's active Python environment and existing tests; do not treat an old scalar-contract match as proof against the replacement MQ5.
