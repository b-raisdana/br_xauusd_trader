# Current state

## Active objective

Implement `docs/TradingStrategy.v1.0.md` as three DDD/SOA services: signal, order, and position. Treat the active specifications and current Leader clarifications as authority; prior implementations and their tests are references only.

## Implemented

- V1 domain config validates M15 trend, RSI, Zero Lag MACD, breakout, zone, entry, session, and position parameters.
- Domain market functions validate UTC nanosecond candles and zones with Pandera; RSI and DEMA Zero Lag MACD use `pandas-ta` on completed candles. `@pandera_validate` guards stage DataFrame inputs/outputs.
- Application contracts use immutable, versioned stage results and content-addressed artifact references. Stage and snapshot-ingress protocols enforce one input and one output.
- Risk ownership is documented in [TradingStrategy.Orders.v1.0.md](TradingStrategy.Orders.v1.0.md): order generation owns sizing/budget gates; position management records net realized PnL for the next order cycle.

## Verified data

For 2026-07-29, local `strategy-results/ticks.26-07-29.gxA2Pnh.parquet` contains 902,975 XAUUSD! / opofinance ticks from 01:00:00.729Z through 23:59:58.639Z. `ranges.csv` contains 12 normal zones for that date. The installed MT5 terminal returned 276 M5 and 92 M15 candles; every Bid-derived OHLC field matched the local ticks exactly (1,472 of 1,472 fields; maximum delta 0). The v1 market calculations ran on these UTC ns MT5 frames: 90 eligible M15 rows (UP 43 / DOWN 35 / NONE 12), RSI ready on 262 M5 rows, and `pandas-ta` DEMA signal ready on 251 M5 rows. DEMA readiness differs from the fresh manual prototype because `pandas-ta` seeds EMA internally; matched-history Python/EA parity remains open. The dataset is one broker-day and does not establish profitability.

## Verification

- `C:\Code\venv-shared-pandas` Python 3.12.8, pandas 3.0.5, Pandera 0.32.1, and pandas-ta 0.4.71b0 were used for final focused checks.
- All five focused `strategy_v1` test modules: 24 tests pass, including Pandera rejections for missing columns, invalid dtypes, missing output columns, and incorrect UTC index precision. The unit gate contains 25 tests including `test_tick_schema.py`.
- Tests for the absent `application.xauusd_trading_strategy_1_vector` package were deleted at the Leader's request; they did not run against the active checkout and were not used as v1 specifications.
- Ruff, formatting, `git diff --check`, and all hooks in `pre-commit run --files <task files>` pass, including pytest-fast, ratchet, and Pandera decorator checks. A diagnostic `--all-files` run also exposed pre-existing repo-wide line-ending normalization and forbidden `object` annotations in untouched `duckdb_cache.py` and `domain/ohlcv/ohlcv.py`; hook-only edits to unrelated files were reverted.
- The real MT5 check on Python 3.12 returned 276 M5 / 92 M15 rows, 262 ready RSI values and 251 ready DEMA signal values; all indexes were UTC nanoseconds.

## Open work

The Leader resumed work on 2026-11-11 to clear the pre-commit failures and remove old tests. Resume strategy work from [strategy v1 implementation](todo/strategy-v1-implementation.md): signal rules, order, position, end-to-end replay, cost acceptance, and parity remain incomplete. Order sizing needs sourced commission/swap/fee/slippage; consecutive-loss deduction and broker holiday/session calendar also need resolution. No live order execution is authorized.
