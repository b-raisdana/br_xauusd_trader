# Scenarios: on_init.py Numba Compatibility Analysis

## Numba Constraint Summary

Numba `@njit` (nopython mode) supports:
- Primitive types (int, float, bool, complex)
- NumPy arrays and basic slicing
- Simple loops, conditionals, math operations
- `@njit` functions calling other `@njit` functions
- Limited string support (fixed-length, no formatting, no f-strings)
- No Python objects, classes, dataclasses, dicts, sets
- No exceptions with custom messages
- No Pydantic, no Protocols, no dataclasses
- No dynamic attribute access (`getattr`, `hasattr`)
- No closures capturing Python objects
- No `tuple` of heterogeneous types (only homogeneous)

## Function-by-Function Analysis

### on_init.py

#### `DefaultSmokeSuite.run_all()`
```python
def run_all(self) -> tuple[SmokeResult, ...]:
    return (run_core_vector_smoke(),)
```
**Verdict: ❌ IMPOSSIBLE**
- Returns `tuple[SmokeResult, ...]` - `SmokeResult` is a dataclass
- Calls `run_core_vector_smoke()` which returns dataclass
- Numba cannot construct or return Python dataclass instances

#### `validate_initialization_settings()`
```python
def validate_initialization_settings(
    settings: StrategySettings,
    environment: RuntimeEnvironment,
) -> tuple[str, ...]:
    errors: list[str] = []
    if settings.enable_trading:
        errors.append("live trading is not implemented or approved")
    # ... more string appends, attribute access
    return tuple(errors)
```
**Verdict: ❌ IMPOSSIBLE**
- Takes `StrategySettings` (Pydantic model) and `RuntimeEnvironment` (dataclass)
- Builds `list[str]` dynamically - Numba lists only support homogeneous numeric types
- String literals with dynamic appends - Numba strings are fixed-size, no `.append()`
- Attribute access on arbitrary objects (`settings.enable_trading`, `environment.is_tester`)
- Returns `tuple[str, ...]` - heterogeneous tuple of strings

#### `on_init()`
```python
def on_init(
    settings: StrategySettings,
    environment: RuntimeEnvironment | None = None,
    smoke_suite: SmokeSuite | None = None,
) -> OnInitResult:
    if environment is None:
        environment = RuntimeEnvironment()
    errors = validate_initialization_settings(settings, environment)
    if errors:
        return OnInitResult(status=OnInitStatus.FAILED, errors=errors)
    # ... protocol dispatch, dataclass construction
```
**Verdict: ❌ IMPOSSIBLE**
- Optional parameters with default instantiation (`RuntimeEnvironment()`)
- Calls `validate_initialization_settings()` (impossible)
- Protocol dispatch (`smoke_suite.run_all()`) - Numba has no Protocol support
- Constructs `OnInitResult` dataclass with heterogeneous fields
- Returns `OnInitResult` dataclass instance

### smoke.py

#### `nearly_equal()`
```python
def nearly_equal(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return abs(left - right) <= tolerance
```
**Verdict: ✅ FULLY COMPATIBLE**
- Pure float arithmetic
- Primitive inputs and output
- No allocations, no side effects
- Perfect candidate for `@njit`

#### `run_core_vector_smoke()`
```python
def run_core_vector_smoke(vectors: CoreVectors = core_vectors) -> SmokeResult:
    try:
        breakout_zone = XauZone(id="2026-09-06:R1", low=..., high=...)
        if not breakout_valid(...):
            return SmokeResult("core_vectors", False, "breakout")
        # ... 200+ lines of domain function calls, enum usage, string errors
    except Exception as exc:
        return SmokeResult("core_vectors", False, str(exc))
```
**Verdict: ❌ IMPOSSIBLE**
- Creates `XauZone` dataclass instances
- Uses enums (`XauDirection.BUY`, `XauTrend.UP`) - Numba has no enum support
- Calls domain functions that use enums, dataclasses, complex logic
- String error messages ("breakout", "reversal", etc.)
- Exception handling with `str(exc)` - Numba exceptions cannot carry custom messages
- Returns `SmokeResult` dataclass
- Dynamic `getattr(vectors, f"vec_risk_zone_{index}_low")` - impossible in Numba

### lifecycle.py Types

All are ❌ IMPOSSIBLE:
- `ProceduralTick` - dataclass with `datetime` field
- `RuntimeEnvironment` - dataclass
- `OnInitStatus` - IntEnum (Numba has no enum support)
- `SmokeResult` - dataclass with string fields
- `SmokeSuite` - Protocol
- `EventLoop` - Protocol
- `OnInitResult` - dataclass with tuple[str, ...] field
- `OnTickResult` - dataclass

### settings.py

`StrategySettings` (Pydantic BaseModel) - ❌ IMPOSSIBLE
- Pydantic validation, frozen config, field constraints
- No Numba equivalent exists

## Feasible Extraction

Only `nearly_equal()` can be made `@njit` compatible.

### Proposed Extraction

Create `src/application/xauusd_trading_strategy_1/numerical.py`:
```python
from numba import njit

@njit
def nearly_equal(left: float, right: float, tolerance: float = 1e-9) -> bool:
    return abs(left - right) <= tolerance
```

Then in `smoke.py`:
```python
from .numerical import nearly_equal
```

## Architectural Conclusion

The initialization/smoke validation layer is **architecturally wrong** for Numba optimization. This code:
- Runs once at startup
- Does configuration validation
- Exercises domain logic for correctness checking
- Is not a hot path

Numba should target `on_tick.py` tick processing loop and domain mathematical functions, not initialization code.

## Recommendation

1. Extract `nearly_equal()` to numerical.py with `@njit` ✅
2. Document all other functions as "truly impossible" with specific reasons ✅
3. Focus Numba efforts on `on_tick.py` and domain mathematical functions instead
4. Keep on_init.py as Python - correct architectural boundary