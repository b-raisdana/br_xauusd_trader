# Divergence Report: MT5 vs Python vs Documentation

**Date**: 2026-09-18  
**Primary Source of Truth**: `mt5/XAUUSD_MVP.mq5`  
**Secondary Reference**: `src/application/xauusd_trading_strategy_1/`  
**Documentation**: `docs/todo/Vectorization Implementation Plan.md`

---

## Executive Summary

A detailed comparison was performed between the MT5 implementation (primary source of truth), the Python implementation, and the vectorization planning documentation. The analysis revealed a **critical divergence** regarding bar period that has been corrected in the documentation. The Python implementation is largely consistent with the MT5 implementation.

---

## Critical Divergence: Bar Period

### Issue
The original `Vectorization Implementation Plan.md` incorrectly assumed **1-minute bars** for bar-based calculations. The MT5 implementation uses **15-minute bars (PERIOD_M15)**.

### MT5 Evidence
- **Line 633**: `CopyRates(_Symbol,PERIOD_M15,day_start,bar_time-1,history)` - loads historical 15-minute bars
- **Line 634**: `iTime(_Symbol,PERIOD_M15,1)` - gets previous 15-minute bar time
- **Line 643**: `iOpen(_Symbol,PERIOD_M15,0)` - gets current 15-minute bar open
- **Line 1251**: `iTime(_Symbol,PERIOD_M15,0)` - current bar time is 15-minute based
- **Line 1275**: `iHigh(_Symbol,PERIOD_M15,1)` - previous 15-minute bar high
- **Line 1276**: `iLow(_Symbol,PERIOD_M15,1)` - previous 15-minute bar low
- **Line 1277**: `iClose(_Symbol,PERIOD_M15,1)` - previous 15-minute bar close

### Documentation Corrections Made
The following sections in `Vectorization Implementation Plan.md` were corrected to reflect 15-minute bars:

1. **Overview section** - Added critical divergence note
2. **Bar boundary description** - Changed from "minute changes" to "15-minute bar changes"
3. **Time semantics section** - Changed bar_time definition from minute-level to 15-minute intervals
4. **Trend calculation section** - Added note about historical M15 data loading
5. **Phase 3 implementation steps** - Updated to specify 15-minute bars
6. **Bar data columns** - Updated column descriptions to specify 15-minute bars
7. **Derived time columns** - Updated bar_time definition to 15-minute intervals

### Python Implementation Status
The Python implementation uses a generic `bar_time_provider` that defaults to minute-level flooring (`tick.time.replace(second=0, microsecond=0)`). However, this is designed to be configurable through the `bar_time_provider` parameter in `CurrentEventLoop.__init__`. The actual bar period depends on the port implementation (`ports.current_bar`, `ports.previous_bar`) which should provide 15-minute bar data to match MT5 behavior.

**Status**: **Potentially divergent** - The Python implementation may not enforce 15-minute bars by default, but this appears to be configurable. The port implementations should be verified to ensure they provide M15 data.

---

## Algorithm Consistency Analysis

### Tick Processing Flow
**Status**: **Consistent**

The execution flow documented in the plan matches both implementations:

1. Time basis probe emission (first 5 ticks)
2. Event loop initialization (if not ready)
3. Day boundary check and reinitialization
4. Bar boundary check (close previous bar, begin new bar)
5. Operational safety checks
6. Pullback TP management
7. Profit protection management
8. Close opposite reversals
9. Process candidates from bar close
10. Process coordinator tick (trend, engagement, reversal, pullback signals)
11. Process candidates from coordinator tick
12. Update counters

**MT5 Reference**: `ProcessCurrentEventLoopTick` (lines 1248-1335)  
**Python Reference**: `process_current_event_loop_tick` (lines 163-235)

### State Model
**Status**: **Consistent**

The documented state model matches both implementations:

- `StrategyRuntimeState` / `XauMarketCoordinator` structure
- Trend state (trend, count, highs, lows)
- Zone states (engagement, usage counters)
- Pullback window lifecycle
- Reversal keys tracking

### Signal Generation Logic
**Status**: **Consistent**

- **Breakout signals**: Generated at bar close, require engagement and trend alignment
- **Reversal signals**: Generated during bar on zone touches against trend
- **Pullback signals**: Generated during bar from active pullback windows

### Risk Calculations
**Status**: **Consistent**

- Stop loss calculation (nearest zone in opposite direction)
- Take profit calculation (nearest zone in trade direction)
- Portfolio risk limits
- Concurrency limits
- Margin requirements

---

## Minor Divergences and Observations

### 1. Bar Time Calculation
**MT5**: Uses MQL5 `iTime(_Symbol,PERIOD_M15,0)` for current bar time  
**Python**: Uses configurable `bar_time_provider` defaulting to minute flooring  
**Impact**: Low - Python implementation is configurable but should be set to 15-minute intervals

### 2. Trend History Loading
**MT5**: Uses `CopyRates(_Symbol,PERIOD_M15,day_start,bar_time-1,history)`  
**Python**: Uses `ports.load_trend_history(day_start, bar_time)`  
**Impact**: Low - Port interface abstracts the implementation

### 3. Zone Engagement Logic
**Status**: **Consistent**

Both implementations track engagement per zone and direction, with reset at bar open.

### 4. Pullback Window Lifecycle
**Status**: **Consistent**

Both implementations use 5-bar window (bar_offset 1-5) with sequence incrementing.

---

## Python Implementation Assessment

### Correctness
**Overall Assessment**: **Mostly Correct**

The Python implementation in `src/application/xauusd_trading_strategy_1/` correctly implements the core algorithm logic as defined in the MT5 source. The main concern is the configurable bar period, which should be set to 15-minute intervals to match MT5 behavior.

### Port Interface Design
**Status**: **Well-Designed**

The `EventLoopPorts` protocol properly abstracts the external dependencies (zone loading, bar data, execution, etc.), allowing the same algorithm logic to be used with different data sources and execution environments.

### Key Files Analyzed
- `on_tick.py` - Entry point, delegates to event loop
- `event_loop.py` - Main event loop logic, matches MT5 flow
- `coordinator.py` - Signal generation logic, matches MT5 coordinator

---

## Recommendations

### Immediate Actions
1. ✅ **Completed**: Corrected documentation to specify 15-minute bars throughout
2. ⚠️ **Required**: Verify Python port implementations provide 15-minute bar data
3. ⚠️ **Required**: Set default `bar_time_provider` to 15-minute flooring
4. ⚠️ **Required**: Add validation to ensure bar period matches MT5 (15 minutes)

### Testing Recommendations
1. Create integration tests that verify Python implementation produces identical results to MT5 for the same input data
2. Add validation checks for bar period in initialization
3. Test trend history loading with actual M15 data
4. Verify bar boundary detection matches MT5 behavior

### Documentation Updates
1. ✅ **Completed**: Added critical divergence note to overview
2. ✅ **Completed**: Updated all bar period references to 15-minute
3. ⚠️ **Recommended**: Add configuration section explaining bar period requirements
4. ⚠️ **Recommended**: Add port implementation guidelines for M15 data

---

## Conclusion

The primary divergence found was the **incorrect assumption of 1-minute bars** in the documentation, which has been corrected. The MT5 implementation uses **15-minute bars (PERIOD_M15)** for all bar-based calculations. The Python implementation appears algorithmically correct but requires verification that the port implementations provide 15-minute bar data to match MT5 behavior exactly.

The core algorithm logic, state management, and signal generation are consistent between MT5 and Python implementations. The vectorization plan should proceed with the corrected understanding of 15-minute bars as the fundamental time unit for bar-based calculations.

---

**Files Modified**:
- `docs/todo/Vectorization Implementation Plan.md` - Corrected bar period references throughout

**Files Analyzed**:
- `mt5/XAUUSD_MVP.mq5` - Primary source of truth
- `src/application/xauusd_trading_strategy_1/on_tick.py` - Python entry point
- `src/application/xauusd_trading_strategy_1/event_loop.py` - Python event loop
- `src/domain/xau_usd/coordinator.py` - Python coordinator logic
