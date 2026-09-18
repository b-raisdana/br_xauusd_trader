# Vectorized XAUUSD Trading Strategy Implementation

## Overview

This directory contains a vectorized implementation of the XAUUSD trading strategy using pandas DataFrames and vectorized operations. The implementation follows the MT5 source of truth (`mt5/XAUUSD_MVP.mq5`) and uses 15-minute bars (PERIOD_M15) for all bar-based calculations.

## Architecture

### Core Components

- **`vectorized_strategy.py`**: Main strategy implementation that processes tick data using vectorized pandas operations
- **`zone_loader.py`**: Zone data loading and management, corresponding to MT5's `LoadGeneratedRawZones`

### Key Design Principles

1. **Vectorized Operations**: Uses pandas/numpy vectorized operations instead of per-tick loops
2. **MultiIndex Structure**: Maintains the input DataFrame structure with MultiIndex (broker, symbol, datetime, date)
3. **State Management**: Represents persistent state as DataFrame columns where appropriate
4. **Group Independence**: Processes each (broker, symbol) group independently
5. **MT5 Alignment**: Follows the exact semantics of the MT5 implementation

## Implementation Status

### Completed Components

- ✅ State-Variables.Glossary.csv documenting MT5/Python state mapping
- ✅ Vectorized trend calculation using pandas operations
- ✅ Vectorized zone engagement updates
- ✅ Vectorized breakout signal generation (framework)
- ✅ Vectorized reversal signal generation (framework)
- ✅ Vectorized pullback signal generation (framework)
- ✅ 15-minute bar boundary detection and processing
- ✅ Zone data loading and management
- ✅ _temp_state DataFrame schema and processing pipeline

### Framework Components (Placeholder)

The following components have the framework implemented but require additional logic for full functionality:

- ⚠️ Breakout signal generation (needs zone state management)
- ⚠️ Reversal signal generation (needs reversal key tracking)
- ⚠️ Pullback signal generation (needs pullback window state management)
- ⚠️ Final action column generation (needs signal candidate collection and risk management)

## Usage

### Basic Usage

```python
from application.xauusd_trading_strategy_1_vector import VectorizedXauUsdStrategy, ZoneLoader
import pandas as pd

# Create input DataFrame with MultiIndex
tick_data = pd.DataFrame({
    'bid': [...],
    'ask': [...]
})
tick_data.index = pd.MultiIndex.from_arrays([
    ['broker1'] * len(tick_data),  # broker
    ['XAUUSD'] * len(tick_data),   # symbol
    pd.date_range(...),            # datetime
    pd.date_range(...).floor('s')  # date
], names=['broker', 'symbol', 'datetime', 'date'])

# Initialize strategy with zone loader
zone_loader = ZoneLoader()
strategy = VectorizedXauUsdStrategy(zone_loader)

# Process tick data
result = strategy.process_tick_data(tick_data, preload_days=['2026-09-18'])

# Result has same MultiIndex with 'action' column
print(result[['action']])
```

### Advanced Usage

```python
# Custom zone loader
custom_zone_loader = ZoneLoader(zones_file_path='custom/path/to/zones.mqh')
strategy = VectorizedXauUsdStrategy(custom_zone_loader)

# Preload specific days
result = strategy.process_tick_data(tick_data, preload_days=['2026-09-18', '2026-09-19'])
```

## MT5 Alignment

### Bar Period

The implementation uses **15-minute bars (PERIOD_M15)** as specified in the MT5 source. This is a critical correction from the original documentation which incorrectly assumed 1-minute bars.

### Key MT5 Correspondences

| MT5 Function | Python Equivalent | Vectorized Implementation |
|-------------|------------------|-------------------------|
| `ProcessCurrentEventLoopTick` | `process_current_event_loop_tick` | `_process_group` |
| `InitializeCurrentEventLoop` | `initialize_current_event_loop` | `_process_day_boundaries` |
| `CloseCoordinatorBar` | `close_coordinator_bar` | `_close_bar` |
| `BeginCoordinatorBar` | `begin_coordinator_bar` | `_begin_bar` |
| `ProcessCoordinatorTick` | `process_coordinator_tick` | `_process_tick_operations` |
| `LoadGeneratedRawZones` | `load_raw_zones` | `ZoneLoader.load_zones_for_day` |
| `BuildMergedZones` | `build_merged_zones` | `ZoneLoader.load_zones_for_day` |

### State Mapping

The vectorized implementation maps MT5 state variables to DataFrame columns:

| MT5 Variable | DataFrame Column | Description |
|-------------|------------------|-------------|
| `g_market_state.broker_day` | `broker_day` | Current broker day |
| `g_current_bar_time` | `bar_time` | 15-minute bar timestamp |
| `g_market_state.trend.trend` | `trend` | Current trend (UP/DOWN/NONE) |
| `g_market_state.trend.count` | `trend_count` | Number of trend candles recorded |
| `g_market_state.bar_active` | `bar_active` | Whether bar processing is active |
| `g_market_state.zones[].buy_engaged` | `buy_engaged` | Zone buy engagement state |
| `g_market_state.zones[].sell_engaged` | `sell_engaged` | Zone sell engagement state |

See `docs/todo/State-Variables.Glossary.csv` for complete state mapping.

## Vectorization Strategy

### Day Boundary Processing

Uses vectorized groupby operations to detect day changes and reinitialize state:

```python
day_changed = state["broker_day"] != state["broker_day"].shift(1)
state["day_group"] = day_changed.cumsum()
for day_group_id, day_group in state.groupby("day_group"):
    # Reinitialize state for new day
```

### Bar Boundary Processing

Uses vectorized groupby operations to detect 15-minute bar changes:

```python
bar_changed = state["bar_time"] != state["bar_time"].shift(1)
state["bar_group"] = bar_changed.cumsum()
for bar_group_id, bar_group in state.groupby("bar_group"):
    # Close previous bar, begin new bar
```

### Trend Calculation

Uses vectorized operations to compute trend updates:

```python
# Vectorized reference calculation
state["reference_high"] = state.apply(compute_reference_high, axis=1)
state["reference_low"] = state.apply(compute_reference_low, axis=1)

# Vectorized trend update
state.loc[has_reference, "trend"] = np.where(
    state.loc[has_reference, "bid"] > state.loc[has_reference, "reference_high"],
    XauTrend.UP.value,
    np.where(
        state.loc[has_reference, "bid"] < state.loc[has_reference, "reference_low"],
        XauTrend.DOWN.value,
        state.loc[has_reference, "trend"]
    )
)
```

### Zone Engagement

Uses vectorized boundary cross detection:

```python
# Vectorized cross counting
crosses = self._count_directional_crosses_vectorized(zones, previous_bid, current_bid)
state["multi_zone_tick_gap"] = crosses > 1

# Vectorized engagement update
buy_cross = (~state["buy_engaged"]) & (previous_bid < zone.low) & (current_bid >= zone.low)
state.loc[buy_cross, "buy_engaged"] = True
```

## Testing and Validation

### Deferred Validation

As specified in the vectorization plan, comprehensive correctness validation is deferred until the implementation is fully operational. The validation will include:

1. **Reference Comparison**: Run both implementations against the same deterministic input
2. **Numerical Comparison**: Define explicit numerical comparison rules with tolerances
3. **Edge Cases**: Test boundary conditions, empty input, duplicate timestamps
4. **Regression Tests**: Create tests to prevent behavioral divergence

### Current Status

The implementation provides the framework and structure for vectorized processing. Additional work is needed to:

1. Complete the signal generation logic with proper state management
2. Implement risk management filters
3. Add comprehensive testing
4. Optimize performance for large datasets

## Dependencies

- pandas
- numpy
- domain.xau_usd (shared domain models and enums)

## Performance Considerations

The vectorized implementation is designed for performance:

- **Grouped Operations**: Uses pandas groupby for independent (broker, symbol) processing
- **Vectorized Calculations**: Avoids Python-level per-tick loops
- **Caching**: Zone loader includes caching for repeated day lookups
- **Memory Efficiency**: Single _temp_state DataFrame avoids unnecessary copying

## Future Work

1. Complete signal generation with proper state management
2. Implement comprehensive testing and validation
3. Add performance benchmarks
4. Optimize for large-scale datasets
5. Add support for multiple brokers and symbols
6. Implement historical bar data loading for trend history initialization

## References

- MT5 Source: `mt5/XAUUSD_MVP.mq5`
- Python Reference: `src/application/xauusd_trading_strategy_1/`
- Vectorization Plan: `docs/todo/Vectorization Implementation Plan.md`
- State Glossary: `docs/todo/State-Variables.Glossary.csv`
- Divergence Report: `docs/todo/Divergence Report - MT5 vs Python vs Documentation.md`