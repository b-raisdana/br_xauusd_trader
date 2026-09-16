# Task: Make on_tick.py Numba Compatible

## Objective

Analyze and refactor `src/application/xauusd_trading_strategy_1/on_tick.py` to use `@njit` where feasible, documenting what is truly impossible due to Numba limitations.

## Scope

- `src/application/xauusd_trading_strategy_1/on_tick.py`
- Related: `global_state_variable.py`, `lifecycle.py`, `settings.py`
- Domain: `EventLoop` protocol implementations

## Current State Analysis

### on_tick.py Functions

| Function | Numba Feasibility | Reason |
|----------|-------------------|--------|
| `process_current_event_loop_tick()` | ❌ Impossible | Protocol dispatch (`event_loop.process_tick`), returns `bool` but calls Python object method |
| `on_tick()` | ❌ Impossible | Uses `StrategySettings` (Pydantic), `StrategyRuntimeState` (dataclass with complex fields), `RuntimeEnvironment` (dataclass), `Tick` (dataclass with datetime), constructs `OnTickResult` dataclass, mutates runtime state, exception handling |

### global_state_variable.py

`StrategyRuntimeState` dataclass - ❌ Impossible
- 50+ fields of mixed types (int, float, bool, list, strings, domain objects)
- `XauMarketCoordinator`, `XauExecutionProjection`, `XauExecutionBinding`, `XauRuntimeRequest` domain objects
- Mutable lists with default factories
- File path strings
- Numba cannot handle dataclasses, lists of objects, or complex nested structures

### lifecycle.py Types (from on_init analysis)

All ❌ Impossible:
- `Tick` - dataclass with `datetime` field
- `RuntimeEnvironment` - dataclass
- `OnTickResult` - dataclass
- `EventLoop` - Protocol
- `OnInitResult`, `SmokeResult`, `OnInitStatus`, `SmokeSuite` - not used here but also impossible

### settings.py

`StrategySettings` (Pydantic BaseModel) - ❌ Impossible

## What CAN Be Numba-Compatible

The on_tick hot path is fundamentally about:
1. Tick validation (bid/ask finite, positive)
2. Probe counting (integer increment, comparison)
3. Boolean gate checks
4. Delegating to event loop

**However**, the data structures passed in (`Tick`, `StrategySettings`, `StrategyRuntimeState`, `RuntimeEnvironment`) are all Python objects that Numba cannot natively consume or produce.

### Feasible Approach: Numerical Kernel Extraction

Extract pure numerical predicates to `@njit` functions:
- `tick_is_valid(bid: float, ask: float) -> bool`
- `should_emit_probe(emit_flag: bool, probe_count: int, tick_valid: bool) -> bool`
- `increment_probe_count(probe_count: int) -> int` (or just `probe_count + 1`)

The main `on_tick()` remains Python (correct architectural boundary - it's orchestration, not computation).

## Approach

1. Create `src/application/xauusd_trading_strategy_1/numerical.py` with `@njit` tick validation and probe logic
2. Refactor `on_tick.py` to use numerical kernels where possible (passing primitives, not objects)
3. Document all other functions/types as "truly impossible" with specific reasons
4. Keep orchestration in Python

## Acceptance Criteria

- [ ] `numerical.py` has `@njit` functions for tick validation, probe logic
- [ ] `on_tick.py` uses numerical kernels (passing primitives extracted from objects)
- [ ] All existing tests pass (vectorbt integration, pytest)
- [ ] Pre-commit passes (ruff, pytest)
- [ ] No behavioral changes to on_tick logic
- [ ] Documentation updated with final status