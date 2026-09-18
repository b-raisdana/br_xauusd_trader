# Scenarios: on_tick.py with vectorbt Random CSV

## Data Generation

Random OHLCV CSV generator parameters (XAUUSD realistic):

- Bar count: 50 M15 bars (12.5 hours)
- Price range: 2300.00 – 2400.00 with random walk
- Volume: 50 – 500 per bar
- Edge cases injected: bar 10 = zero volume, bar 20 = doji (O=H=L=C), bar 35 = monotonic uptrend
- Timestamps: consecutive M15 intervals from `2026-09-16T00:00:00+00:00`

Data loading (vectorbt 0.28.2 API):

```python
import pandas as pd
import vectorbt as vbt
df = pd.read_csv('data/random_ohlcv.csv', parse_dates=['Datetime'], index_col='Datetime')
sd = vbt.SyntheticData.from_data({'XAUUSD': df}, download_kwargs={})
close = sd.get('Close')
```

## Scenario 1: Normal Tick Processing

- **Setup**: Load `data/random_ohlcv.csv` via `SyntheticData.from_data`. `StrategySettings(run_current_event_loop=True, emit_time_basis_probe=True)`. Mock `EventLoop` returns `True` for `process_tick`.
- **Action**: For each index in `close`, construct `Tick(time=idx, bid=close.iloc[i], ask=close.iloc[i])` and call `on_tick()`.
- **Expected**: `handled=True`, `time_basis_probe_emitted` increments from `True` through bar 4, then `False`. `event_loop_failed=False`. `OnTickResult` returned for all 50 bars.

## Scenario 2: Probe Emit Limit

- **Setup**: Same as Scenario 1, but verify probe count precisely.
- **Action**: Track `strategy_runtime.time_basis_probe_count` and `time_basis_probe_emitted` across all ticks.
- **Expected**: `time_basis_probe_count` reaches exactly 5. Probe emitted on ticks 1–5 only (assuming all `is_valid=True`).

## Scenario 3: Event Loop Disabled

- **Setup**: `StrategySettings(run_current_event_loop=False, emit_time_basis_probe=True)`. `event_loop` provided but should not be called.
- **Action**: Call `on_tick()` for each bar.
- **Expected**: `handled=True`, probe fires for first 5 ticks, event loop never invoked. `event_loop_failed=False`.

## Scenario 4: Event Loop Absent

- **Setup**: `StrategySettings(run_current_event_loop=True, emit_time_basis_probe=False)`. `event_loop=None`.
- **Action**: Call `on_tick()` once.
- **Expected**: `handled=False`, `event_loop_failed=True`. Second call returns same with `event_loop_failure_reported=True` on runtime state (no double reporting).

## Scenario 5: Event Loop Exception

- **Setup**: Mock `EventLoop.process_tick()` raises `RuntimeError` on tick 25 (call 25). All other calls return `True`.
- **Action**: Call `on_tick()` for ticks 1–50.
- **Expected**: Tick 25 (index 24) returns `handled=False`, `event_loop_failed=True`. Ticks 1–24 and 26–50 return `handled=True`, `event_loop_failed=False`. `event_loop_failure_reported=True` on runtime after tick 25. Mock `process_tick` called for all 50 ticks (exception caught, processing continues).

## Scenario 6: Invalid Ticks (NaN/Zero Prices)

- **Setup**: Use bars where `bid=NaN/ask=NaN` and `bid=0.0/ask=0.0` from the random CSV. `run_current_event_loop=True`.
- **Action**: Call `on_tick()` for invalid ticks.
- **Expected**: `is_valid=False` on invalid ticks. Probe does not increment on invalid ticks (gate: `tick.is_valid`). Event loop IS still called for invalid ticks (only probe count is gated). `OnTickResult` returned for each without exception. `time_basis_probe_count` remains 0 if all ticks are invalid.

## Scenario 7: vectorbt Integration Loop

- **Setup**: Load random CSV via `SyntheticData.from_data`. Iterate `close` index for tick-equivalent data.
- **Action**: For each bar, construct `Tick(time=idx, bid=close.iloc[i], ask=close.iloc[i])` and call `on_tick()`.
- **Expected**: Full iteration completes. All `OnTickResult` objects have consistent fields. No state corruption across bars.

## Scenario 8: handle_tick Alias

- **Setup**: Same as Scenario 1 but call `handle_tick` instead of `on_tick`.
- **Action**: `handle_tick(tick, settings, runtime, environment, event_loop)`.
- **Expected**: Identical behavior to `on_tick`. `handle_tick is on_tick` reference holds.
