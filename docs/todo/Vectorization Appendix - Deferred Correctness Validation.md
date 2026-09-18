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
- Floating-point prices: `rtol=1e-9`, `atol=1e-9`
- Bid/ask prices
- Stop-loss and take-profit values
- Zone boundaries (low, high)

**NaN/NA handling**:
- Use pandas `equals()` with `equal_nan=True` for state columns
- Explicitly check for NaN in price columns and validate against reference

### Implementation Approach

**Test fixture creation**:
- Create deterministic input fixtures with known tick data
- Include zones configuration for each test case
- Ensure fixtures cover all major signal types and edge cases

**Execution**:
- Load fixture into both implementations
- Run event-loop implementation with same settings
- Run vectorized implementation with same settings
- Capture outputs from both

**Comparison**:
- Compare action column row-by-row
- Compare state trajectories at key checkpoints
- Compare signal candidate lists (timing, type, parameters)
- Report discrepancies with detailed context (row index, state values, expected vs actual)

**Discrepancy reporting**:
- Row index and timestamp
- Input values (bid, ask)
- State values before discrepancy
- Expected output from reference
- Actual output from vectorized
- Difference magnitude
- Potential root cause analysis

---

## Edge Cases

### Test Scenarios

**Empty input DataFrame**:
- Input: DataFrame with zero rows
- Expected: No errors, empty output DataFrame
- Validation: Output structure matches input structure

**Single-row input**:
- Input: DataFrame with one tick
- Expected: No previous row access, initialization only
- Validation: No errors, reasonable state initialization

**First-row behavior**:
- Input: First tick of a session
- Expected: No previous_bid, no previous_trend
- Validation: Proper handling of missing previous values

**Duplicate timestamps (same millisecond)**:
- Input: Multiple rows with identical datetime
- Expected: Each row processed independently, order preserved
- Validation: State updates respect row order within same timestamp

**Multiple rows at same second (different milliseconds)**:
- Input: Multiple rows within same second but different milliseconds
- Expected: Same bar_time for all, different processing order
- Validation: Bar boundary detection works correctly

**Multiple brokers in same DataFrame**:
- Input: Rows from multiple brokers
- Expected: State isolated per broker
- Validation: No cross-broker state contamination

**Multiple symbols in same DataFrame**:
- Input: Rows from multiple symbols
- Expected: State isolated per symbol
- Validation: No cross-symbol state contamination

**Multiple (broker, symbol) groups**:
- Input: Rows from multiple broker-symbol combinations
- Expected: State isolated per group
- Validation: Groupby operations work correctly

**State isolation between groups**:
- Input: Interleaved rows from different groups
- Expected: Each group maintains independent state
- Validation: No state leakage between groups

**Day/session boundaries**:
- Input: Ticks spanning multiple days
- Expected: State reinitialized at day boundary
- Validation: Day boundary detection and reinitialization

**State reset conditions**:
- Input: Ticks triggering various reset conditions
- Expected: Proper state reset at boundaries
- Validation: Reset logic matches reference

**Threshold transitions**:
- Input: Ticks crossing trend thresholds, zone boundaries
- Expected: Proper state transitions at exact thresholds
- Validation: Transition logic handles boundary conditions

**Boundary conditions**:
- Input: Price exactly at zone boundary
- Expected: Correct engagement/disengagement behavior
- Validation: Boundary comparison logic (inclusive/exclusive)

**End-of-stream behavior**:
- Input: Last row of DataFrame
- Expected: Proper finalization, no incomplete state
- Validation: Final state is consistent and valid

**Zone priority variations**:
- Input: Zones with priority 1 and 2
- Expected: Different usage limits based on priority
- Validation: Priority-based logic works correctly

**Pullback window expiration**:
- Input: Pullback windows beyond bar_offset > 5
- Expected: Windows deactivated and removed
- Validation: Expiration logic matches reference

**Reversal usage limit exhaustion**:
- Input: Multiple reversals in same zone
- Expected: Reversals blocked after limit (2 for priority 1, 1 for priority 2)
- Validation: Usage limit enforcement

**Pullback usage limit exhaustion**:
- Input: Multiple pullbacks in same zone
- Expected: Pullbacks blocked after limit (1 for priority 2)
- Validation: Usage limit enforcement

### Validation Approach

For each edge case:
1. Create specific test fixture with minimal but representative data
2. Document expected behavior based on reference implementation
3. Run both implementations
4. Verify behavior matches expected semantics
5. Document any differences in implementation approach
6. If differences are acceptable, document rationale

---

## Determinism

### Requirement

Repeated execution with the same input must produce the same result.

### Validation Approach

**Fixed seeds**:
- If any random operations are used, set fixed seed
- Document all sources of randomness
- Ensure reproducibility across runs

**External dependencies**:
- Mock or control all external dependencies
- Use deterministic data sources for zones, history, etc.
- Ensure no hidden non-determinism (e.g., hash-based ordering)

**Repeated execution test**:
- Run the same input multiple times
- Verify identical output each time
- Check for any variation in results

**Non-determinism detection**:
- Check for operations that may introduce non-determinism:
  - Dictionary iteration order (Python < 3.7)
  - Set operations
  - Hash-based data structures
  - Parallel execution without ordering guarantees
- Document and mitigate any found

---

## Regression Tests

### Location

`tests/application/xauusd_trading_strategy_1_vector/`

### Test Structure

**test_vectorization_correctness.py**:
- Main comparison tests against reference implementation
- Tests for all major calculation paths
- Tests for all signal families
- Tests for state trajectory matching

**test_edge_cases.py**:
- Edge case-specific tests
- One test per edge case scenario
- Minimal fixtures focused on specific behavior

**test_state_isolation.py**:
- Multi-broker/symbol isolation tests
- Tests for groupby correctness
- Tests for state leakage prevention

**fixtures/**:
- Deterministic input fixtures (CSV or Parquet)
- Fixture naming: `{scenario}_{description}.parquet`
- Fixture metadata file documenting expected behavior

### Test Coverage

**Major calculation paths**:
- Trend calculation and state updates
- Reference high/low calculation
- Candle array rolling
- Zone engagement updates
- Breakout validation
- Reversal directional touch
- Pullback penetration check
- Pullback window lifecycle
- Risk calculations (stop loss, take profit, portfolio, concurrency)

**Signal families**:
- Breakout signals (BUY and SELL)
- Reversal signals (BUY and SELL)
- Pullback signals (BUY and SELL)

**State transitions**:
- Day boundary reinitialization
- Bar boundary behavior
- Engagement reset at bar open
- Pullback window creation and expiration

**Risk calculation paths**:
- Initial stop loss calculation
- Initial take profit calculation
- Portfolio risk check
- Concurrency check
- Margin check (if external data available)

**All edge cases listed above**

### Regression Criteria

**Action column**:
- Must match reference implementation exactly
- No missing actions
- No extra actions
- Correct action type and timing

**State trajectories**:
- Must match reference implementation at all ticks
- Trend state must match
- Zone engagement must match
- Pullback windows must match (creation, lifecycle, removal)

**Signal candidates**:
- Must match reference implementation
- Correct timing (tick index)
- Correct type (family)
- Correct direction
- Correct zone association
- Correct parameters (entry price, etc.)

**State isolation**:
- No cross-group state contamination
- Independent state per (broker, symbol)
- Correct groupby behavior

**Any deviation**:
- Must be explained with detailed analysis
- Must be accepted as intentional difference
- Must be documented with rationale

---

## Performance Benchmarking

### Objective

Measure performance improvement of vectorized implementation over event-loop.

### Metrics

**Execution time**:
- Total execution time for fixed input size
- Time per major phase (trend, engagement, signals, etc.)
- Cold start vs warm start performance

**Memory usage**:
- Peak memory allocation
- Memory per row
- Memory growth rate with input size

**Throughput**:
- Rows processed per second
- Ticks processed per second
- Scaling behavior with input size

### Benchmark Approach

**Input sizes**:
- Small: 10K ticks
- Medium: 100K ticks
- Large: 1M ticks
- Very large: 10M ticks (if feasible)

**Measurement**:
- Use time.perf_counter() for precise timing
- Measure memory with memory_profiler or similar
- Run each benchmark multiple times and average
- Exclude fixture loading time from measurements

**Profiling**:
- Use cProfile or similar to identify bottlenecks
- Profile major functions separately
- Identify hot paths for optimization

**Success criteria**:
- Vectorized implementation should be significantly faster than event-loop (target: 10-100x)
- Memory usage should be reasonable for expected input sizes (target: < 1GB for 1M ticks)
- Performance should scale linearly with input size (O(n) complexity)

### Optimization Targets

Based on profiling results:
- Identify top 3 bottlenecks
- Optimize vectorized operations
- Consider Numba for sequential parts
- Optimize memory allocation patterns
- Reduce intermediate DataFrame copies

---

## Implementation Validation Checklist

### Correctness

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

### Performance

- [ ] Performance benchmarks meet expectations
- [ ] Memory usage is reasonable
- [ ] Scaling is linear with input size
- [ ] No memory leaks detected
- [ ] No performance regressions over time

### Testing

- [ ] Regression tests pass consistently
- [ ] Edge case tests pass consistently
- [ ] State isolation tests pass consistently
- [ ] Determinism tests pass consistently
- [ ] Test coverage is comprehensive

### Documentation

- [ ] Documentation is complete and accurate
- [ ] Code is well-commented
- [ ] API documentation is clear
- [ ] Implementation notes are documented
- [ ] Known limitations are documented

---

## Test Data Management

### Fixture Storage

**Format**: Parquet (efficient, preserves types)

**Location**: `tests/fixtures/xauusd_vectorization/`

**Naming convention**: `{scenario}_{description}_{size}.parquet`

**Metadata**: JSON file alongside each fixture documenting:
- Input description
- Expected output summary
- Reference implementation version
- Date created

### Fixture Categories

**Minimal fixtures**: Small datasets for specific edge cases
- `empty.parquet`: Empty DataFrame
- `single_row.parquet`: One tick
- `duplicate_timestamps.parquet`: Same millisecond
- `day_boundary.parquet`: Spans day boundary

**Realistic fixtures**: Larger datasets with realistic market data
- `session_10k.parquet`: 10K ticks from real session
- `session_100k.parquet`: 100K ticks from real session
- `multi_broker.parquet`: Multiple brokers
- `multi_symbol.parquet`: Multiple symbols

**Stress fixtures**: Large datasets for performance testing
- `stress_1m.parquet`: 1M ticks
- `stress_10m.parquet`: 10M ticks (if feasible)

### Fixture Versioning

- Include reference implementation version in metadata
- Update fixtures when reference implementation changes
- Maintain backward compatibility where possible
- Document breaking changes

---

## Continuous Validation

### CI Integration

**Automated tests**:
- Run regression tests on every commit
- Run edge case tests on every commit
- Run performance benchmarks weekly

**Failure handling**:
- Block merge if regression tests fail
- Alert if performance degrades beyond threshold
- Investigate and fix failures before proceeding

### Monitoring

**Performance metrics**:
- Track execution time over time
- Track memory usage over time
- Alert on performance regressions

**Correctness metrics**:
- Track test pass rate
- Track flaky tests
- Investigate and fix flakiness

---

## Known Limitations and Future Work

### Current Limitations

**Ports/Adapters**: The vectorized implementation does not include the external ports (load_raw_zones, process_candidates, etc.). These are mocked for testing but will need real implementations for production use.

**Risk state**: Portfolio risk, open positions, and margin state are external dependencies. The vectorized implementation assumes these are provided as input columns or through a separate mechanism.

**Execution state**: Order execution, position management, and trade outcomes are not part of the signal generation logic. These are handled by separate execution infrastructure.

### Future Work

**Real-time processing**: Adapt the vectorized implementation for streaming/real-time processing with incremental state updates.

**Multi-timeframe support**: Extend to support multiple timeframes (e.g., M1, M5, H1) with appropriate state management.

**Parameter optimization**: Add support for parameter optimization and backtesting with vectorized evaluation.

**Production integration**: Integrate with real MT5 infrastructure for live trading (after thorough testing and validation).
