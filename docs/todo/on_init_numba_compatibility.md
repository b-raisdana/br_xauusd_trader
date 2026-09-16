# Task: Make on_init.py Numba Compatible

## Objective

Analyze and refactor `src/application/xauusd_trading_strategy_1/on_init.py` to use `@njit` where feasible, documenting what is truly impossible due to Numba limitations.

## Scope

- `src/application/xauusd_trading_strategy_1/on_init.py`
- Related: `smoke.py`, `lifecycle.py`, `settings.py`
- Domain functions called from smoke tests

## Current State Analysis

### on_init.py Functions

| Function | Numba Feasibility | Reason |
|----------|-------------------|--------|
| `DefaultSmokeSuite.run_all()` | ❌ Impossible | Returns tuple of custom `SmokeResult` dataclass objects |
| `validate_initialization_settings()` | ❌ Impossible | Uses Pydantic `StrategySettings`, string building, attribute access on objects |
| `on_init()` | ❌ Impossible | Instantiates `RuntimeEnvironment`, `DefaultSmokeSuite`, `OnInitResult` dataclasses; protocol dispatch |

### smoke.py Functions

| Function | Numba Feasibility | Reason |
|----------|-------------------|--------|
| `nearly_equal()` | ✅ Possible | Pure float comparison, no allocations |
| `run_core_vector_smoke()` | ❌ Impossible | Creates `XauZone` objects, calls domain functions with enums, string error messages, exception handling |

### lifecycle.py Types

All dataclasses (`Tick`, `RuntimeEnvironment`, `SmokeResult`, `OnInitResult`, `OnTickResult`) and Protocols (`SmokeSuite`, `EventLoop`) are ❌ Impossible - Numba does not support Python classes, dataclasses, or Protocols.

### settings.py

`StrategySettings` (Pydantic BaseModel) is ❌ Impossible - Numba has no Pydantic support.

## What CAN Be Numba-Compatible

Only isolated, pure numerical helper functions with:
- Primitive inputs (int, float, bool)
- Primitive outputs
- No allocations, no strings, no exceptions
- No external function calls except other @njit functions

Candidate: `nearly_equal()` in smoke.py

## Approach

1. Extract `nearly_equal()` to a separate numerical utilities module with `@njit`
2. Document all other functions as "truly impossible" with specific Numba limitation reasons
3. Create a numba-compatible validation shim for smoke test numerical comparisons only
4. Keep main initialization logic in Python (correct architectural boundary)

## Acceptance Criteria

- [ ] `nearly_equal()` extracted to `src/application/xauusd_trading_strategy_1/numerical.py` with `@njit`
- [ ] `smoke.py` imports and uses the njit version
- [ ] Documentation in this file updated with final status
- [ ] Pre-commit passes (ruff, pytest)
- [ ] No behavioral changes to on_init/smoke logic