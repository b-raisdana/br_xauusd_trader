# Vectorization Appendix — Deferred Correctness Validation and Testing

## Purpose

This appendix documents the correctness validation and testing plan that will be executed after the vectorized implementation is operational. The validation is deferred to first establish the complete end-to-end computational flow, then systematically compare it against the original event-loop implementation.

## Intended Order

1. Investigate original algorithm
2. Document algorithm and implementation plan
3. Implement vectorized version
4. Make the complete vectorized flow operational
5. Then perform systematic correctness validation
6. Add regression/edge-case tests
7. Benchmark and optimize based on evidence

---

## Reference Comparison

### Objective

Compare the vectorized implementation against the original event-loop implementation using the same deterministic input.

### Comparison Scope

**Primary outputs**:
- `action` for every row
- All observable per-tick results (signal candidates)
- All observable state (trend, engagement, pullback windows)
- Relevant intermediate results where needed to diagnose discrepancies

**State trajectories**:
- Trend state evolution across ticks
- Zone engagement changes
- Pullback window lifecycle
- Reversal usage counters
- Pullback fill counters

### Numerical Comparison Rules

**Exact equality required for**:
- Action values (string or enum)
- Enum values (trend, direction, signal family, etc.)
- Boolean flags (engaged, active, etc.)
- Integer counters (sequence, usage, fills, etc.)
- String identifiers (zone_id, bar_id, candidate_id)

**Tolerance-based comparison for**:
- Floating-point prices
- Bid/ask prices
- Stop-loss and take-profit values
- Zone boundaries (low, high)

**NaN/NA handling**: Use comparison methods that handle NaN equality for state columns.

### Implementation Approach

**Test fixture creation**:
- Create deterministic input fixtures with known tick data
- Include zone configuration for each test case
- Ensure fixtures cover all major signal types and edge cases

**Execution**:
- Load fixture into both implementations
- Run both implementations with same settings
- Capture outputs from both

**Comparison**:
- Compare action column row-by-row
- Compare state trajectories at key checkpoints
- Compare signal candidate lists
- Report discrepancies with detailed context

---

## Edge Cases

### Test Scenarios

- Empty input DataFrame
- Single-row input
- First-row behavior (no previous row)
- Duplicate timestamps (multiple rows at same millisecond)
- Multiple rows at same second (different milliseconds)
- Multiple brokers in same data
- Multiple symbols in same data
- Multiple (broker, symbol) groups
- State isolation between groups
- Day/session boundaries
- State reset conditions
- Threshold transitions (trend changes, zone boundary crossings)
- Boundary conditions (price exactly at zone boundary)
- End-of-stream behavior (last row)
- Zone priority variations (1 vs 2)
- Pullback window expiration (bar_offset > 5)
- Reversal usage limit exhaustion
- Pullback usage limit exhaustion

### Validation Approach

For each edge case:
1. Create specific test fixture with minimal but representative data
2. Document expected behavior based on reference implementation
3. Run both implementations
4. Verify behavior matches expected semantics
5. Document any differences

---

## Determinism

### Requirement

Repeated execution with the same input must produce the same result.

### Validation Approach

- If any random operations are used, set fixed seed
- Mock or control all external dependencies
- Use deterministic data sources for zones, history
- Ensure no hidden non-determinism
- Run the same input multiple times and verify identical output

---

## Regression Tests

### Test Structure

**Main comparison tests**: Against reference implementation for all major calculation paths and signal families

**Edge case tests**: One test per edge case scenario

**State isolation tests**: Multi-broker/symbol isolation and groupby correctness

**Fixtures**: Deterministic input data covering all scenarios

### Test Coverage

- All major calculation paths (trend, engagement, signals)
- All signal families (breakout, reversal, pullback)
- All state transitions (day boundary, bar boundary)
- All risk calculation paths
- All edge cases listed above

### Regression Criteria

- Action column must match reference implementation exactly
- State trajectories must match reference at all ticks
- Signal candidates must match reference
- Any deviation must be explained and documented

---

## Performance Benchmarking

### Objective

Measure performance improvement of vectorized implementation over event-loop.

### Metrics

- Execution time for fixed input size
- Memory usage
- Throughput (rows per second)

### Success Criteria

- Vectorized implementation should be significantly faster than event-loop
- Memory usage should be reasonable for expected input sizes
- Performance should scale with input size

---

## Known Limitations and Future Work

### Current Limitations

- External ports (zone loading, candidate processing) are mocked for testing but need real implementations for production
- Risk state, open positions, and margin are external dependencies
- Order execution and position management are separate from signal generation

### Future Work

- Real-time streaming processing with incremental state updates
- Multi-timeframe support
- Parameter optimization and backtesting
- Production integration with real infrastructure
