# Strategy v1 implementation

Implement the active signal, order, and position specifications as DDD domain policies behind separate SOA stage contracts. Do not copy prior implementation behavior. Keep calculations vectorized, validate DataFrames with Pandera, and move large frames through immutable artifact references.

## Resume status

- **Resumed on 2026-11-11 for full v1 implementation.** The strategy remains incomplete and is not approved for live use.
- Completed foundation: v1 config/contracts, artifact store, MT5 and zone adapters, UTC-nanosecond input checks, Pandera schemas, closed-candle filtering, M15 trend, RSI/DEMA MACD confirmation, unique zone membership, two-sided reversal invalidation, risk budget/cost/sizing functions, order-price rules, MT5 risk calculator, position lifecycle core/service, and 61 passing tests.
- Real-data check: 2026-07-29 MT5 M5/M15 candles and local OPO ticks/zones were inspected; 1,472 Bid-derived OHLC fields matched exactly. Domain indicator output was run on the 276 M5 / 92 M15 candles.
- Use the project environment `C:\Code\venv-shared-pandas` (Python 3.12.8, pandas 3.0.5, Pandera 0.32.1, pandas-ta 0.4.71b0) for subsequent verification; the global Python 3.14 install is not the target environment.
- `pandas-ta` DEMA reports 251 ready signal rows on the one-day MT5 sample; the fresh manual prototype reported 210 because seeding differs. This is not an accepted MT5 parity result.
- The saved tick artifact has 1,512 repeated precise timestamps with differing quotes; preserve source row order for same-time events. The currently inspected saved candle artifact contains M15 only, so no full M5 replay was claimed.
- Public OPO instrument/account cost information was inspected, but it does not establish this account's historical commission/swap/fee/slippage. The cost model and order sizing remain unapproved.
- Tests tied to the removed pre-v1 package were deleted at the Leader's request; active tests under `tests/` cover current v1 foundations and the shared MT5 tick schema.

## Signal stage

- **IN PROGRESS** — config, immutable contracts, MT5/zone adapters, M15 trend, `pandas-ta` RSI, DEMA Zero Lag MACD confirmations, UTC/Pandera checks, and closed-candle filtering exist.
- Remaining: tick-driven reversal/pullback lifecycle, startup state, per-zone overlap edge use, strict confirmation/expiry ordering, concrete signal service, and real-tick replay.
- Implement user-confirmed rules: exit outranks same-candle MACD; reversal cancels when a closed M5 bar is strictly more than $1 outside either zone boundary; unconfirmed pullback cancels on leaving the zone; only closed indicators are used; pullback return must occur in the five M5 bars after the breakout close (10:00 break permits return through the 10:25 candle, before 10:30); confirmation gets a separate five-M5 window; overlap interiors are ineligible.
- Acceptance: deterministic boundary tests plus a replay over matching ticks, MT5 M5/M15 bars, and that date's zones; preserve hashes and output counts.

## Order stage

- **IN PROGRESS** — target-zone/fallback TP, fixed LIMIT-band readiness, DST-aware session SL, net-loss budgets, consecutive-loss reset/consumption, OPO public cost stress, native MT5 risk calculator, volume-step rounding, and budget/margin gates exist.
- Still require: account/symbol snapshot and native profit/margin were not obtainable on 2026-11-11 because MT5 returned `No IPC connection`; current-account execution costs and broker SL/TP constraints remain unverified. Fee/slippage history is absent; explicit stress estimates are not realized costs.
- Remaining: concrete order service, stale LIMIT lifetime/cutoff orchestration, session/holiday calendar source, immutable risk audit artifact, and real-data order replay.
- Consecutive-loss rule is resolved: each `PnL > -1 USD` resets the fixed budget to `max(40 USD, 2 * PerOrderRiskableMoney)`; losses `PnL <= -1 USD` consume it by absolute net amount, and gains do not offset the loss sum.

## Position stage

- Implement single-position lifecycle, LIMIT/fill/close events, protection, holding/session cutoffs, reverse-entry sequencing, net outcome recording, and retry state for rejected/unknown closes. The retry rule is confirmed; implementation remains open.
- Resolve the broker symbol/holiday session schedule and event source. No parallel broker/account reads inside a stage; inputs arrive through the snapshot-ingress service.
- Acceptance: deterministic lifecycle tests and ordered replay using actual ticks plus recorded or explicitly simulated execution events.

## End-to-end and parity

- Artifact store and MT5 market-data/zone adapters exist. Implement snapshot ingress, three concrete application services, and a replay CLI.
- Run all three services in sequence on real data with a versioned config and captured provenance. Report sample, trade, costs, and uncertainty; a one-day sample does not establish profitability.
- Native MT5 compilation, matched event traces, full field-level Python/EA parity, and live readiness are separate gates; do not claim them from Python replay.
