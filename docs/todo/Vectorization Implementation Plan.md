# Vectorization Implementation Plan

## Overview

**Objective**: Convert the event-loop-based XAUUSD trading strategy into a vectorized data processing implementation.

**Primary source of truth**: `mt5/XAUUSD_MVP.mq5` (MT5 implementation)

**Target implementation**: `src/application/xauusd_trading_strategy_1_vector/`

**Scope restrictions**: This document is investigation and planning only. No implementation code will be created during this phase.

**Expected final output**: A data structure with grouped indices (broker, symbol, datetime, date) containing an `action` column with the same semantics as the MT5 implementation.

**Critical divergence note**: The original documentation incorrectly assumed 1-minute bars. The MT5 implementation uses **15-minute bars** for all bar-based calculations (trend history, bar close/open, breakout signals). This has been corrected throughout this document to match the MT5 source of truth.

---

## Current Algorithm

The strategy processes XAUUSD price ticks to generate trading signals (breakouts, reversals, pullbacks) based on predefined price zones and trend analysis. The algorithm operates on a per-tick basis with persistent state that tracks market conditions, zone engagement, and signal generation history.

### Core Components

**Zone-based signal generation**: The strategy uses predefined price zones (low-high ranges) to identify potential trading opportunities. Zones have priorities (1 or 2) that affect signal frequency.

**Trend tracking**: A rolling window of highs and lows determines the current trend (UP, DOWN, or NONE). Trend influences which signals are valid. The trend initializes at NONE at the start of each day and resets daily without carry from the previous day.

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
Check time basis probe emission (first 5 valid ticks if enabled)
    ↓
If event loop not ready:
    Initialize event loop:
        - Load raw zones for broker day
        - Merge overlapping zones
        - Initialize daily zone states
        - Load trend history (previous candles)
        - Initialize trend state
        - Begin first bar
        - Set event loop ready = True
    ↓
Check day boundary:
    If tick time day != current broker day:
        Set event loop ready = False
        Reinitialize event loop (as above)
    ↓
Check bar boundary:
    If bar time != current bar time:
        Close previous bar:
            - Generate breakout signals from engaged zones
            - Create pullback windows for new breakouts
            - Record trend candle
            - Set bar active = False
        Begin new bar:
            - Advance pullback window offsets
            - Cancel expired pullback windows
            - Reset zone engagement based on bar open
            - Set bar active = True
            - Update current bar time
    ↓
Execute operational safety checks
    ↓
Manage pullback take-profit modifications
    ↓
Manage profit protection trailing stops
    ↓
Close opposite reversal positions
    ↓
Process pending candidates from previous bar close
    ↓
Process coordinator tick:
    - Update trend based on current bid
    - Update zone engagement based on bid movement
    - Generate reversal signals on zone touches
    - Generate pullback signals from active windows
    - Update last bid, last ask
    ↓
Process new candidates from coordinator tick
    ↓
Update candidate counters (breakout, reversal, pullback)
    ↓
Return success/failure
```

**Note**: This execution flow matches the MT5 implementation. The processing sequence is: Trend update → Engagement/Touch check → Signal evaluation (Reversal, Pullback). If Trend change and Touch occur in the same tick, Signal uses the new Trend.

### Key Decision Points

**Day boundary**: When the broker day changes, all state is reinitialized. This includes zones, trend history, and all counters.

**Bar boundary**: When the 15-minute bar changes, the previous bar is closed and a new bar begins. This is when breakout signals are generated and pullback windows are created.

**Zone engagement**: A zone becomes engaged when price enters its range during an open bar. Engagement is required for breakout signals and is reset at each bar open.

**Reversal uniqueness**: Each (bar, zone, direction) combination can generate at most one reversal signal per bar.

**Pullback window lifecycle**: Pullback windows are created on bar close when a breakout occurs. They remain active for 5 bars (bar_offset 1-5). Each window can generate multiple pullback signals (sequence incrementing).

---

## State Model

### Global Strategy-Level State

State not specific to broker/symbol: execution projections, execution bindings, runtime requests, order audit log, market coordinator, current bar time, event loop readiness, daily loss lock, operational lock, various counters (breakout, reversal, pullback, attempt, accept, reject), request/event sequences, restart lock, session counters, financial totals, protection modify counters, conflict close counter, symbol spec emission flag, attribution counters.

**Reset behavior**: Most counters are cumulative across the session. Event loop readiness resets on day boundary. Daily loss lock persists once set.

### Core Algorithmic State (per broker, per symbol)

- `broker_day`: String in format "YYYY.MM.DD"
- `bar_id`: String identifier for current bar
- `day_active`: Boolean indicating day initialization complete
- `bar_active`: Boolean indicating bar processing active
- `bar_open`: Opening bid price of current bar
- `last_bid`: Last processed bid price (previous tick)
- `last_ask`: Last processed ask price (previous tick)
- `breakout_sequence`: Daily sequence number for breakout IDs
- `trend`: Trend tracking state (trend, count, highs, lows)
- `zones`: One state per zone (engagement, usage counters)
- `pullbacks`: Active pullback windows
- `reversal_keys`: List tracking reversal uniqueness per bar
- `attempted_bars`: List of bar_ids where entry was attempted

**Reset behavior**: Reinitialized at day start. Engagement resets at each bar open. Reversal and Pullback usage accumulate during the day.

### Trend Reference State

- `trend`: Current trend (NONE, UP, DOWN)
- `count`: Number of candles recorded (0-3, then rolling)
- `highs`: Array of 3 high prices (rolling window)
- `lows`: Array of 3 low prices (rolling window)

**Reset behavior**: Reinitialized at day start. Count increments to 3, then highs/lows roll.

### Per-Zone State

- `zone`: Zone identity, boundaries, priority
- `buy_engaged`: Boolean indicating price is in zone for buy signals
- `sell_engaged`: Boolean indicating price is in zone for sell signals
- `reversal_usage`: Counter for reversal signals used (limit: 2 for High, 1 for Normal per day)
- `pullback_fills`: Counter for pullback fills (affects usage allowance)

**Reset behavior**: Reinitialized at day start. Engagement reset at each bar open. Usage counters accumulate during the day.

### Pullback Window State

- `parent_breakout_id`: ID of the breakout that created this window
- `zone`: Zone associated with this pullback
- `direction`: BUY or SELL
- `bar_offset`: Number of bars since breakout (active 1-5)
- `active`: Boolean indicating window is within valid range
- `penetration_latched`: Boolean indicating price has penetrated zone
- `pending_active`: Boolean indicating pending order is active
- `sequence`: Sequence number for pullback signals from this window

**Reset behavior**: Created on bar close when breakout occurs. Becomes inactive after bar_offset > 5.

---

## Input Model

### Expected Data Structure

**Index levels**: broker, symbol, datetime (UTC timezone-aware), date (floored)

**Required columns**: bid, ask

### Time Semantics

**bar_time**: Derived from datetime by flooring to 15-minute intervals. Used for bar boundary detection.

**Day boundary**: Detected when broker_day changes. Triggers full reinitialization.

**Bar boundary**: Detected when bar_time changes. Triggers bar close and new bar begin.

**Duplicate timestamps**: Valid and expected. Each row represents a distinct event even with identical timestamps. Relative order matters for state updates.

**Ordering assumptions**: Data must be sorted by (broker, symbol, datetime). Within the same timestamp, row order is preserved and matters for sequential state updates.

---

## Calculation Inventory

### Trend Calculation

**Inputs**: Current bid, reference_high, reference_low (from last 3 candles)
**Previous state**: trend, count, highs[0-2], lows[0-2]
**Calculation**: If bid > reference_high: trend = UP; if bid < reference_low: trend = DOWN; else: trend unchanged
**Updated state**: trend (may change)
**Output**: Used in breakout validation and reversal detection
**Dependency**: Sequential - trend depends on previous trend state

### Reference High/Low Calculation

**Inputs**: highs[0:count], lows[0:count]
**Calculation**: reference_high = max(highs[:count]); reference_low = min(lows[:count])
**Updated state**: None (read-only)
**Output**: Used in trend calculation
**Dependency**: Sequential - arrays roll after 3 candles

### Zone Engagement Update

**Inputs**: previous_bid, current_bid, zone boundaries
**Calculation**: Count directional zone crosses; if multi-zone tick gap, set engagement based on current_bid position; else update incrementally
**Updated state**: buy_engaged, sell_engaged per zone
**Output**: Used in breakout validation
**Dependency**: Sequential - depends on previous engagement state

### Breakout Validation

**Inputs**: zone, direction, trend, close_price, engaged
**Calculation**: If not engaged: False; If BUY: trend == UP and close_price > zone.high + buffer; If SELL: trend == DOWN and close_price < zone.low - buffer
**Updated state**: None (read-only)
**Output**: Boolean indicating valid breakout
**Dependency**: None (stateless per tick)

### Reversal Directional Touch

**Inputs**: zone, direction, trend, previous_bid, current_bid, multi_zone_tick_gap
**Calculation**: If multi_zone_tick_gap: False; If SELL: trend == UP and previous_bid < zone.low and current_bid >= zone.low; If BUY: trend == DOWN and previous_bid > zone.high and current_bid <= zone.high
**Updated state**: None (read-only)
**Output**: Boolean indicating valid reversal touch
**Dependency**: None (stateless per tick)

### Pullback Penetration Check

**Inputs**: zone, direction, bid
**Calculation**: entry_price = zone.high if BUY else zone.low; If BUY: penetrated = bid <= zone.high - penetration; If SELL: penetrated = bid >= zone.low + penetration
**Updated state**: None (read-only)
**Output**: (penetrated: bool, entry_price: float)
**Dependency**: None (stateless per tick)

### Pullback Window Active Check

**Inputs**: bar_offset
**Calculation**: return 1 <= bar_offset <= 5
**Updated state**: None (read-only)
**Output**: Boolean indicating window is in valid range
**Dependency**: None (stateless per tick)

### Pullback Usage Allowed Check

**Inputs**: zone_priority, daily_fills
**Calculation**: If daily_fills < 0: False; If zone_priority == 1: True; Else: daily_fills < 1
**Updated state**: None (read-only)
**Output**: Boolean indicating pullback usage is allowed
**Dependency**: None (stateless per tick)

### Initial Stop Loss Calculation

**Inputs**: direction, entry_price, zones list
**Calculation**: Find nearest zone boundary in opposite direction from entry; Apply cap of BASE_R_USD (6) on stop distance; If no Stop Zone found: Trade rejected
**Updated state**: None (read-only)
**Output**: (found: bool, stop_loss: float | None, stop_zone_id: str | None)
**Dependency**: None (stateless per tick)

### Initial Take Profit Calculation

**Inputs**: direction, entry_price, zones list
**Calculation**: Find nearest zone boundary in trade direction from entry; Minimum distance of BASE_R_USD (6) from entry; If no Target Zone found: Trade rejected
**Updated state**: None (read-only)
**Output**: (found: bool, take_profit: float | None, target_zone_id: str | None)
**Dependency**: None (stateless per tick)

### Portfolio Risk Check

**Inputs**: strategy_capital, realized_gross_loss, open_risk, pending_risk, proposed_risk
**Calculation**: budget = strategy_capital * GROSS_DAILY_RISK_FRACTION (15%); return realized_gross_loss + open_risk + pending_risk + proposed_risk <= budget
**Updated state**: None (read-only)
**Output**: Boolean indicating portfolio risk allows entry
**Dependency**: None (stateless per tick)

### Concurrency Check

**Inputs**: strategy_capital, open_positions
**Calculation**: maximum = 3 if capital == 200, 5 if capital == 300; return maximum >= 0 and open_positions < maximum
**Updated state**: None (read-only)
**Output**: Boolean indicating concurrency allows entry
**Dependency**: None (stateless per tick)

---

## State Transitions and Boundary Conditions

### Day Boundary
- All zone states reset
- Trend resets to NONE
- Breakout sequence resets
- Pullback windows cleared
- Reversal usage resets

### Bar Open
- Zone engagement resets based on bar open position
- Pullback window offsets advance by 1
- Expired pullback windows (offset > 5) removed
- Engagement reset from bar open position

### Breakout Signal Generation (at bar close)
- Check each engaged zone against trend and buffer conditions
- Generate breakout candidates with daily sequence IDs
- Create pullback windows for new breakouts

### Entry Decision Gate (sequential checks)
1. No entry attempted in current M15 bar
2. Daily usage quota available for signal type and zone
3. Free Space > 3.00 USD in trade direction
4. Valid Stop Zone and Target Zone found
5. Daily loss not locked
6. Portfolio risk within GROSS15 budget
7. Position count below profile maximum
8. Margin sufficient
9. Volume = 0.01 lot, SL/TP valid direction
10. Session end lock and restart lock not active

---

## Output Contract

### Expected Output

**Structure**: Grouped data with indices (broker, symbol, datetime, date); same row count and order as input; `action` column

**Action values**:
- No signal: no action generated
- Breakout Buy/SELL: valid breakout detected at bar close
- Reversal Buy/SELL: valid directional touch detected during bar
- Pullback Buy/SELL: valid pullback signal from active window

---

## Deferred Correctness Validation and Testing

### Reference Comparison

Compare the vectorized implementation against the original event-loop implementation using the same deterministic input.

**Comparison scope**: `action` for every row, all observable per-tick results, all observable state, relevant intermediate results.

**Numerical comparison rules**:
- Exact equality for: action values, enum values, boolean flags, integer counters, string identifiers
- Tolerance for: floating-point prices

### Edge Cases

Test scenarios include: empty input, single-row input, first-row behavior, duplicate timestamps, multiple brokers, multiple symbols, state isolation between groups, day/session boundaries, threshold transitions, boundary conditions, end-of-stream behavior, zone priority variations, pullback window expiration, usage limit exhaustion.

### Determinism

Repeated execution with the same input must produce the same result. Use fixed seeds, mock external dependencies, verify no non-deterministic operations.

### Regression Tests

Tests should cover all major calculation paths (trend, engagement, signals), all signal families (breakout, reversal, pullback), all state transitions (day boundary, bar boundary), all risk calculation paths, and all edge cases.

**Regression criteria**: Action column must match reference implementation exactly; state trajectories must match; any deviation must be explained and accepted.
