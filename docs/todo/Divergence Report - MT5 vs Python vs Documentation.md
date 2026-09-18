# Divergence Report: MT5 vs Python vs Documentation

**Date**: 2026-09-18
**Primary Source of Truth**: `mt5/XAUUSD_MVP.mq5`
**Documentation**: `docs/todo/Vectorization Implementation Plan.md`

## Executive Summary

A detailed comparison was performed between the MT5 implementation (primary source of truth), the Python implementation, and the vectorization planning documentation. The primary divergence found was an incorrect assumption about bar period. The Python implementation is largely consistent with the MT5 implementation.

## Critical Divergence: Bar Period

### Issue
The original planning documentation incorrectly assumed **1-minute bars** for bar-based calculations. The MT5 implementation uses **15-minute bars**.

### Documentation Corrections Made

The following sections were corrected to reflect 15-minute bars throughout:
1. Overview section — Added critical divergence note
2. Bar boundary description — Changed to 15-minute bar changes
3. Time semantics — bar_time definition corrected to 15-minute intervals
4. Trend calculation — Added note about historical M15 data loading
5. Implementation phases — Updated to specify 15-minute bars
6. Data column descriptions — Corrected to specify 15-minute bars
7. Derived time columns — bar_time definition updated

### Python Implementation Status

The Python implementation uses a configurable bar time provider. The port implementations should be verified to ensure they provide 15-minute data to match MT5 behavior.

## Algorithm Consistency Analysis

### Tick Processing Flow
**Status**: Consistent

The execution flow matches both implementations in sequence: time basis probe → event loop initialization → day boundary check → bar boundary check → operational safety checks → TP management → profit protection → close opposite reversals → process candidates from bar close → coordinator tick processing → process candidates → update counters.

### State Model
**Status**: Consistent

Documented state model matches both implementations for strategy runtime state, market coordinator, trend state, zone states, pullback windows, and reversal keys.

### Signal Generation Logic
**Status**: Consistent

- Breakout signals: Generated at bar close, require engagement and trend alignment
- Reversal signals: Generated during bar on zone touches against trend
- Pullback signals: Generated during bar from active pullback windows

### Risk Calculations
**Status**: Consistent

Stop loss, take profit, portfolio risk, concurrency, and margin calculations match between implementations.

## Minor Divergences

### Bar Time Calculation
- MT5: Uses 15-minute bar time from MQL5 API
- Python: Uses configurable bar time provider, should be set to 15-minute intervals
- Impact: Low — configurable but must be verified

### Trend History Loading
- MT5: Loads historical 15-minute bars from MQL5 API
- Python: Uses port interface for trend history loading
- Impact: Low — port interface abstracts implementation

## Recommendations

### Immediate Actions
1. Corrected: Documentation now specifies 15-minute bars throughout
2. Required: Verify Python port implementations provide 15-minute bar data
3. Required: Set default bar time provider to 15-minute flooring
4. Required: Add validation ensuring bar period matches MT5 (15 minutes)

### Documentation Updates
1. Corrected: All bar period references now specify 15-minute
2. Recommended: Add configuration section explaining bar period requirements
