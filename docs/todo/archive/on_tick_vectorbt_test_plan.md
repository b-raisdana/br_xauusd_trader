# Test Plan: on_tick.py with vectorbt

## Objective

Validate `src/application/xauusd_trading_strategy_1/on_tick.py` tick processing behavior using vectorbt backtesting with a randomly generated OHLCV CSV as market data.

## Scope

- `on_tick()` entry point and result contract
- `process_current_event_loop_tick()` delegation
- Time basis probe emission (up to 5 ticks)
- Event loop activation gate (`run_current_event_loop` setting)
- Graceful failure when event loop is absent
- Exception isolation in event loop processing
- Vectorbt backtesting report generation from on_tick signals

## Test Data

A randomly generated OHLCV CSV provides market data for vectorbt backtesting and report generation. The CSV must contain columns compatible with vectorbt's `SyntheticData`:

| Column | Type | Description |
|--------|------|-------------|
| `Open` | float | Candle open price |
| `High` | float | Candle high price |
| `Low` | float | Candle low price |
| `Close` | float | Candle close price |
| `Volume` | float | Candle volume |
| `Datetime` | ISO 8601 | Candle timestamp (UTC), index column |

The random generator produces realistic XAUUSD prices around `2300-2400` range with M15 bars across 50 candles, including edge cases: zero-volume bars, identical OHLC (doji), and monotonic price sequences.

## Backtesting Report

`scripts/vectorbt_backtest_report.py` processes ticks via `on_tick()`, converts `handled=True` results into entry signals, and runs a vectorbt `Portfolio.from_signals` backtest producing `docs/todo/on_tick_vectorbt_report.csv` with columns: `Datetime`, `Open`, `High`, `Low`, `Close`, `Entry`, `Exit`, `OnTick_Handled`, `Portfolio_Value`, `Returns`.

## Environment

```powershell
.\.venv\Scripts\python.exe -c "import vectorbt; print(vectorbt.__version__)"
```

Expected: `0.28.2` (pinned per Runbook).

## Approach

1. Generate random CSV via `scripts/generate_random_ohlcv.py` (or inline).
2. Load CSV with pandas, wrap in vectorbt:
   ```python
   import pandas as pd
   import vectorbt as vbt
   df = pd.read_csv('data/random_ohlcv.csv', parse_dates=['Datetime'], index_col='Datetime')
   sd = vbt.SyntheticData.from_data({'XAUUSD': df}, download_kwargs={})
   close = sd.get('Close')
   ```
3. Iterate `close` index, constructing `ProceduralTick` objects from OHLCV rows.
4. Configure `StrategySettings` with `run_current_event_loop=True` and `emit_time_basis_probe=True`.
5. Call `on_tick()` per bar, inspect `OnTickResult`.
6. Run with `run_current_event_loop=False` to verify probe-only path.
7. Run with `event_loop=None` to verify failure path.

## Acceptance Criteria

- `on_tick()` returns `OnTickResult` for every bar without raising.
- `time_basis_probe_emitted=True` for first 5 valid ticks when `emit_time_basis_probe=True`.
- `event_loop_failed=False` when a real `EventLoop` is provided.
- `event_loop_failed=True` when `event_loop=None` and failure not yet reported.
- All `process_current_event_loop_tick()` exceptions caught and reported via `event_loop_failed=True`.
