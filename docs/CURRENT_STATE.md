# Current state

## Active objective

Implement `docs/TradingStrategy.v1.0.md` as three DDD/SOA services: signal, order, and position. Treat the active specifications and current Leader clarifications as authority; prior implementations and their tests are references only.

## Implemented

- V1 domain config validates M15 trend, RSI, Zero Lag MACD, breakout, zone, entry, session, and position parameters.
- Domain functions filter closed M5/M15 candles at the inclusive close-time boundary, calculate M15 trend, RSI/DEMA MACD confirmations, and unique zone membership; stable DataFrames use UTC nanosecond Pandera schemas and `@pandera_validate`.
- The main strategy document consolidates answered task questions, including two-sided reversal cancellation at strictly more than $1 outside the zone and confirmed opposite-signal close behavior.
- Order-domain functions now calculate DST-aware session SL distance, nearest-zone/fallback TP and fixed LIMIT-band readiness. Risk-domain functions calculate 24-hour net-loss budget, fixed-budget consecutive-loss consumption, OPO-based cost stress, and volume/margin/budget gates.
- An MT5 risk adapter and immutable risk snapshot model call native `OrderCalcProfit`/`OrderCalcMargin` and expose account/symbol metadata without leaking account identifiers.
- `docs/TradingStrategy.v1.0.md` consolidates Leader-confirmed rules from the task; signal, order, and position documents retain detailed algorithms.
- Application contracts use immutable, versioned stage results and content-addressed artifact references. Stage and snapshot-ingress protocols enforce one input and one output.
- Risk ownership is documented in [TradingStrategy.Orders.v1.0.md](TradingStrategy.Orders.v1.0.md): order generation owns sizing/budget gates; position management records net realized PnL for the next order cycle.

## Verified data

For 2026-07-29, local `strategy-results/ticks.26-07-29.gxA2Pnh.parquet` contains 902,975 XAUUSD! / opofinance ticks from 01:00:00.729Z through 23:59:58.639Z. `ranges.csv` contains 12 normal zones for that date. The earlier MT5 read returned 276 M5 and 92 M15 candles; every Bid-derived OHLC field matched the local ticks exactly (1,472 of 1,472 fields; maximum delta 0). The v1 market calculations ran on those UTC ns MT5 frames: 90 eligible M15 rows (UP 43 / DOWN 35 / NONE 12), RSI ready on 262 M5 rows, and `pandas-ta` DEMA signal ready on 251 M5 rows. DEMA readiness differs from the fresh manual prototype because `pandas-ta` seeds EMA internally; matched-history Python/EA parity remains open. The saved candle artifact currently inspected contains M15 only, and the tick artifact has 1,512 repeated precise timestamps with differing quotes; the candidate replay must preserve their stored order. This snapshot alone cannot validate the full M5 signal lifecycle. The data is one broker-day and does not establish profitability.

## Verification

- `C:\Code\venv-shared-pandas` Python 3.12.8, pandas 3.0.5, Pandera 0.32.1, and pandas-ta 0.4.71b0 were used for final focused checks.
- `python -m pytest -q -n0 tests`: 61 tests pass, including closed-candle boundaries, two-sided reversal invalidation and MACD precedence, indicator thresholds, order-price rules, net-loss budgets, cost estimates, risk sizing, MT5 adapter contracts, position lifecycle/service, and existing market/zone/artifact checks.
- Tests for the absent `application.xauusd_trading_strategy_1_vector` package were deleted at the Leader's request; they did not run against the active checkout and were not used as v1 specifications.
- Ruff, formatting, and all hooks in `python -m pre_commit run --files <task files>` pass, including pytest-fast, ratchet, Pandera decorator checks, and forbidden-`object` annotation checks. A diagnostic `--all-files` run also exposed pre-existing repo-wide line-ending normalization and forbidden `object` annotations in untouched `duckdb_cache.py` and `domain/ohlcv/ohlcv.py`; hook-only edits to unrelated files were reverted.
- The real MT5 check on Python 3.12 returned 276 M5 / 92 M15 rows, 262 ready RSI values and 251 ready DEMA signal values; all indexes were UTC nanoseconds.

## Open work

The Leader resumed work on 2026-11-11 to clear pre-commit failures, remove old tests, and continue strategy implementation. The MT5 terminal currently returns `No IPC connection`, so account/symbol risk metadata and live `OrderCalcProfit`/`OrderCalcMargin` were not verified during this resume. Public OPO rates plus explicit slippage stress are implemented as estimates; they do not establish the current account's historical cost. Concrete stage services, complete tick-driven pullback state, position execution lifecycle, calendar/event ingestion, end-to-end replay, and Python/EA parity remain incomplete. No live order execution is authorized.
