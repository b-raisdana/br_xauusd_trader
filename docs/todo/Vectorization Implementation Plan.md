# Vectorization Implementation Plan

## Overview

**Objective**: Convert the event-loop-based XAUUSD trading strategy into a vectorized DataFrame implementation.

**Primary source of truth**: `mt5/XAUUSD_MVP.mq5` (MT5 implementation)

**Secondary reference**: `src/application/xauusd_trading_strategy_1/on_tick.py` and `src/application/xauusd_trading_strategy_1/event_loop.py` (Python implementation)

**Target implementation**: `src/application/xauusd_trading_strategy_1_vector/`

**Scope restrictions**: This document is investigation and planning only. No implementation code will be created during this phase.

**Expected final output**: A pandas DataFrame with MultiIndex (broker, symbol, datetime, date) containing an `action` column with the same semantics as the MT5 implementation.

**Critical divergence note**: The original documentation incorrectly assumed 1-minute bars. The MT5 implementation uses **15-minute bars (PERIOD_M15)** for all bar-based calculations (trend history, bar close/open, breakout signals). This has been corrected throughout this document to match the MT5 source of truth.

---

## Current Algorithm

The strategy processes XAUUSD price ticks to generate trading signals (breakouts, reversals, pullbacks) based on predefined price zones and trend analysis. The algorithm operates on a per-tick basis with persistent state that tracks market conditions, zone engagement, and signal generation history.

### Core Components

**Zone-based signal generation**: The strategy uses predefined price zones (low-high ranges) to identify potential trading opportunities. Zones have priorities (1 or 2) that affect signal frequency.

**Trend tracking**: A 3-candle rolling window of highs and lows determines the current trend (UP, DOWN, or NONE). Trend influences which signals are valid.

**Three signal families**:
- **Breakout**: Price closes beyond a zone boundary in the direction of the trend
- **Reversal**: Price touches a zone boundary against the current trend
- **Pullback**: After a breakout, price penetrates back into the zone and then re-enters in the breakout direction

**Risk management**: Each signal includes stop-loss and take-profit levels derived from neighboring zones. Portfolio risk limits constrain position sizing and entry frequency.

---

## Execution Flow

### Tick Processing Sequence

```
Tick arrives (time, bid, ask)
    ↓
Check time_basis_probe emission (first 5 valid ticks if enabled)
    ↓
If event_loop not ready:
    Initialize event loop:
        - Load raw zones for broker_day
        - Merge overlapping zones
        - Initialize daily zone states
        - Load trend history (previous candles)
        - Initialize trend state
        - Begin first bar
        - Set event_loop_ready = True
    ↓
Check day boundary:
    If tick.time.day != runtime.market_state.broker_day:
        Set event_loop_ready = False
        Reinitialize event loop (as above)
    ↓
Check bar boundary:
    If bar_time != runtime.current_bar_time:
        Close previous bar:
            - Generate breakout signals from engaged zones
            - Create pullback windows for new breakouts
            - Record trend candle
            - Set bar_active = False
        Begin new bar:
            - Advance pullback window offsets
            - Cancel expired pullback windows
            - Reset zone engagement based on bar open
            - Set bar_active = True
            - Update current_bar_time
    ↓
Execute operational safety checks (ports.execute_operational_safety)
    ↓
Manage pullback take-profit modifications (ports.manage_pullback_tp)
    ↓
Manage profit protection trailing stops (ports.manage_profit_protection)
    ↓
Close opposite reversal positions (ports.close_opposite_reversals)
    ↓
Process pending candidates from previous bar close (ports.process_candidates)
    ↓
Process coordinator tick:
    - Update trend based on current bid
    - Update zone engagement based on bid movement
    - Generate reversal signals on zone touches
    - Generate pullback signals from active windows
    - Update last_bid, last_ask
    ↓
Process new candidates from coordinator tick (ports.process_candidates)
    ↓
Update candidate counters (breakout, reversal, pullback)
    ↓
Return success/failure
```

**Note**: This execution flow matches the MT5 implementation in `mt5/XAUUSD_MVP.mq5::ProcessCurrentEventLoopTick` (lines 1248-1335). The Python implementation in `src/application/xauusd_trading_strategy_1/event_loop.py::process_current_event_loop_tick` (lines 163-235) follows the same sequence.

### Key Decision Points

**Day boundary**: When the broker day changes, all state is reinitialized. This includes zones, trend history, and all counters.

**Bar boundary**: When the 15-minute bar changes (bar_time), the previous bar is closed and a new bar begins. This is when breakout signals are generated and pullback windows are created. **Note**: The MT5 implementation uses PERIOD_M15 (15-minute bars), not 1-minute bars as might be assumed.

**Zone engagement**: A zone becomes engaged when price enters its range. Engagement is required for breakout signals and is reset at each bar open.

**Reversal uniqueness**: Each (bar_id, zone_id, direction) combination can generate at most one reversal signal per bar, tracked via reversal_keys.

**Pullback window lifecycle**: Pullback windows are created on bar close when a breakout occurs. They remain active for 5 bars (bar_offset 1-5). Each window can generate multiple pullback signals (sequence incrementing).

---

## State Model

### StrategyRuntimeState

**Global strategy-level state** (not broker/symbol-specific):

- `time_basis_probe_count`: Counter for first 5 probe emissions
- `execution_projections`: List of XauExecutionProjection tracking order lifecycle
- `execution_bindings`: 6y6yList of XauExecutionBinding mapping request_id to order_ticket/position_id
- `runtime_requests`: List of XauRuntimeRequest for pending orders
- `execution_bindings_file`: Path to persistent bindings file
- `order_audit_file`: Path to order audit log
- `market_state`: XauMarketCoordinator (contains the core algorithmic state)
- `current_bar_time`: Unix timestamp of current bar (minute-level)
- `event_loop_ready`: Boolean flag indicating initialization complete
- `event_loop_failure_reported`: Boolean flag for error reporting
- `breakout_candidate_count`: Counter for breakout signals generated
- `reversal_candidate_count`: Counter for reversal signals generated
- `pullback_candidate_count`: Counter for pullback signals generated
- `tester_attempt_count`: Counter for tester execution attempts
- `tester_accept_count`: Counter for accepted tester orders
- `tester_reject_count`: Counter for rejected tester orders
- `request_sequence`: Sequence number for request IDs
- `event_sequence`: Sequence number for events
- `daily_loss_locked`: Boolean flag for daily loss limit
- `operational_lock`: Boolean flag for operational safety
- `session_cancel_count`: Counter for session cancellations
- `session_close_count`: Counter for session closes
- `session_zero_exposure`: Boolean flag for session flattening
- `restart_lock`: Boolean flag for same-day restart simulation
- `max_open_positions`: Maximum allowed positions (from capital)
- `gate_rejections`: Array of 8 counters for rejection reasons
- `final_net_realized`: Final net realized PnL
- `final_gross_loss`: Final gross loss
- `invalid_price_rejections`: Counter for invalid price rejections
- `other_broker_rejections`: Counter for other broker rejections
- `protection_modifies`: Counter for protection modifications
- `protection_modify_rejects`: Counter for protection modification rejections
- `sl_loosen_violations`: Counter for SL loosen violations
- `tp_extensions`: Counter for TP extensions
- `tp_restores`: Counter for TP restores
- `tp_market_closes`: Counter for TP market closes
- `tp_modify_rejects`: Counter for TP modify rejections
- `tp_close_rejects`: Counter for TP close rejections
- `breakout_conflict_closes`: Counter for breakout conflict closes
- `symbol_spec_emitted`: Boolean flag for symbol spec emission
- `attribution_attempts`: Array of 6 counters for attribution attempts
- `attribution_accepts`: Array of 6 counters for attribution accepts
- `attribution_rejects`: Array of 6 counters for attribution rejects

**Reset behavior**: Most counters are cumulative across the session. `event_loop_ready` is reset on day boundary. `daily_loss_locked` is set when loss limit is hit and persists.

### XauMarketCoordinator

**Core algorithmic state** (conceptually per-broker, per-symbol):

- `broker_day`: String in format "YYYY.MM.DD"
- `bar_id`: String identifier for current bar (format "YYYY-MM-DDTHH:MM")
- `day_active`: Boolean indicating day initialization complete
- `bar_active`: Boolean indicating bar processing active
- `bar_open`: Opening bid price of current bar
- `last_bid`: Last processed bidPrice (previous tick)
- `last_ask`: Last processed ask price (previous tick)
- `breakout_sequence`: Daily sequence number for breakout IDs
- `trend`: XauTrendReferenceState (trend tracking state)
- `zones`: List of XauDailyZoneSignalState (one per zone)
- `pullbacks`: List of XauPullbackWindowState (active pullback windows)
- `reversal_keys`: List of strings tracking reversal uniqueness per bar
- `attempted_bars`: List of bar_ids where entry was attempted

**Reset behavior**: Reinitialized at day start. All fields reset to initial values.

### XauTrendReferenceState

- `trend`: Current trend (NONE, UP, DOWN)
- `count`: Number of candles recorded (0-3, then rolling)
- `highs`: Array of 3 high prices (rolling window)
- `lows`: Array of 3 low prices (rolling window)

**Reset behavior**: Reinitialized at day start. Count increments to 3, then highs/lows roll.

### XauDailyZoneSignalState (per zone)

- `zone`: XauZone (id, low, high, priority)
- `buy_engaged`: Boolean indicating price is in zone for buy signals
- `sell_engaged`: Boolean indicating price is in zone for sell signals
- `reversal_usage`: Counter for reversal signals used (limit: 2 for priority 1, 1 for priority 2)
- `pullback_fills`: Counter for pullback fills (affects usage allowance)

**Reset behavior**: Reinitialized at day start. Engagement reset at each bar open. Reversal_usage and pullback_fills accumulate during the day.

### XauPullbackWindowState (per active pullback)

- `parent_breakout_id`: ID of the breakout that created this window
- `zone`: XauZone associated with this pullback
- `direction`: XauDirection (BUY or SELL)
- `bar_offset`: Number of bars since breakout (0-5, active 1-5)
- `active`: Boolean indicating window is within valid range
- `penetration_latched`: Boolean indicating price has penetrated zone
- `pending_active`: Boolean indicating pending order is active
- `sequence`: Sequence number for pullback signals from this window

**Reset behavior**: Created on bar close when breakout occurs. Becomes inactive after bar_offset > 5. Removed from list when inactive.

---

## Input Model

### Expected DataFrame Structure

**MultiIndex levels**:
- `broker`: Broker identifier (string)
- `symbol`: Symbol identifier (string, e.g., "XAUUSD")
- `datetime`: UTC timezone-aware timestamp with millisecond precision
- `date`: datetime floored to seconds (for grouping)

**Required columns**:
- `bid`: Current bid price (float)
- `ask`: Current ask price (float)

### Time Semantics

**bar_time**: Derived from datetime by flooring to 15-minute level (minute % 15 = 0, second=0, microsecond=0). Used for bar boundary detection. **Note**: The MT5 implementation uses PERIOD_M15 (15-minute bars), not 1-minute bars.

**Day boundary**: Detected when broker_day (from datetime) changes. Triggers full reinitialization.

**Bar boundary**: Detected when bar_time changes. Triggers bar close and new bar begin.

**Duplicate timestamps**: Valid and expected. Each row represents a distinct event even with identical timestamps. Relative order matters for state updates.

**Ordering assumptions**: DataFrame must be sorted by (broker, symbol, datetime). Within the same timestamp, row order is preserved and matters for sequential state updates.

---

## Calculation Inventory

### Trend Calculation

**Source**: `domain/xau_usd/state.py::process_trend_tick`, `domain/xau_usd/zone.py::update_trend`

**Inputs**: Current bid, reference_high, reference_low (from last 3 candles)

**Previous state**: trend, count, highs[0-2], lows[0-2]

**Calculation**: 
- If bid > reference_high: trend = UP
- If bid < reference_low: trend = DOWN
- Else: trend unchanged

**Updated state**: trend (may change)

**Output**: Used in breakout_valid and reversal_directional_touch

**Vectorization candidate**: Yes - can use rolling window and comparison

**Dependency**: Sequential - trend depends on previous trend state

### Reference High/Low Calculation

**Source**: `domain/xau_usd/state.py::trend_references`

**Inputs**: highs[0:count], lows[0:count]

**Previous state**: count, highs array, lows array

**Calculation**: 
- reference_high = max(highs[:count])
- reference_low = min(lows[:count])

**Updated state**: None (read-only)

**Output**: Used in trend calculation

**Vectorization candidate**: Yes - can use expanding().max() and expanding().min()

**Dependency**: Sequential - arrays roll after 3 candles

### Candle Recording

**Source**: `domain/xau_usd/state.py::record_trend_candle`

**Inputs**: high, low (from bar close)

**Previous state**: count, highs array, lows array

**Calculation**:
- If count < 3: Append to array, increment count
- Else: Roll arrays (shift left, append new)

**Updated state**: count, highs, lows

**Output**: None

**Vectorization candidate**: Partially - can use shift for rolling, but initialization phase is sequential

**Dependency**: Sequential - array management

### Zone Engagement Update

**Source**: `domain/xau_usd/state.py::update_zone_engagement`

**Inputs**: previous_bid, current_bid, zone boundaries

**Previous state**: buy_engaged, sell_engaged per zone

**Calculation**:
- Count directional zone crosses (previous_bid to current_bid)
- If multi-zone tick gap (>1 cross): Set engagement based on current_bid position
- Else: Update engagement incrementally based on boundary crosses

**Updated state**: buy_engaged, sell_engaged per zone

**Output**: Used in breakout_valid

**Vectorization candidate**: Yes - can use vectorized boundary comparisons

**Dependency**: Sequential - depends on previous engagement state

### Breakout Validation

**Source**: `domain/xau_usd/zone.py::breakout_valid`

**Inputs**: zone, direction, trend, close_price, engaged

**Previous state**: None (read-only)

**Calculation**:
- If not engaged: False
- If BUY direction: trend == UP and close_price > zone.high + BREAKOUT_BUFFER_USD
- If SELL direction: trend == DOWN and close_price < zone.low - BREAKOUT_BUFFER_USD

**Updated state**: None

**Output**: Boolean indicating valid breakout

**Vectorization candidate**: Yes - vectorized comparison

**Dependency**: None (stateless per tick)

### Reversal Directional Touch

**Source**: `domain/xau_usd/zone.py::reversal_directional_touch`

**Inputs**: zone, direction, trend, previous_bid, current_bid, multi_zone_tick_gap

**Previous state**: None (read-only)

**Calculation**:
- If multi_zone_tick_gap: False
- If SELL direction: trend == UP and previous_bid < zone.low and current_bid >= zone.low
- If BUY direction: trend == DOWN and previous_bid > zone.high and current_bid <= zone.high

**Updated state**: None

**Output**: Boolean indicating valid reversal touch

**Vectorization candidate**: Yes - vectorized comparison

**Dependency**: None (stateless per tick)

### Pullback Penetration Check

**Source**: `domain/xau_usd/zone.py::pullback_penetrated`

**Inputs**: zone, direction, bid

**Previous state**: None (read-only)

**Calculation**:
- entry_price = zone.high if BUY else zone.low
- If BUY: penetrated = bid <= zone.high - PULLBACK_PENETRATION_USD
- If SELL: penetrated = bid >= zone.low + PULLBACK_PENETRATION_USD

**Updated state**: None

**Output**: (penetrated: bool, entry_price: float)

**Vectorization candidate**: Yes - vectorized comparison

**Dependency**: None (stateless per tick)

### Pullback Window Active Check

**Source**: `domain/xau_usd/zone.py::pullback_window_active`

**Inputs**: bar_offset

**Previous state**: None (read-only)

**Calculation**: return 1 <= bar_offset <= 5

**Updated state**: None

**Output**: Boolean indicating window is in valid range

**Vectorization candidate**: Yes - vectorized comparison

**Dependency**: None (stateless per tick)

### Pullback Usage Allowed Check

**Source**: `domain/xau_usd/zone.py::pullback_usage_allowed`

**Inputs**: zone_priority, daily_fills

**Previous state**: None (read-only)

**Calculation**:
- If daily_fills < 0: False
- If zone_priority == 1: True
- Else: daily_fills < 1

**Updated state**: None

**Output**: Boolean indicating pullback usage is allowed

**Vectorization candidate**: Yes - vectorized comparison

**Dependency**: None (stateless per tick)

### Initial Stop Loss Calculation

**Source**: `domain/xau_usd/entry.py::initial_stop`

**Inputs**: direction, entry_price, zones list

**Previous state**: None (read-only)

**Calculation**:
- Find nearest zone boundary in opposite direction from entry
- For BUY: find zone with high < entry, max high
- For SELL: find zone with low > entry, min low
- stop_loss = max(nearest, entry - BASE_R_USD) for BUY
- stop_loss = min(nearest, entry + BASE_R_USD) for SELL

**Updated state**: None

**Output**: (found: bool, stop_loss: float | None, stop_zone_id: str | None)

**Vectorization candidate**: Yes - can use vectorized search

**Dependency**: None (stateless per tick)

### Initial Take Profit Calculation

**Source**: `domain/xau_usd/entry.py::initial_target`

**Inputs**: direction, entry_price, zones list

**Previous state**: None (read-only)

**Calculation**:
- Find nearest zone boundary in trade direction from entry
- For BUY: find zone with low > entry and low - entry >= BASE_R_USD, min low
- For SELL: find zone with high < entry and entry - high >= BASE_R_USD, max high

**Updated state**: None

**Output**: (found: bool, take_profit: float | None, target_zone_id: str | None)

**Vectorization candidate**: Yes - can use vectorized search

**Dependency**: None (stateless per tick)

### Portfolio Risk Check

**Source**: `domain/xau_usd/entry.py::portfolio_risk_allows`

**Inputs**: strategy_capital, realized_gross_loss, open_risk, pending_risk, proposed_risk

**Previous state**: None (read-only)

**Calculation**:
- budget = strategy_capital * GROSS_DAILY_RISK_FRACTION
- return realized_gross_loss + open_risk + pending_risk + proposed_risk <= budget + 1e-9

**Updated state**: None

**Output**: Boolean indicating portfolio risk allows entry

**Vectorization candidate**: Yes - vectorized comparison

**Dependency**: None (stateless per tick)

### Concurrency Check

**Source**: `domain/xau_usd/entry.py::concurrency_allows_entry`

**Inputs**: strategy_capital, open_positions

**Previous state**: None (read-only)

**Calculation**:
- maximum = 3 if capital == 200, 5 if capital == 300, else -1
- return maximum >= 0 and open_positions < maximum

**Updated state**: None

**Output**: Boolean indicating concurrency allows entry

**Vectorization candidate**: Yes - vectorized comparison

**Dependency**: None (stateless per tick)

---

## Vectorization Plan

### Trend and Reference Calculations

**Approach**: Use pandas rolling and expanding windows

**Implementation**:
- Create `bar_high` and `bar_low` columns from 15-minute bar close data
- Use `expanding().max()` and `expanding().min()` for reference_high/reference_low
- Use vectorized comparison for trend updates
- Handle the 3-candle initialization with cumulative count
- Load historical M15 bars for trend history initialization (as in MT5 CopyRates with PERIOD_M15)

**Grouping**: groupby(["broker", "symbol"])

**State columns**: `trend`, `reference_high`, `reference_low`, `trend_count`

**Dependencies**: Previous trend state (sequential)

### Zone Engagement

**Approach**: Vectorized boundary comparisons with previous bid

**Implementation**:
- Create `previous_bid` column using `shift(1)`
- For each zone, check if bid crossed zone.low or zone.high
- Count crosses per tick to detect multi-zone gaps
- Update engagement based on crosses and current position

**Grouping**: groupby(["broker", "symbol"])

**State columns**: `buy_engaged_zone_N`, `sell_engaged_zone_N` per zone

**Dependencies**: Previous engagement state (sequential)

### Breakout Signal Generation

**Approach**: Vectorized comparison at bar close

**Implementation**:
- Identify bar close rows (where bar_time changes)
- For each engaged zone, check breakout conditions
- Generate breakout candidates where conditions met

**Grouping**: groupby(["broker", "symbol"])

**State columns**: None (stateless per tick)

**Dependencies**: Engagement state, trend state

### Reversal Signal Generation

**Approach**: Vectorized comparison with previous bid

**Implementation**:
- Create `previous_bid` column
- For each zone and direction, check reversal touch conditions
- Track uniqueness using bar_id + zone_id + direction key
- Filter duplicates using reversal_keys tracking

**Grouping**: groupby(["broker", "symbol"])

**State columns**: `reversal_keys` (list accumulation)

**Dependencies**: Trend state, previous bid

### Pullback Window Management

**Approach**: Track windows as DataFrame rows with lifecycle columns

**Implementation**:
- Create pullback windows on bar close when breakout occurs
- Track `bar_offset`, `active`, `penetration_latched`, `pending_active`, `sequence`
- Increment bar_offset at each bar boundary
- Deactivate windows when bar_offset > 5
- Remove inactive windows

**Grouping**: groupby(["broker", "symbol"])

**State columns**: `pullback_windows` (list of window states)

**Dependencies**: Bar boundary events, breakout signals

### Pullback Signal Generation

**Approach**: Vectorized evaluation per active window

**Implementation**:
- For each active window, check penetration condition
- Check window active range (1 <= bar_offset <= 5)
- Check usage allowance based on zone priority and daily fills
- Generate pullback candidates when conditions met
- Increment sequence per window

**Grouping**: groupby(["broker", "symbol"])

**State columns**: `pullback_windows` (updated)

**Dependencies**: Pullback window state, bid price

### Risk Calculations

**Approach**: Vectorized search and comparison

**Implementation**:
- For stop loss: find nearest zone in opposite direction
- For take profit: find nearest zone in trade direction
- Check portfolio risk limits
- Check concurrency limits
- Check margin requirements

**Grouping**: groupby(["broker", "symbol"])

**State columns**: None (stateless per tick, depends on external risk state)

**Dependencies**: None (stateless per tick)

---

## Sequential Dependency Report

### Trend State Update

**Why sequential**: Trend depends on previous trend value and the comparison logic is stateful (trend persists until reference is crossed).

**Why normal vectorization does not directly apply**: The trend is a state variable that persists across ticks. A simple `bid > reference_high` comparison does not capture the persistence of the trend state.

**Cumulative formulation**: Partially cumulative. The trend can be expressed as:
- Initialize trend as NONE
- For each tick: if bid > reference_high then UP else if bid < reference_low then DOWN else previous_trend

This is a sequential state machine that can be vectorized using `np.where` with cumulative logic or Numba.

**Numba suitability**: High - simple state machine with few branches.

**Smallest sequential part**: The trend update logic itself (single state variable).

**Remaining pipeline**: All other calculations (reference high/low, breakout validation, etc.) can be fully vectorized once trend is computed.

### Candle Array Rolling

**Why sequential**: The highs/lows arrays roll after 3 candles, which requires tracking the count and managing the circular buffer.

**Why normal vectorization does not directly apply**: The initialization phase (count < 3) is different from the rolling phase (count >= 3).

**Cumulative formulation**: Can be expressed as:
- For first 3 candles: append to arrays
- For subsequent candles: shift arrays and append new value

This can be vectorized using `shift()` for the rolling phase, but the initialization requires special handling.

**Numba suitability**: Medium - simple array management, but pandas shift may be sufficient.

**Smallest sequential part**: The array rolling logic.

**Remaining pipeline**: Reference high/low calculation can use expanding windows once arrays are available.

### Zone Engagement State

**Why sequential**: Engagement depends on previous engagement state and the incremental update logic.

**Why normal vectorization does not directly apply**: Engagement is a boolean state that persists until reset at bar open.

**Cumulative formulation**: Can be expressed as:
- At bar open: reset engagement based on bar_open position
- During bar: update engagement based on boundary crosses

The bar-open reset is a boundary condition, but the intra-bar updates can be vectorized.

**Numba suitability**: Low - can be handled with pandas groupby and boundary comparisons.

**Smallest sequential part**: The engagement update logic during bar.

**Remaining pipeline**: Breakout validation and reversal touch checks are stateless once engagement is known.

### Pullback Window Lifecycle

**Why sequential**: Windows are created, updated, and removed dynamically based on bar offset and signal generation.

**Why normal vectorization does not directly apply**: The list of windows changes over time (creation/deletion), which is not easily represented as a fixed DataFrame column.

**Cumulative formulation**: Can be expressed as:
- At bar close: create windows for new breakouts
- At each bar: increment bar_offset, deactivate expired windows
- During bar: evaluate signals for active windows

This requires tracking a variable-length list of windows per group.

**Numba suitability**: High - dynamic list management with clear lifecycle rules.

**Smallest sequential part**: Window list management (creation, update, deletion).

**Remaining pipeline**: Pullback signal evaluation per window can be vectorized once windows are known.

### Reversal Keys Tracking

**Why sequential**: Keys are accumulated to ensure uniqueness per bar, requiring deduplication logic.

**Why normal vectorization does not directly apply**: The list of keys grows during the bar and must be checked for duplicates.

**Cumulative formulation**: Can be expressed as:
- At bar open: clear reversal_keys
- During bar: add new keys if not already present

This is a sequential accumulation with deduplication.

**Numba suitability**: Low - can be handled with pandas groupby and drop_duplicates.

**Smallest sequential part**: Key accumulation and deduplication.

**Remaining pipeline**: Reversal signal generation is stateless once uniqueness is enforced.

---

## _temp_state Schema

### Proposed Columns

**Input columns** (from source DataFrame):
- `broker`: string
- `symbol`: string
- `datetime`: datetime (UTC)
- `date`: datetime (floored to seconds)
- `bid`: float
- `ask`: float

**Derived time columns**:
- `bar_time`: datetime (floored to 15-minute intervals: minute % 15 = 0, second=0, microsecond=0)
- `broker_day`: string (format "YYYY.MM.DD")
- `is_bar_boundary`: boolean (bar_time changed from previous row)
- `is_day_boundary`: boolean (broker_day changed from previous row)

**Trend state columns**:
- `trend`: int (0=NONE, 1=UP, 2=DOWN)
- `trend_count`: int (0-3, then rolling)
- `trend_high_0`, `trend_high_1`, `trend_high_2`: float (rolling highs)
- `trend_low_0`, `trend_low_1`, `trend_low_2`: float (rolling lows)
- `reference_high`: float (max of available highs)
- `reference_low`: float (min of available lows)

**Zone columns** (per zone, indexed by zone_id):
- `zone_{zone_id}_low`: float
- `zone_{zone_id}_high`: float
- `zone_{zone_id}_priority`: int
- `zone_{zone_id}_buy_engaged`: boolean
- `zone_{zone_id}_sell_engaged`: boolean
- `zone_{zone_id}_reversal_usage`: int
- `zone_{zone_id}_pullback_fills`: int

**Pullback window columns** (serialized as JSON or separate rows):
- `pullback_window_id`: string (parent_breakout_id:sequence)
- `pullback_parent_breakout_id`: string
- `pullback_zone_id`: string
- `pullback_direction`: int (0=BUY, 1=SELL)
- `pullback_bar_offset`: int
- `pullback_active`: boolean
- `pullback_penetration_latched`: boolean
- `pullback_pending_active`: boolean
- `pullback_sequence`: int

**Bar data columns**:
- `bar_open`: float (opening bid of current 15-minute bar)
- `bar_high`: float (high of current 15-minute bar)
- `bar_low`: float (low of current 15-minute bar)
- `bar_close`: float (close bid of current 15-minute bar)

**Signal candidate columns**:
- `signal_candidate_id`: string
- `signal_family`: int (0=BREAKOUT, 1=REVERSAL, 2=PULLBACK)
- `signal_direction`: int (0=BUY, 1=SELL)
- `signal_order_type`: int (0=MARKET, 1=PENDING_STOP)
- `signal_entry_price`: float
- `signal_zone_id`: string
- `signal_bar_id`: string

**Risk calculation columns**:
- `stop_loss`: float
- `take_profit`: float
- `stop_zone_id`: string
- `target_zone_id`: string
- `portfolio_allowed`: boolean
- `concurrency_allowed`: boolean
- `margin_allowed`: boolean
- `entry_decision`: int (XauEntryRejection enum)

**Action column** (final output):
- `action`: string (or int enum representing the action)

**Previous row columns** (for sequential dependencies):
- `previous_bid`: float
- `previous_ask`: float
- `previous_trend`: int
- `previous_bar_time`: datetime

### Column Purposes

**Input columns**: Raw tick data from source.

**Derived time columns**: Time-based boundary detection for day and bar transitions.

**Trend state columns**: Track trend calculation state across ticks.

**Zone columns**: Track per-zone engagement and usage state.

**Pullback window columns**: Track active pullback windows and their lifecycle.

**Bar data columns**: Track OHLC data for bar close calculations.

**Signal candidate columns**: Store generated signal candidates for processing.

**Risk calculation columns**: Store risk management calculation results.

**Action column**: Final output indicating the action to take (if any).

**Previous row columns**: Facilitate sequential calculations by providing access to previous tick values.

---

## Output Contract

### Exact Expected Output

**DataFrame structure**:
- MultiIndex: (broker, symbol, datetime, date)
- Row count: Same as input DataFrame
- Row order: Same as input DataFrame
- Column: `action` (string or int enum)

**Action values and meanings**:
The original implementation does not produce a simple `action` column. Instead, it generates signal candidates that are processed through ports (external adapters) which may or may not result in actual trading actions.

For the vectorized implementation, the `action` column should represent the signal candidate type:
- `"NONE"`: No signal generated
- `"BREAKOUT_BUY"`: Buy breakout signal
- `"BREAKOUT_SELL"`: Sell breakout signal
- `"REVERSAL_BUY"`: Buy reversal signal
- `"REVERSAL_SELL"`: Sell reversal signal
- `"PULLBACK_BUY"`: Buy pullback signal
- `"PULLBACK_SELL"`: Sell pullback signal

**Action generation locations**:
- Breakout signals: `domain/xau_usd/coordinator.py::close_coordinator_bar` (lines 220-239)
- Reversal signals: `domain/xau_usd/coordinator.py::process_coordinator_tick` (lines 144-172)
- Pullback signals: `domain/xau_usd/coordinator.py::process_coordinator_tick` (lines 174-196)

**Preserved input columns**:
- The original input columns (broker, symbol, datetime, date, bid, ask) should remain in the final output for traceability.

**Discarded columns**:
- Intermediate calculation columns can be discarded after the action column is generated, unless needed for debugging or validation.

---

## Implementation Sequence

### Phase 1: Setup and Input Processing

- [ ] Create vectorized strategy module structure under `src/application/xauusd_trading_strategy_1_vector/`
- [ ] Define input DataFrame schema with MultiIndex (broker, symbol, datetime, date)
- [ ] Implement input validation (bid > 0, ask > bid, finite values)
- [ ] Derive time columns: bar_time (15-minute intervals), broker_day, is_bar_boundary, is_day_boundary
- [ ] Implement previous row columns: previous_bid, previous_ask, previous_bar_time
- [ ] Group by (broker, symbol) for state isolation

### Phase 2: Zone Loading and Initialization

- [ ] Implement zone loading from external source (ports.load_raw_zones equivalent)
- [ ] Implement zone merging logic (build_merged_zones)
- [ ] Initialize zone state columns per zone (low, high, priority, engagement)
- [ ] Implement day boundary detection and reinitialization logic
- [ ] Reset all state columns on day boundary

### Phase 3: Trend Calculation

- [ ] Implement 15-minute bar high/low tracking (OHLC aggregation per M15 bar)
- [ ] Implement trend reference calculation (expanding max/min)
- [ ] Implement trend state update logic (sequential state machine)
- [ ] Handle 3-candle initialization phase with historical M15 data loading
- [ ] Implement candle array rolling logic
- [ ] Test trend calculation against MT5 reference implementation

### Phase 4: Zone Engagement

- [ ] Implement zone engagement reset at bar open
- [ ] Implement directional cross detection (previous_bid to current_bid)
- [ ] Implement multi-zone tick gap detection
- [ ] Implement zone engagement update logic
- [ ] Test zone engagement against reference implementation

### Phase 5: Breakout Signal Generation

- [ ] Identify bar close rows (is_bar_boundary)
- [ ] Implement breakout validation logic per zone and direction
- [ ] Generate breakout candidates at bar close
- [ ] Implement breakout ID generation (sequence)
- [ ] Test breakout signals against reference implementation

### Phase 6: Reversal Signal Generation

- [ ] Implement reversal directional touch logic
- [ ] Implement reversal uniqueness tracking (reversal_keys)
- [ ] Generate reversal candidates during bar
- [ ] Implement reversal usage limits (priority-based)
- [ ] Test reversal signals against reference implementation

### Phase 7: Pullback Window Management

- [ ] Implement pullback window creation on breakout
- [ ] Implement bar_offset increment at bar boundary
- [ ] Implement window deactivation (bar_offset > 5)
- [ ] Implement window removal (inactive windows)
- [ ] Serialize pullback windows to DataFrame columns
- [ ] Test pullback window lifecycle against reference implementation

### Phase 8: Pullback Signal Generation

- [ ] Implement pullback penetration check
- [ ] Implement pullback window active check
- [ ] Implement pullback usage allowance check
- [ ] Generate pullback candidates during bar
- [ ] Implement pullback sequence increment
- [ ] Test pullback signals against reference implementation

### Phase 9: Risk Calculations

- [ ] Implement initial stop loss calculation (zone search)
- [ ] Implement initial take profit calculation (zone search)
- [ ] Implement portfolio risk check
- [ ] Implement concurrency check
- [ ] Implement margin check (if external data available)
- [ ] Implement entry decision logic
- [ ] Test risk calculations against reference implementation

### Phase 10: Action Column Generation

- [ ] Consolidate all signal candidates into action column
- [ ] Map signal types to action values
- [ ] Handle multiple signals per tick (priority logic)
- [ ] Generate final action column
- [ ] Preserve input columns in output
- [ ] Discard intermediate columns (optional)

### Phase 11: Integration and Testing

- [ ] Integrate all phases into end-to-end pipeline
- [ ] Implement error handling and validation
- [ ] Add logging for debugging
- [ ] Create test fixtures with deterministic input
- [ ] Run comparison tests against reference implementation
- [ ] Validate action column matches reference behavior

### Phase 12: Optimization and Cleanup

- [ ] Profile performance bottlenecks
- [ ] Optimize vectorized operations
- [ ] Implement Numba for sequential parts if beneficial
- [ ] Clean up intermediate columns
- [ ] Add documentation
- [ ] Final validation and regression testing

---

## Appendix — Deferred Correctness Validation and Testing

### Why Deferred

Correctness validation is deferred because the immediate objective is to establish the vectorized implementation and its complete end-to-end computational flow. Once that implementation is operational, the deferred validation will compare it systematically against the original event-loop implementation.

The intended order is:

1. Investigate original algorithm
2. Document algorithm and implementation plan
3. Implement vectorized version
4. Make the complete vectorized flow operational
5. Then perform systematic correctness validation
6. Add regression/edge-case tests
7. Benchmark and optimize based on evidence

### Reference Comparison

**Objective**: Compare the vectorized implementation against the original event-loop implementation using the same deterministic input.

**Comparison scope**:
- `action` for every row
- All observable per-tick results (signal candidates)
- All observable state (trend, engagement, pullback windows)
- Relevant intermediate results where needed to diagnose discrepancies

**Numerical comparison rules**:
- Exact equality for: action values, enum values, boolean flags, integer counters
- `rtol=1e-9` and `atol=1e-9` for: floating-point prices (bid, ask, stop_loss, take_profit)
- NaN/NA equality: Use pandas `equals()` with `equal_nan=True` for state columns

**Implementation approach**:
- Create deterministic test fixtures with known input data
- Run both implementations on the same input
- Compare outputs using the rules above
- Report any discrepancies with detailed context (row index, state values)

### Edge Cases

**Test scenarios**:
- Empty input DataFrame
- Single-row input
- First-row behavior (no previous row)
- Duplicate timestamps (multiple rows at same millisecond)
- Multiple rows at same second (different milliseconds)
- Multiple brokers in same DataFrame
- Multiple symbols in same DataFrame
- Multiple (broker, symbol) groups
- State isolation between groups
- Day/session boundaries
- State reset conditions
- Threshold transitions (trend changes, engagement changes)
- Boundary conditions (price exactly at zone boundary)
- End-of-stream behavior (last row)
- Zone priority variations (1 vs 2)
- Pullback window expiration (bar_offset > 5)
- Reversal usage limit exhaustion
- Pullback usage limit exhaustion

**Validation approach**:
- For each edge case, create a specific test fixture
- Run both implementations
- Verify behavior matches expected semantics
- Document any differences in implementation approach

### Determinism

**Requirement**: Repeated execution with the same input must produce the same result.

**Validation approach**:
- Use fixed seed for any random operations (if any)
- Ensure all external dependencies are mocked or controlled
- Run the same input multiple times and verify identical output
- Check for non-deterministic operations (hash-based ordering, etc.)

### Regression Tests

**Location**: `tests/application/xauusd_trading_strategy_1_vector/`

**Test structure**:
- `test_vectorization_correctness.py`: Main comparison tests
- `test_edge_cases.py`: Edge case-specific tests
- `test_state_isolation.py`: Multi-broker/symbol isolation tests
- `fixtures/`: Deterministic input fixtures (CSV or Parquet)

**Test coverage**:
- All major calculation paths (trend, engagement, signals)
- All signal families (breakout, reversal, pullback)
- All state transitions (day boundary, bar boundary)
- All risk calculation paths
- All edge cases listed above

**Regression criteria**:
- Action column must match reference implementation exactly
- State trajectories must match reference implementation
- Signal candidates must match reference implementation
- Any deviation must be explained and accepted

### Performance Benchmarking

**Objective**: Measure performance improvement of vectorized implementation over event-loop.

**Metrics**:
- Total execution time for fixed input size
- Memory usage
- Throughput (rows per second)

**Benchmark approach**:
- Use realistic input sizes (e.g., 1M ticks)
- Measure cold start and warm start performance
- Profile memory allocation patterns
- Identify bottlenecks for further optimization

**Success criteria**:
- Vectorized implementation should be significantly faster than event-loop
- Memory usage should be reasonable for expected input sizes
- Performance should scale linearly with input size

### Implementation Validation Checklist

- [ ] Action column matches reference for all test fixtures
- [ ] Trend state matches reference at all ticks
- [ ] Zone engagement matches reference at all ticks
- [ ] Breakout signals match reference (timing, direction, zone)
- [ ] Reversal signals match reference (timing, direction, zone)
- [ ] Pullback signals match reference (timing, direction, zone, sequence)
- [ ] Pullback window lifecycle matches reference
- [ ] State isolation between (broker, symbol) groups
- [ ] Day boundary reinitialization matches reference
- [ ] Bar boundary behavior matches reference
- [ ] Edge cases handled correctly
- [ ] Performance benchmarks meet expectations
- [ ] Regression tests pass consistently
- [ ] Documentation is complete and accurate
