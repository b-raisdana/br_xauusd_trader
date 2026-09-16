# Test Plan: on_init.py Numba Compatibility Extraction

## Objective

Validate that extracting `nearly_equal()` to a `@njit`-compiled numerical module preserves behavior and integrates correctly with smoke tests.

## Scope

- New file: `src/application/xauusd_trading_strategy_1/numerical.py`
- Modified: `src/application/xauusd_trading_strategy_1/smoke.py` (import change)
- Unchanged: `on_init.py`, `lifecycle.py`, `settings.py` (documented as impossible)

## Test Data

No external test data needed. Tests use inline float values covering:
- Exact equality
- Within tolerance
- Outside tolerance
- Edge cases: zero, negative, very small numbers, large numbers

## Test Cases

### Unit Tests for `numerical.nearly_equal`

| Test | left | right | tolerance | Expected |
|------|------|-------|-----------|----------|
| exact_equal | 1.0 | 1.0 | 1e-9 | True |
| within_tolerance | 1.0 | 1.0000000001 | 1e-9 | True |
| outside_tolerance | 1.0 | 1.0000001 | 1e-9 | False |
| zero_comparison | 0.0 | 1e-10 | 1e-9 | True |
| negative_values | -100.0 | -100.000000001 | 1e-9 | True |
| large_values | 1e10 | 1e10 + 1 | 1e-9 | False (relative) |
| custom_tolerance | 1.0 | 1.1 | 0.2 | True |
| custom_tolerance_fail | 1.0 | 1.1 | 0.05 | False |

### Integration Tests

1. **Smoke test still passes** - Run existing `run_core_vector_smoke()` and verify all vector validations still produce expected `SmokeResult` outcomes
2. **No behavioral change** - Compare smoke test results before/after extraction
3. **Numba compilation** - Verify `@njit` function compiles without falling back to object mode

## Environment

```powershell
.\.venv\Scripts\python.exe -c "import numba; print(numba.__version__)"
.\.venv\Scripts\python.exe -c "from src.application.xauusd_trading_strategy_1.numerical import nearly_equal; print(nearly_equal(1.0, 1.0))"
```

Expected: Numba 0.59+ (compatible with project), function returns `True`

## Approach

1. Create `numerical.py` with `@njit` decorated `nearly_equal`
2. Update `smoke.py` to import from `.numerical`
3. Run targeted pytest on smoke tests
4. Run full pre-commit gate
5. Verify vectorbt integration tests still pass (if any use smoke)

## Acceptance Criteria

- [ ] `numerical.py` created with `@njit` function
- [ ] `smoke.py` imports and uses `numerical.nearly_equal`
- [ ] All existing smoke test vectors pass (230-line validation in `run_core_vector_smoke`)
- [ ] Unit tests for `nearly_equal` pass with edge cases
- [ ] Pre-commit passes (ruff-check, ruff-format, pytest)
- [ ] No performance regression (Numba should be faster or equal for repeated calls)
- [ ] Documentation in `on_init_numba_compatibility.md` updated with final status

## Risk Mitigation

- If Numba compilation fails (e.g., version incompatibility), keep Python fallback
- Test with `NUMBA_DISABLE_JIT=1` to verify Python fallback path works
- Ensure `nearly_equal` signature matches exactly (defaults, types)