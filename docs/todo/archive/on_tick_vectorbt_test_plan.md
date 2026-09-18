# Test Plan: on_tick.py Validation

## Objective

Validate tick processing behavior using backtesting with randomly generated market data.

## Scope

- `on_tick()` entry point and result contract
- Delegation to event loop
- Time basis probe emission (up to 5 ticks)
- Event loop activation gate
- Graceful failure when event loop is absent
- Exception isolation in event loop processing

## Test Data

A randomly generated market data CSV provides data for backtesting. The CSV must contain columns compatible with the backtesting framework's synthetic data format:

| Column | Type | Description |
|--------|------|-------------|
| Open | float | Candle open price |
| High | float | Candle high price |
| Low | float | Candle low price |
| Close | float | Candle close price |
| Volume | float | Candle volume |
| Datetime | ISO 8601 | Candle timestamp (UTC), index column |

The random generator produces realistic XAUUSD prices with M15 bars including edge cases: zero-volume bars, identical OHLC (doji), and monotonic price sequences.

## Backtesting Report

Process ticks via `on_tick()`, convert handled results into entry signals, and produce a backtest report with columns: Datetime, Open, High, Low, Close, Entry, Exit, OnTick_Handled, Portfolio_Value, Returns.

## Approach

1. Generate random CSV
2. Load CSV, wrap in synthetic market data
3. Iterate close index, constructing tick objects from OHLCV rows
4. Configure settings with event loop enabled and probe emission enabled
5. Call `on_tick()` per bar, inspect results
6. Run with event loop disabled to verify probe-only path
7. Run with event loop absent to verify failure path

## Acceptance Criteria

- `on_tick()` returns result for every bar without raising.
- Probe emitted on first 5 valid ticks when enabled.
- Event loop failure reported correctly when absent or failing.
- All exceptions caught and reported via event loop failure flag.
