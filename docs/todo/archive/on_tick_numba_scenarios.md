# Scenarios: on_tick.py Numba Compatibility Analysis

## Numba Constraint Summary

Numba `@njit` (nopython mode) supports:
- Primitive types (int, float, bool, complex)
- NumPy arrays and basic slicing
- Simple loops, conditionals, math operations
- `@njit` functions calling other `@njit` functions
- Limited string support (fixed-length, no formatting)
- No Python objects, classes, dataclasses, dicts, sets
- No exceptions with custom messages
- No Pydantic, no Protocols, no dataclasses
- No dynamic attribute access (`getattr`, `hasattr`)
- No closures capturing Python objects
- No `datetime` objects
- No mutable lists of heterogeneous types

## Function-by-Function Analysis

### on_tick.py

#### `process_current_event_loop_tick()`
```python
def process_current_event_loop_tick(
    tick: Tick,
    event_loop: EventLoop,
) -> bool:
    return event_loop.process_tick(tick)
```
**Verdict: ❌ IMPOSSIBLE**
- Takes `ProceduralTick` (dataclass with `datetime`) and `EventLoop` (Protocol)
- Protocol dispatch (`event_loop.process_tick`) - Numba has no Protocol/interface support
- Calls arbitrary Python method on unknown object
- Returns `bool` but the computation happens in Python land

#### `on_tick()`
```python
def on_tick(
    tick: Tick,
    settings: StrategySettings,
    strategy_runtime: StrategyRuntimeState,
    environment: RuntimeEnvironment | None = None,
    event_loop: EventLoop | None = None,
) -> OnTickResult:
    if environment is None:
        environment = RuntimeEnvironment()
    probe_emitted = False
    if settings.emit_time_basis_probe and strategy_runtime.time_basis_probe_count < 5 and tick.is_valid:
        strategy_runtime.time_basis_probe_count += 1
        probe_emitted = True
    # ... gate checks, mutation, exception handling, dataclass construction
```
**Verdict: ❌ IMPOSSIBLE (as written)**
- **Parameters**: All are Python objects Numba cannot natively handle:
  - `ProceduralTick` - dataclass with `datetime` field
  - `StrategySettings` - Pydantic BaseModel
  - `StrategyRuntimeState` - dataclass with 50+ fields including lists, domain objects, strings
  - `RuntimeEnvironment` - dataclass
  - `EventLoop` - Protocol
- **Mutations**: `strategy_runtime.time_basis_probe_count += 1`, `strategy_runtime.event_loop_failure_reported = True` - Numba cannot mutate Python dataclass fields
- **Attribute access**: `settings.emit_time_basis_probe`, `strategy_runtime.time_basis_probe_count`, `tick.is_valid` - dynamic attribute access on arbitrary objects
- **Control flow**: Optional parameters with default instantiation, exception handling (`try/except Exception`)
- **Returns**: `OnTickResult` dataclass with heterogeneous fields
- **Protocol dispatch**: `event_loop.process_tick(tick)` via `process_current_event_loop_tick()`

### global_state_variable.py

#### `StrategyRuntimeState`
```python
@dataclass(slots=True)
class StrategyRuntimeState:
    time_basis_probe_count: int = 0
    execution_projections: list[XauExecutionProjection] = field(default_factory=list)
    execution_bindings: list[XauExecutionBinding] = field(default_factory=list)
    runtime_requests: list[XauRuntimeRequest] = field(default_factory=list)
    execution_bindings_file: str = r"XAUUSD_Current\bindings.tsv"
    order_audit_file: str = r"XAUUSD_Current\orders.jsonl"
    market_state: XauMarketCoordinator = field(default_factory=XauMarketCoordinator)
    current_bar_time: int = 0
    event_loop_ready: bool = False
    event_loop_failure_reported: bool = False
    # ... 30 more fields of mixed types
```
**Verdict: ❌ IMPOSSIBLE**
- Dataclass with 50+ fields
- Mixed types: int, float, bool, str, list[domain_object], domain_object
- `XauMarketCoordinator`, `XauExecutionProjection`, `XauExecutionBinding`, `XauRuntimeRequest` are complex domain objects
- Mutable lists with default factories
- File path strings (raw strings with backslashes)
- Numba has no dataclass support, no list of objects, no string paths

### lifecycle.py Types (relevant to on_tick)

#### `ProceduralTick`
```python
@dataclass(frozen=True, slots=True)
class Tick:
    time: datetime
    bid: float
    ask: float

    @property
    def is_valid(self) -> bool:
        return isfinite(self.bid) and isfinite(self.ask) and self.bid > 0.0 and self.ask > 0.0
```
**Verdict: ❌ IMPOSSIBLE**
- `datetime` field - Numba has no datetime support
- Property method - Numba cannot call Python properties
- `math.isfinite` - available in Numba but on Python float objects

#### `RuntimeEnvironment`
```python
@dataclass(frozen=True, slots=True)
class RuntimeEnvironment:
    is_tester: bool = False
```
**Verdict: ❌ IMPOSSIBLE** - Dataclass

#### `OnTickResult`
```python
@dataclass(frozen=True, slots=True)
class OnTickResult:
    handled: bool
    time_basis_probe_emitted: bool = False
    event_loop_failed: bool = False
```
**Verdict: ❌ IMPOSSIBLE** - Dataclass construction/return

#### `EventLoop` Protocol
```python
class EventLoop(Protocol):
    def process_tick(self, tick: Tick) -> bool: ...
```
**Verdict: ❌ IMPOSSIBLE** - Protocol, method taking dataclass

## What CAN Be Numba-Compatible: Pure Numerical Kernels

These can be extracted as `@njit` functions taking **only primitives**:

### 1. Tick Validation
```python
@njit
def tick_is_valid(bid: float, ask: float) -> bool:
    return (bid > 0.0) and (ask > 0.0) and isfinite(bid) and isfinite(ask)
```
- Pure float logic
- `math.isfinite` supported in Numba

### 2. Probe Emission Logic
```python
@njit
def should_emit_probe(emit_flag: bool, probe_count: int, tick_valid: bool, max_probes: int = 5) -> bool:
    return emit_flag and tick_valid and (probe_count < max_probes)
```
- Pure bool/int logic

### 3. Probe Count Increment
```python
@njit
def increment_probe_count(probe_count: int) -> int:
    return probe_count + 1
```
- Trivial but explicit

### 4. Gate Checks
```python
@njit
def should_run_event_loop(run_flag: bool) -> bool:
    return run_flag

@njit
def event_loop_failed(handled: bool) -> bool:
    return not handled
```
- Pure bool logic

## Architectural Pattern: Numerical Kernel + Python Orchestration

### Recommended Structure

**`numerical.py`** (Numba-compatible):
```python
from numba import njit
from math import isfinite

@njit
def tick_is_valid(bid: float, ask: float) -> bool:
    return (bid > 0.0) and (ask > 0.0) and isfinite(bid) and isfinite(ask)

@njit
def should_emit_probe(emit_flag: bool, probe_count: int, tick_valid: bool, max_probes: int = 5) -> bool:
    return emit_flag and tick_valid and (probe_count < max_probes)

@njit
def increment_probe_count(probe_count: int) -> int:
    return probe_count + 1
```

**`on_tick.py`** (Python orchestration, calls numerical kernels):
```python
from .numerical import tick_is_valid, should_emit_probe, increment_probe_count

def on_tick(...) -> OnTickResult:
    # Extract primitives from objects
    bid, ask = tick.bid, tick.ask
    emit_flag = settings.emit_time_basis_probe
    probe_count = strategy_runtime.time_basis_probe_count
    
    # Call numerical kernels
    tick_valid = tick_is_valid(bid, ask)
    probe_emitted = should_emit_probe(emit_flag, probe_count, tick_valid)
    
    if probe_emitted:
        strategy_runtime.time_basis_probe_count = increment_probe_count(probe_count)
    
    # ... rest of Python orchestration (gate checks, mutations, event loop dispatch, result construction)
```

## Why This Is the Correct Boundary

1. **on_tick() runs per tick** - but the hot path is the event loop processing, not the gate checks
2. **Gate checks are trivial** - a few boolean ops, not worth Numba overhead
3. **Event loop is the real computation** - `event_loop.process_tick()` does the work; it should be Numba-optimized if it's numerical
4. **Data structure conversion cost** - extracting primitives from dataclasses/Pydantic each tick adds overhead
5. **Orchestration vs computation** - on_tick is orchestration (routing, state mutation, protocol dispatch); numerical kernels are computation

## Recommendation

1. **Extract numerical kernels** to `numerical.py` with `@njit`:
   - `tick_is_valid(bid, ask)`
   - `should_emit_probe(emit_flag, probe_count, tick_valid)`
   - `increment_probe_count(probe_count)`

2. **Refactor on_tick.py** to extract primitives and call kernels

3. **Focus Numba effort on EventLoop implementations** - the actual tick processing logic in `process_tick()` methods is where numerical computation happens

4. **Document all on_tick.py functions/types as impossible** with specific Numba limitation reasons

5. **Keep orchestration in Python** - correct architectural boundary