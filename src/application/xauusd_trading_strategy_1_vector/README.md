# Vectorized XAUUSD Trading Strategy Implementation

## Overview

This directory contains a vectorized implementation of the XAUUSD trading strategy using pandas DataFrames and vectorized operations. The implementation follows the MT5 source of truth (`mt5/XAUUSD_MVP.mq5`) and uses 15-minute bars (PERIOD_M15) for all bar-based calculations.

## Pullback candidate generation

`generate_pullback_signals` consumes `pullback_windows_opened` events in chronological order within each broker/symbol stream. A window starts at offset 1 and expires after five observed bars or a broker-day change. Active zone/direction windows retain their original parent. The shared scalar evaluator latches 0.20 USD penetration and emits `PENDING_STOP` candidates at the broken edge, with IDs `<parent>:PB<sequence>`. Trend flips do not cancel windows. Input window objects are copied, so replay is repeatable.

The optional `pullback_feedback` column contains tuples of `PullbackFeedback(zone_id, direction, daily_fills, pending_active, filled=False)` execution snapshots applied before that tick's evaluation. `daily_fills` is the cumulative broker-day zone count across both directions and must not decrease; `pending_active` applies to that zone/direction. `filled=True` clears its penetration latch. Snapshots persist until updated or day rollover; an empty tuple means no update. Without this column, generation assumes zero fills and no accepted pending orders and can emit retry candidates on successive ticks. Normal zones stop after one fill; High zones have no daily cap. Candidate emission never consumes a fill.

Outputs include tuple-valued `pullback_signals`, aggregate `pullback_penetration_latched`, and the sum of candidate sequences for currently active windows in `pullback_sequence`. This completes candidate generation only: the action/execution layer must supply feedback and apply entry/risk gates; it remains a separate placeholder. A row loop preserves causal fill, pending and penetration state while DataFrame output assignment is batched.

## Complete Strategy Flow

The vectorized strategy processes data through the following sequence:

1. **Input Data Loading**: Load tick data, 15-minute candles, and zone data
2. **Zone Initialization**: Load and cache zones for relevant trading days
3. **Strategy Initialization**: Initialize the vectorized strategy with zone loader
4. **Day Boundary Processing**: Detect day changes and reinitialize state
5. **Bar Boundary Processing**: Detect 15-minute bar changes, close previous bar, begin new bar
6. **Tick-Level Processing**: Update trend, zone engagement, and generate signals
7. **Signal Generation**: Generate breakout, reversal, and pullback signals
8. **Order Management**: Generate order lifecycle tracking columns
9. **Position Tracking**: Generate position lifecycle tracking columns
10. **Result Output**: Save final results with all computed columns

## Architecture

### Core Components

- **`__main__.py`**: Main entry point that orchestrates the complete strategy flow
- **`the_strategy.py`**: Main strategy implementation that processes tick data using vectorized pandas operations
- **`zone_loader.py`**: Zone data loading and management, corresponding to MT5's `LoadGeneratedRawZones`

### Key Design Principles

1. **Vectorized Operations**: Uses pandas/numpy for bulk transforms; pullback execution feedback requires sequential state replay
2. **MultiIndex Structure**: Maintains the input DataFrame structure with MultiIndex (broker, symbol, datetime, date)
3. **State Management**: Represents persistent state as DataFrame columns where appropriate
4. **Group Independence**: Processes each (broker, symbol) group independently
5. **MT5 Alignment**: Follows the exact semantics of the MT5 implementation

## Input Data Requirements

### Tick Data (Required)

**Format**: CSV file or pandas DataFrame

**Required Columns**:

- `broker`: Broker identifier (string)
- `symbol`: Symbol identifier (string, e.g., "XAUUSD")
- `datetime`: UTC timezone-aware timestamp with millisecond precision
- `bid`: Current bid price (float)
- `ask`: Current ask price (float)

**MultiIndex Structure**: (broker, symbol, datetime, date)

**Example CSV Format**:

```csv
broker,symbol,datetime,bid,ask
MT5,XAUUSD,2026-09-18T00:00:00Z,2000.0,2000.5
MT5,XAUUSD,2026-09-18T00:00:01Z,2000.1,2000.6
```

**Sample Data Generation**:

```python
from application.xauusd_trading_strategy_1_vector.__main__ import create_sample_tick_data

tick_data = create_sample_tick_data(
    broker="MT5",
    symbol="XAUUSD",
    start_time="2026-09-18 00:00:00",
    end_time="2026-09-18 23:59:59",
    tick_interval_seconds=60,
)
```

### 15-Minute Candle Data (Required)

**Format**: CSV file or pandas DataFrame

**Required Columns**:

- `broker`: Broker identifier (string)
- `symbol`: Symbol identifier (string)
- `datetime`: UTC timezone-aware timestamp for 15-minute bar
- `open`: Opening price (float)
- `high`: High price (float)
- `low`: Low price (float)
- `close`: Closing price (float)
- `close_ask`: Closing ask price (float)

**Example CSV Format**:

```csv
broker,symbol,datetime,open,high,low,close,close_ask
MT5,XAUUSD,2026-09-18T00:00:00Z,2000.0,2005.0,1995.0,2002.0,2002.5
MT5,XAUUSD,2026-09-18T00:15:00Z,2002.0,2008.0,2000.0,2005.0,2005.5
```

**Sample Data Generation**:

```python
from application.xauusd_trading_strategy_1_vector.__main__ import create_sample_15min_candles

candle_data = create_sample_15min_candles(tick_data)
```

### Zone Data (Required)

**Format**: CSV file or dictionary mapping broker_day to list of XauZone objects

**Required Columns**:

- `broker_day`: Day in format "YYYY-MM-DD" (string)
- `zone_id`: Unique zone identifier (string)
- `low`: Zone low price (float)
- `high`: Zone high price (float)
- `priority`: Zone priority (int, 1 or 2)

**Example CSV Format**:

```csv
broker_day,zone_id,low,high,priority
2026-09-18,2026-09-18:R1,1990.0,1995.0,1
2026-09-18,2026-09-18:R2,1995.0,2000.0,1
2026-09-18,2026-09-18:R3,2000.0,2005.0,1
```

**Sample Data Generation**:

```python
from application.xauusd_trading_strategy_1_vector.__main__ import create_sample_zones

zones_dict = {"2026-09-18": create_sample_zones("2026-09-18")}
```

## Output Data Structure

### Final Result DataFrame

The output DataFrame maintains the same MultiIndex as the input (broker, symbol, datetime, date) and includes the following column categories:

### Input Columns (Preserved)

- `bid`: Current bid price (float)
- `ask`: Current ask price (float)

### Derived Time Columns

- `bar_time`: 15-minute bar timestamp (datetime)
- `broker_day`: Trading day in format "YYYY-MM-DD" (string)

### Trend State Columns

- `trend`: Current trend (int: 0=NONE, 1=UP, 2=DOWN)
- `trend_count`: Number of trend candles recorded (int: 0..`TREND_POINTS_N`)
- `trend_high_<i>`: `i`-th most recent bar high in the trend window, `i` in `0..TREND_POINTS_N-1` (float)
- `trend_low_<i>`: `i`-th most recent bar low in the trend window, `i` in `0..TREND_POINTS_N-1` (float)

`TREND_POINTS_N` lives in `config/trend_points.py` and sizes every trend high/low definition, usage and
validation point, so the trend window is resized by changing that single setting.

### Bar State Columns

- `bar_open`: Opening bid price of current bar (float)
- `bar_active`: Whether bar processing is active (bool)
- `day_active`: Whether day initialization is complete (bool)

### Zone Engagement Columns

- `buy_engaged`: Whether price is in zone for buy signals (bool)
- `sell_engaged`: Whether price is in zone for sell signals (bool)

### Signal Generation Columns

- `breakout_sequence`: Daily sequence number for breakout IDs (int)
- `reversal_keys`: String tracking reversal uniqueness per bar (string)
- `attempted_bars`: List of bar IDs where entry was attempted (string)

### Pullback Window Columns

- `pullback_active`: Whether pullback window is active (bool)
- `pullback_bar_offset`: Number of bars since breakout (int: 0-5)
- `pullback_penetration_latched`: Whether price has penetrated zone (bool)
- `pullback_sequence`: Sequence number for pullback signals (int)

### Intermediate Calculation Columns

- `reference_high`: Reference high from trend history (float)
- `reference_low`: Reference low from trend history (float)
- `multi_zone_tick_gap`: Whether tick crossed multiple zones (bool)

### Signal Columns

- `action`: Trading action signal (object/dict, None if no action)
- `reversal_signals`: Reversal signal candidates (object/dict)
- `pullback_signals`: Pullback signal candidates (object/dict)

### Candle Data Columns (Merged)

- `open`: 15-minute bar open price (float)
- `high`: 15-minute bar high price (float)
- `low`: 15-minute bar low price (float)
- `close`: 15-minute bar close price (float)
- `close_ask`: 15-minute bar close ask price (float)

### Order Management Columns

- `order_id`: Unique identifier for each order (string, format: "ORD-XXXXXX")
- `order_type`: Type of order (string: "MARKET", "PENDING_STOP", etc.)
- `order_direction`: Direction of order (string: "BUY", "SELL")
- `order_status`: Status of order (string: "PENDING", "FILLED", "CANCELLED", etc.)
- `entry_price`: Entry price for the order (float)
- `stop_loss`: Stop loss price (float)
- `take_profit`: Take profit price (float)
- `order_time`: Time when order was created (datetime)

### Position Tracking Columns

- `position_id`: Unique identifier for each position (string, format: "POS-XXXXXX")
- `position_direction`: Direction of position (string: "LONG", "SHORT")
- `position_size`: Size of position in lots (float)
- `position_entry_price`: Entry price for the position (float)
- `position_current_price`: Current market price (float)
- `position_unrealized_pnl`: Unrealized profit/loss (float)
- `position_status`: Status of position (string: "OPEN", "CLOSED", etc.)
- `position_time`: Time when position was opened (datetime)

## Signal, Order, and Position Management

### Signal Generation

The strategy generates three types of signals:

1. **Breakout Signals**: Generated at 15-minute bar close when price breaks through zone boundaries in trend direction
2. **Reversal Signals**: Generated during bar when price touches zone boundary against current trend
3. **Pullback Signals**: Generated during bar from active pullback windows after penetration

**Signal Format**:

```python
{
    "signal_id": str,  # Unique signal identifier
    "signal_type": str,  # 'BREAKOUT', 'REVERSAL', 'PULLBACK'
    "direction": str,  # 'BUY', 'SELL'
    "entry_price": float,  # Suggested entry price
    "zone_id": str,  # Associated zone
    "bar_id": str,  # Bar identifier
    "signal_time": datetime,  # Signal generation time
}
```

### Order Lifecycle Management

Orders are generated from signal candidates and tracked through their lifecycle:

**Order States**:

1. **PENDING**: Order submitted but not yet filled
2. **FILLED**: Order filled at market
3. **CANCELLED**: Order cancelled before fill
4. **REJECTED**: Order rejected by broker
5. **EXPIRED**: Order expired without fill

**Order Types**:

- **MARKET**: Immediate execution at current price (breakouts, reversals)
- **PENDING_STOP**: Stop order to enter on price penetration (pullbacks)

**Order Management Flow**:

```
Signal → Risk Check → Order Creation → Order Submission → Order Fill/Reject → Position Opening
```

### Position Lifecycle Management

Positions are opened when orders are filled and tracked through their lifecycle:

**Position States**:

1. **OPEN**: Position is currently active
2. **CLOSED**: Position has been closed
3. **PARTIALLY_CLOSED**: Position partially closed

**Position Tracking**:

- Entry price and size
- Current market price
- Unrealized PnL calculation
- Stop loss and take profit management
- Position closing conditions

**Position Management Flow**:

```
Order Fill → Position Opening → Price Tracking → PnL Calculation → SL/TP Management → Position Closing
```

## Usage

### Command Line Interface

The vectorized strategy provides a comprehensive command-line interface for execution:

### Basic Commands

#### Run with Sample Data

```bash
python -m application.xauusd_trading_strategy_1_vector --sample
```

#### Run with Custom Data Files

```bash
python -m application.xauusd_trading_strategy_1_vector \
    --ticks data/ticks.csv \
    --candles data/candles.csv \
    --zones data/zones.csv \
    --output results/output.csv
```

#### Run with Custom Parameters

```bash
python -m application.xauusd_trading_strategy_1_vector --sample \
    --start-time "2026-09-18 00:00:00" \
    --end-time "2026-09-18 23:59:59" \
    --tick-interval 60 \
    --output results/custom_output.csv \
    --format parquet
```

#### Run in Debug Mode

```bash
python -m application.xauusd_trading_strategy_1_vector --sample --debug
```

### Command-Line Options

| Option            | Description                                   | Default              |
| ----------------- | --------------------------------------------- | -------------------- |
| `--sample`        | Use sample data instead of loading from files | False                |
| `--ticks`         | Path to tick data CSV file                    | None                 |
| `--candles`       | Path to 15-minute candle data CSV file        | None                 |
| `--zones`         | Path to zones CSV file                        | None                 |
| `--output`        | Path to output file                           | strategy_results.csv |
| `--format`        | Output format (csv or parquet)                | csv                  |
| `--start-time`    | Start time for sample data                    | 2026-09-18 00:00:00  |
| `--end-time`      | End time for sample data                      | 2026-09-18 23:59:59  |
| `--tick-interval` | Tick interval in seconds for sample data      | 60                   |
| `--debug`         | Enable debug mode and return strategy objects | False                |

### Debug Mode

Debug mode provides additional functionality for testing and inspection:

- Returns strategy and zone loader objects for inspection
- Provides access to internal state via helper functions
- Enables detailed logging of strategy execution
- Useful for understanding internal processing and debugging

**Debug Helper Functions**:

- `get_strategy_internal_state(strategy)` - Access internal \_per_tick_temp_state DataFrame
- `get_zone_loader_cache(zone_loader)` - Access cached zones
- `clear_zone_loader_cache(zone_loader)` - Clear zone cache

### Programmatic Usage

```python
from application.xauusd_trading_strategy_1_vector import VectorizedXauUsdStrategy, ZoneCache, run_vectorized_strategy
from application.xauusd_trading_strategy_1_vector.__main__ import (
    create_sample_tick_data,
    create_sample_15min_candles,
    create_sample_zones,
)

# Create sample data
tick_data = create_sample_tick_data(
    broker="MT5",
    symbol="XAUUSD",
    start_time="2026-09-18 00:00:00",
    end_time="2026-09-18 23:59:59",
    tick_interval_seconds=60,
)

candle_data = create_sample_15min_candles(tick_data)
zones_dict = {"2026-09-18": create_sample_zones()}

# Run the complete strategy flow
result = run_vectorized_strategy(tick_data=tick_data, candle_data=candle_data, zones_dict=zones_dict)

# Result includes all computed columns
print(result.columns)
print(result.head())
```

### Debug Mode Usage

```python
from application.xauusd_trading_strategy_1_vector.__main__ import (
    run_strategy_with_debug,
    get_strategy_internal_state,
    get_zone_loader_cache,
    create_sample_tick_data,
    create_sample_15min_candles,
    create_sample_zones,
)

# Create sample data
tick_data = create_sample_tick_data()
candle_data = create_sample_15min_candles(tick_data)
zones_dict = {"2026-09-18": create_sample_zones()}

# Run strategy in debug mode
result, strategy, zone_loader = run_strategy_with_debug(
    tick_data=tick_data, candle_data=candle_data, zones_dict=zones_dict, debug=True
)

# Access internal state for inspection
per_tick_state = get_strategy_internal_state(strategy)
cached_zones = get_zone_loader_cache(zone_loader)

print(f"Internal state columns: {per_tick_state.columns.tolist()}")
print(f"Cached zones: {list(cached_zones.keys())}")
```

### Advanced Usage

```python
# Custom zone loader
custom_zone_loader = ZoneLoader(zones_file_path="custom/path/to/zones.mqh")
strategy = VectorizedXauUsdStrategy(zone_loader=custom_zone_loader)

# Preload specific days
result = strategy.process_tick_data(tick_data, candle_df)
```

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
- ✅ \_per_tick_temp_state DataFrame schema and processing pipeline
- ✅ Complete strategy flow orchestration (**main**.py)
- ✅ Order management column generation
- ✅ Position tracking column generation
- ✅ Sample data generation functions
- ✅ File I/O for ticks, candles, and zones

### Framework Components (Placeholder)

The following components have the framework implemented but require additional logic for full functionality:

- ⚠️ Breakout signal generation (needs zone state management)
- ⚠️ Reversal signal generation (needs reversal key tracking)
- ⚠️ Pullback signal generation (needs pullback window state management)
- ⚠️ Final action column generation (needs signal candidate collection and risk management)

## MT5 Alignment

### Bar Period

The implementation uses **15-minute bars (PERIOD_M15)** as specified in the MT5 source. This is a critical correction from the original documentation which incorrectly assumed 1-minute bars.

### Key MT5 Correspondences

| MT5 Function                  | Python Equivalent                 | Vectorized Implementation       |
| ----------------------------- | --------------------------------- | ------------------------------- |
| `ProcessCurrentEventLoopTick` | `process_current_event_loop_tick` | `_process_group`                |
| `InitializeCurrentEventLoop`  | `initialize_current_event_loop`   | `_process_day_boundaries`       |
| `CloseCoordinatorBar`         | `close_coordinator_bar`           | `_close_bar`                    |
| `BeginCoordinatorBar`         | `begin_coordinator_bar`           | `_begin_bar`                    |
| `ProcessCoordinatorTick`      | `process_coordinator_tick`        | `_process_tick_operations`      |
| `LoadGeneratedRawZones`       | `load_raw_zones`                  | `ZoneLoader.load_zones_for_day` |
| `BuildMergedZones`            | `build_merged_zones`              | `ZoneLoader.load_zones_for_day` |

### State Mapping

The vectorized implementation maps MT5 state variables to DataFrame columns:

| MT5 Variable                          | DataFrame Column | Description                      |
| ------------------------------------- | ---------------- | -------------------------------- |
| `g_market_state.broker_day`           | `broker_day`     | Current broker day               |
| `g_current_bar_time`                  | `bar_time`       | 15-minute bar timestamp          |
| `g_market_state.trend.trend`          | `trend`          | Current trend (UP/DOWN/NONE)     |
| `g_market_state.trend.count`          | `trend_count`    | Number of trend candles recorded |
| `g_market_state.bar_active`           | `bar_active`     | Whether bar processing is active |
| `g_market_state.zones[].buy_engaged`  | `buy_engaged`    | Zone buy engagement state        |
| `g_market_state.zones[].sell_engaged` | `sell_engaged`   | Zone sell engagement state       |

See `docs/todo/State-Variables.Glossary.csv` for complete state mapping.

## Vectorization Strategy

Python loops are limited to broker/symbol/day partitions and zone metadata. No bar-group iteration, tick-row iteration, row-wise `apply`, or per-order/per-position assignment loops remain in the calculation path.

- Aggregate observed M15 bars once per day; gather the preceding 1/2/3 closed bars into tick rows with NumPy indexing. The current bar never enters its own references; missing bars are not fabricated.
- Update trend from strict reference crossings, then forward-fill within the broker day. The first observed bar starts at `NONE`; no trend crosses midnight.
- Compute zone crossings with masks and latch engagement using grouped `cummax`, resetting at each bar open. Aggregate engagement columns do not replace the future per-zone signal lifecycle.
- Generate order/position IDs with cumulative masks and string padding. Duplicate timestamps remain separate rows.
- Reject decreasing timestamps within a broker/symbol; preserve duplicate-tick order. Calendar-day boundaries still use the input timestamp timezone; broker timezone conversion is not introduced here.

## Testing and Validation

### Verified State Calculations

`tests/test_vectorized_state.py` covers scalar domain trend parity, 1/2/3-bar bootstrap, day and instrument isolation, gaps, duplicate timestamps, empty input, singleton bars, daily zone selection, engagement persistence, ID generation and future-data invariance. A regression guard rejects Python group iteration and row-wise `apply` in bar/trend processing.

On 2026-09-19, 100,000 synthetic one-second ticks took 0.607 s through the vector state pipeline versus 10.280 s for the scalar trend oracle (16.9x; exact trend/reference parity). This is one local measurement against the oracle, not a speedup claim against the previously broken pipeline or a trading-performance result.

Full signal/risk/lifecycle parity remains unverified. Actions remain placeholders.

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
- **State granularity**: `_per_tick_temp_state` holds tick rows; `_per_candle_temp_state` holds observed candle open/high/low and preceding-bar trend history, indexed by broker, symbol and bar time. Both reset per batch; candle history spans all processed days.

## Future Work

1. Complete signal generation with proper state management
2. Implement comprehensive testing and validation
3. Add performance benchmarks
4. Optimize for large-scale datasets
5. Add support for multiple brokers and symbols
6. Implement historical bar data loading for trend history initialization

## References

- MT5 Source: `mt5/XAUUSD_MVP.mq5`
- Python Reference: `../../../archive_not_used_trash/xauusd_trading_strategy_1/`
- Vectorization Plan: `docs/todo/Vectorization Implementation Plan.md`
- State Glossary: `docs/todo/State-Variables.Glossary.csv`
- Divergence Report: `docs/todo/Divergence Report - MT5 vs Python vs Documentation.md`

`process_tick_data` requires the preloaded M15 `candle_15min_df`; the runner forwards the entry point's loaded candles. Bar processing never reconstructs OHLC from ticks. The current MT5 loader fetches directly; this interface does not add persistent caching.
