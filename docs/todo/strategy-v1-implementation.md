# Strategy v1 implementation

Implement the active signal, order, and position specifications as DDD domain policies behind separate SOA stage contracts. Do not copy prior implementation behavior. Keep calculations vectorized, validate DataFrames with Pandera, and move large frames through immutable artifact references.

## Resume status

- **Resumed on 2026-11-11 for pre-commit cleanup.** The strategy remains incomplete and is not approved for live use.
- Completed foundation: v1 config/contracts, artifact store, MT5 and zone adapters, UTC-nanosecond input checks, Pandera schemas, M15 trend, RSI and DEMA Zero Lag MACD, plus 28 focused tests.
- Real-data check: 2026-07-29 MT5 M5/M15 candles and local OPO ticks/zones were inspected; 1,472 Bid-derived OHLC fields matched exactly. Domain indicator output was run on the 276 M5 / 92 M15 candles.
- Use the project environment `C:\Code\venv-shared-pandas` (Python 3.12.8, pandas 3.0.5, Pandera 0.32.1, pandas-ta 0.4.71b0) for subsequent verification; the global Python 3.14 install is not the target environment.
- `pandas-ta` DEMA reports 251 ready signal rows on the one-day MT5 sample; the fresh manual prototype reported 210 because seeding differs. This is not an accepted MT5 parity result.
- Public OPO instrument/account cost information was inspected, but it does not establish this account's historical commission/swap/fee/slippage. The cost model and order sizing remain unapproved.
- Tests tied to the removed pre-v1 package were deleted at the Leader's request; active tests under `tests/` cover current v1 foundations and the shared MT5 tick schema.

## Signal stage

- **IN PROGRESS** — config, immutable contracts, MT5/zone adapters, M15 trend, `pandas-ta` RSI, DEMA Zero Lag MACD, UTC/Pandera checks, and focused tests exist.
- Implement validated zone ingestion from `C:\Code\data\XAAUSD_PA\ranges.csv`, unique non-overlapping zone regions, reversal/pullback state, closed-candle event ordering, and strict expiry.
- Implement user-confirmed rules: exit outranks same-candle MACD; only closed indicators are used; pullback return must occur in the five M5 bars after the breakout close (10:00 break permits return through the 10:25 candle, before 10:30); confirmation gets a separate five-M5 window; overlap interiors are ineligible.
- Acceptance: deterministic boundary tests plus a replay over matching ticks, MT5 M5/M15 bars, and that date's zones; preserve hashes and output counts.

## Order stage

- Implement target-zone selection, LIMIT wait/revalidation at fixed `E_ref`, session-based SL, TP, risk sizing, broker volume/margin checks, rolling loss budgets, and immutable order/risk audit outputs.
- **BLOCKED ON INPUT** — obtain commission/swap/fee/slippage source and values before sizing; never treat unknown costs as zero.
- Resolve how consecutive net losses reduce the remaining consecutive-loss budget. Reject orders until required account, cost, or broker constraints are present.
- Acceptance: deterministic price/volume/budget boundaries and an actual-data replay with the approved cost model.

## Position stage

- Implement single-position lifecycle, LIMIT/fill/close events, protection, holding/session cutoffs, reverse-entry sequencing, net outcome recording, and retry state for rejected/unknown closes.
- Resolve the broker symbol/holiday session schedule and event source. No parallel broker/account reads inside a stage; inputs arrive through the snapshot-ingress service.
- Acceptance: deterministic lifecycle tests and ordered replay using actual ticks plus recorded or explicitly simulated execution events.

## End-to-end and parity

- Implement the artifact store, MT5 market-data/zone adapters, snapshot ingress, three concrete application services, and a replay CLI.
- Run all three services in sequence on real data with a versioned config and captured provenance. Report sample, trade, costs, and uncertainty; a one-day sample does not establish profitability.
- Native MT5 compilation, matched event traces, full field-level Python/EA parity, and live readiness are separate gates; do not claim them from Python replay.
