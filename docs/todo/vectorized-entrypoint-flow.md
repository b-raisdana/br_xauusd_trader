# Vector Entry Point Flow

Reviewed 2026-09-20: `src/application/xauusd_trading_strategy_1_vector/__main__.py` → zone/MT5 fetches → `ZaoneCache` → `VectorizedXauUsdStrategy` → candle context → order/position projections → export/summary. Research output is not an execution ledger. Strategy-core files were changing concurrently during this review; this batch modifies the CLI, runner, result processing, reporting and MT5 fetch error handling only.

## Verified repairs

- [x] CLI normal/debug dispatch works. Debug exports internal state; normal output retains the strategy's public columns.
- [x] Request complete zone days: normalize the first day, fetch through next midnight and retain ticks in `[start, end)`. The minute-resolution range string previously excluded the last day's final minute.
- [x] Preserve the requested MT5 symbol; report `copy_ticks_range`/`copy_rates_range` failures when MT5 returns `None`.
- [x] Reject empty zones/ticks and unsupported output extensions before writing results; invalid extensions fail before fetching.
- [x] Join only the immediately preceding closed M15 candle, prefix its payload with `candle_`, preserve tick index/order/duplicates and reject duplicate candle keys. Missing previous candles remain missing; final current-bar OHLC is not exposed at earlier ticks.
- [x] Export without duplicated index columns. Create output parent directories and encode dataclass candidate/window collections as JSON in CSV/Parquet without mutating input. Summary counts collection members rather than non-null containers.
- [x] `.venv/Scripts/python.exe -m pytest tests/test_vectorized_pipeline.py tests/test_vectorized_cache.py -q`: 20 passed. Tests cover normal/debug × CSV/Parquet, actual fetch index layouts, duplicate timestamps/candles, causal context, final-minute coverage, empty inputs, candidate serialization, symbol identity and MT5 errors. All broker calls mocked; no live run or profitability evidence.

## Remaining strategy work

- [ ] Complete reversal candidate emission and per-bar/zone/direction deduplication; compare candidates with `process_coordinator_tick`, including trend-before-touch and multi-zone gaps.
- [ ] Complete pullback penetration/attempt/fill transitions, five-bar expiry and per-zone daily usage. Window creation alone is insufficient; prove Normal/High limits and repeated pullbacks against domain/MQL fixtures.
- [ ] Replace `actions.py`'s unconditional `None` with confirmed entry preparation, risk/concurrency/margin/session/restart gates and explicit outcomes. Candidate generation must not imply execution acceptance.
- [ ] Replace order/position placeholders with accepted submissions, fills, cancellations, closes and protection events. Specify broker contract/session/account inputs and execution costs before reporting P&L; retain bid/ask side correctness and idempotent outcomes.
- [ ] Integrate native candle open/closed history into strategy decisions or explicitly retain tick-derived research semantics. Fetched OHLC currently supplies output context only; sparse ticks and mid-day initialization do not establish native MQL parity.
- [ ] Resolve repository gate: recorded changed-file pre-commit run passed Ruff check/format, but pytest reported 3 concurrently edited breakout-test failures plus 10 missing `data/random_ohlcv.zip` fixture errors; incremental ratchet reported missing `ratchet` module. Full snapshot: 66 passed, 3 failed, 10 errors. No hook bypass or clean checkpoint claimed.

The broader parity and execution acceptance criteria are in [Vectorization Implementation Plan](Vectorization%20Implementation%20Plan.md). Reconcile concurrent core edits before treating earlier state/scaffold test results as current evidence.
