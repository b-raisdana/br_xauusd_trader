# VectorBT Code Reduction Plan

Scope: reduce/eliminate custom code in `src/application/xauusd_trading_strategy_1_vector/` and
`src/infrastructure/result_processing/` by maximizing usage of VectorBT 1.1.1 features.
`Portfolio.from_signals()` is one example; the full feature inventory is mapped below.

## Current vectorbt usage

VectorBT is imported in exactly one file: `backtest.py`. Only `vbt.Portfolio.from_signals` is used.
Everything else (trend math, engagement state, order/position simulation, PnL, risk, reporting)
is hand-rolled.

Two execution paths exist:

1. **Native signals-only path** (columnar): `__main__.py` -> `runner.py` ->
   `the_strategy.py::process_tick_data` -> `columnar_process/__main__.py::process_columns`
   -> `signals.py` / `engagement.py` / `trend.py` -> `ResultFilesManifest` artifacts.
2. **Execution replay path**: `replay.py::ExecutionReplay` (782 lines) - custom broker simulation
   (fills, SL/TP, sessions, risk budget, daily-loss lock, pullback windows).
3. **Backtest reporting**: `backtest.py` re-derives entries/exits from position snapshots and runs
   `Portfolio.from_signals`.

## Feature -> code mapping

| VectorBT feature | Replaces | File / lines |
| --- | --- | --- |
| `Portfolio.from_orders` | `_extract_signals` (entries/exits re-derivation from position snapshots) | `backtest.py:26-61` |
| `Portfolio.stats()` | manual metric printing (annualized return, Sharpe, Calmar, max DD, win rate, avg/best/worst PnL) | `backtest.py:151-196` |
| `Portfolio.plot*()` family, `vbt.Rep` | manual report/trades serialization and any future charting | `backtest.py:199-246` |
| `vbt.FMAX` / `vbt.FMIN` (flexible-window max/min) | `_reduce_trend_arrays` + `compute_references` (variable-window max/min over trend points) | `trend.py:62-92` |
| `vbt.IndicatorFactory` | manual registration of trend/reference/engagement columns; gains stats/plots for free | `trend.py`, `engagement.py` |
| `Portfolio.from_order_func` (numba per-bar order func) | per-tick fill/exit PnL accounting in the metric path | `replay.py::_fill/_close/_settle` |
| `vbt.Ranges` / `RangeSplitter` / `RollingSplitter` | future parameter-sweep loops (robustness testing) | none yet |
| `Portfolio.from_random_signals` / `from_holding` | future benchmark code (random-entry, buy-and-hold baselines) | none yet |
| `vbt.Data` (resample/align) | manual 15-min candle merge with offset lookup | `infrastructure/result_processing/__main__.py:15-36` |
| `Portfolio.orders` / `Portfolio.positions` records | `_project_snapshots` order/position projection stages (if metric path moves to `from_orders`) | `infrastructure/result_processing/__main__.py:39-92` |

## Reduction opportunities (priority order)

### P0 - `backtest.py` (201 lines, ~80 removable)

1. **Delete `_extract_signals`** (36 lines). It re-derives entries/exits from
   `position_id`/`position_status` snapshots and uses `bid` as close. Replace with
   `Portfolio.from_orders(close=bid, size=volume, direction=order_direction, price=fill_price, ...)`
   built from the **orders artifact** (`order_time`, `fill_price`, `close_price`, `order_direction`)
   or the `execution_events` stream (SUBMIT/FILL/CLOSE events). Benefits:
   - removes the position-snapshot -> signal -> portfolio two-step;
   - more accurate: exact fill prices instead of snapshot-based detection;
   - preserves bid/ask fill semantics via per-order `price` (unlike `from_signals`, which values at close).
2. **Replace the metric block in `print_backtest_report`** (~50 lines of prints) with
   `portfolio.stats()` (one call returns 100+ metrics incl. Sharpe, Calmar, max drawdown,
   win rate, profit factor) and `portfolio.trades.stats()`. Keep the CLI-facing summary as
   a thin selector over the stats frame.
3. `save_backtest_report` / `save_backtest_trades` (47 lines) already wrap `portfolio.stats()`
   and `portfolio.trades.records`; only the CSV/parquet branch stays.
4. Add `portfolio.plot()` / `plot_drawdowns()` / `plot_trades()` or `vbt.Rep` HTML report instead
   of any future hand-rolled charting (the dead `src/presentation/vectorbt_backtest_report.py`
   is already fully commented out - delete it).

### P1 - `trend.py` (99 lines, ~30 removable)

- `_reduce_trend_arrays` + `compute_references` (31 lines) compute a variable-window
  max/min over the last `trend_count` trend points. This is exactly `vbt.FMAX`/`vbt.FMIN`,
  which accept a window array. Replace the manual slot loop with one FMAX/FMIN call per side.
- `compute_bar_time` (pandas `.floor("15min")`) and `update_trend` (ffill state) have no
  vectorbt equivalent and stay.

### P2 - Indicator registration (capability gain, ~neutral line count)

Register trend/reference/engagement computations as `vbt.IndicatorFactory` indicators. This
does not remove logic but adds built-in stats, plots, and broadcasting, replacing future
custom telemetry around those columns.

### P3 - Execution replay path (large, risky, partial only)

`ExecutionReplay` (782 lines) overlaps with vectorbt's simulation engine in:

- `_fill` / `_close` PnL, cost, and balance accounting -> `Portfolio` economics (fees,
  slippage, per-order price);
- `order_snapshot` / `position_snapshot` -> `Portfolio.orders` / `Portfolio.positions` records;
- `_settle` pending-stop trigger + SL/TP exit -> `Portfolio.from_orders` per-order price/direction,
  or `Portfolio.from_order_func` for a numba-compiled per-bar order function.

**Cannot be removed** (strategy-specific rules, no vectorbt equivalent):
session windows (`_session`), preclose/operational locks, daily-loss guard (`_daily_guard`),
risk budget (`_budget` / `_risk_used`), position caps, pullback window lifecycle, pending-stop
semantics, profit-protection trailing (`_manage`), reversal usage limits.
Recommendation: keep `ExecutionReplay` as the MT5-parity source of truth; only the *metric*
path (P0) moves to `from_orders`. A future `from_order_func` experiment may replace the PnL
accounting for fast parameter sweeps, but the zone logic is too stateful for numba today.

### P4 - Result processing (`infrastructure/result_processing/__main__.py`, 92 lines)

- `merge_results_with_candles` (22 lines): manual 15-min candle merge with offset lookup.
  `vbt.Data` provides resample/align, but the one-off merge is cheaper to keep.
- `_project_snapshots` + `generate_order_management_columns` / `generate_position_tracking_columns`
  (~50 lines): project the last order/position snapshot per tick. If P0 moves the backtest to
  `Portfolio.from_orders`, these stages become unnecessary for the vectorbt path
  (`portfolio.orders` / `portfolio.positions` provide records directly). Remove only after
  confirming no other consumer needs the orders/positions artifacts.

### P5 - Dead code

- `src/presentation/vectorbt_backtest_report.py` (108 lines, 100% commented out): delete.
- `market.py::MarketState` (254 lines): only referenced from commented-out code in
  `tests/` and `archive_not_used_trash/`; the native path uses `ColumnarMarket` instead.
  Verify no hidden importers, then remove (keep `ClosedHistory` type alias if `replay.py`
  still needs it).

## What cannot be removed by vectorbt

Strategy rules that are not generic portfolio machinery: zone model and engagement latches
(`engagement.py`, `domain/zone.py`), breakout/reversal/pullback candidate generation
(`signals.py`, `columnar_process/`), pullback window lifecycle (`columnar_process/windows.py`),
protection and entry math (`domain/entry.py`, `domain/protection.py`, `domain/robust.py`,
`domain/state.py`), and all replay guards listed in P3.

## Risks

- **Fill semantics**: `from_signals` values positions at close; the strategy fills at ask (buy) /
  bid (sell). Use `from_orders` with per-order `price` for the replay-based backtest, or the
  metrics will drift from MT5 parity.
- **Look-ahead**: vectorbt does not enforce causality; signal extraction must remain causal.
- **Numba constraint**: `from_order_func` requires numba-compatible code; the pullback state
  machine is not portable today.
- **Parity**: any removed replay accounting must be re-validated against `tests/test_robust_mt5_parity.py`
  expectations (currently commented out) before deletion.

## Execution order

1. P0 `backtest.py` -> `from_orders` + `stats()` (biggest reduction, correctness gain).
2. P1 `trend.py` -> `FMAX`/`FMIN`.
3. P2 `IndicatorFactory` registration.
4. P4 drop `_project_snapshots` stages once P0 lands and consumers are confirmed.
5. P5 dead-code deletion.
6. P3 `from_order_func` experiment (optional, fast-sweep path only).
