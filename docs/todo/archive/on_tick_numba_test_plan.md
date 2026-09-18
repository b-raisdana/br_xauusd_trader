# Test Plan: on_tick.py Numba Numerical Kernel Extraction

## Objective

Validate that extracting pure numerical predicates from `on_tick.py` to `@njit`-compiled functions in `numerical.py` preserves behavior and integrates correctly.

## Scope

- New/Modified: `src/application/xauusd_trading_strategy_1/numerical.py` (add tick validation, probe logic)
- Modified: `src/application/xauusd_trading_strategy_1/on_tick.py` (use numerical kernels)
- Unchanged: `global_state_variable.py`, `lifecycle.py`, `settings.py` (documented as impossible)

## Test Data

Inline test values covering edge cases for tick validation and probe logic.

## Test Cases

### Unit Tests for `numerical` Module

#### `tick_is_valid(bid, ask)`

| Test | bid | ask | Expected |
|------|-----|-----|----------|
| valid_normal | 2350.5 | 2350.7 | True |
| valid_tight_spread | 2350.0 | 2350.01 | True |
| zero_bid | 0.0 | 2350.5 | False |
| zero_ask | 2350.5 | 0.0 | False |
| negative_bid | -1.0 | 2350.5 | False |
| negative_ask | 2350.5 | -1.0 | False |
| nan_bid | NaN | 2350.5 | False |
| nan_ask | 2350.5 | NaN | False |
| inf_bid | Inf | 2350.5 | False |
| inf_ask | 2350.5 | Inf | False |
| both_nan | NaN | NaN | False |
| very_small_positive | 1e-10 | 1e-10 | True |

#### `should_emit_probe(emit_flag, probe_count, tick_valid, max_probes=5)`

| Test | emit_flag | probe_count | tick_valid | max_probes | Expected |
|------|-----------|-------------|------------|------------|----------|
| emit_enabled_first | True | 0 | True | 5 | True |
| emit_enabled_middle | True | 2 | True | 5 | True |
| emit_enabled_at_limit | True | 4 | True | 5 | True |
| emit_enabled_over_limit | True | 5 | True | 5 | False |
| emit_disabled | False | 0 | True | 5 | False |
| tick_invalid | True | 0 | False | 5 | False |
| custom_max_probes | True | 3 | True | 3 | False |
| custom_max_probes_ok | True | 2 | True | 3 | True |

#### `increment_probe_count(probe_count)`

| Test | probe_count | Expected |
|------|-------------|----------|
| zero | 0 | 1 |
| positive | 3 | 4 |
| at_limit | 4 | 5 |

### Integration Tests

1. **on_tick behavior unchanged** - Run existing vectorbt integration tests (`tests/test_on_tick_vectorbt.py`) and verify identical `OnTickResult` outputs for same inputs
2. **Probe emission count** - Verify `time_basis_probe_emitted=True` for first 5 valid ticks when `emit_time_basis_probe=True`
3. **Event loop gating** - Verify `run_current_event_loop=False` returns `handled=True` without calling event loop
4. **Event loop failure** - Verify `event_loop=None` returns `event_loop_failed=True` after first failure
5. **Exception isolation** - Verify event loop exceptions caught and reported via `event_loop_failed=True`

### Numba Compilation Tests

1. **Import succeeds** - `from src.application.xauusd_trading_strategy_1.numerical import tick_is_valid`
2. **JIT compiles** - Function shows `.compile()` or `.nopython_signatures` populated
3. **No object mode fallback** - Verify `NUMBA_DISABLE_JIT=1` doesn't change results
4. **Performance** - Microbenchmark: 1M calls to `tick_is_valid` should be faster than Python equivalent

## Environment

```powershell
.\.venv\Scripts\python.exe -c "import numba; print(numba.__version__)"
.\.venv\Scripts\python.exe -c "from src.application.xauusd_trading_strategy_1.numerical import tick_is_valid; print(tick_is_valid(2350.5, 2350.7))"
```

Expected: Numba 0.59+, function returns `True`

## Approach

1. Add `@njit` functions to `numerical.py` (or create if not exists)
2. Refactor `on_tick.py` to extract primitives and call numerical kernels
3. Run targeted pytest on on_tick tests
4. Run vectorbt integration tests
5. Run full pre-commit gate
6. Verify no behavioral changes

## Acceptance Criteria

- [ ] `numerical.py` has `@njit` functions: `tick_is_valid`, `should_emit_probe`, `increment_probe_count`
- [ ] `on_tick.py` imports and uses numerical kernels (extracts primitives from objects)
- [ ] All existing vectorbt integration tests pass (`tests/test_on_tick_vectorbt.py`)
- [ ] Unit tests for numerical kernels pass with edge cases
- [ ] Pre-commit passes (ruff-check, ruff-format, pytest)
- [ ] No behavioral changes to on_tick logic (same OnTickResult for same inputs)
- [ ] Numba compiles without object mode fallback
- [ ] Documentation in `on_tick_numba_compatibility.md` updated with final status

## Risk Mitigation

- If Numba compilation fails, keep Python fallback in `numerical.py`:
  ```python
  try:
      from numba import njit
      @njit
      def tick_is_valid(...): ...
  except ImportError:
      def tick_is_valid(...): ...  # Python fallback
  ```
- Test with `NUMBA_DISABLE_JIT=1` to verify fallback path
- Ensure kernel signatures match exactly (types, defaults)
- Vectorbt integration test is the ultimate behavioral contract