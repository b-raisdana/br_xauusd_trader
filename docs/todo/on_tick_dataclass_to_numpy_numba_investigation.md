# Investigation: Dataclass to NumPy Conversion for Numba Compatibility

## Question

Would converting/mapping/casting classes like `RuntimeEnvironment` (dataclass) to NumPy arrays/series allow more usage of Numba `@njit`?

## Short Answer: NO

Converting dataclasses to NumPy arrays does **not** enable Numba compatibility for the functions in `on_tick.py`. The fundamental limitation is not the data structure format—it's that **Numba's nopython mode cannot accept Python objects at function boundaries**.

---

## Detailed Analysis

### Why NumPy Conversion Doesn't Help

| Aspect | Explanation |
|--------|-------------|
| **Function boundary** | `@njit` functions can only receive primitives (`int`, `float`, `bool`, `complex`) and NumPy arrays. A Python function calling `@njit` must extract primitives *before* the call. |
| **Conversion happens in Python** | Converting `RuntimeEnvironment` → `np.ndarray` is a Python operation. The `@njit` function still receives a NumPy array, but the caller must do the conversion. |
| **No pass-through of objects** | You cannot pass a dataclass, Pydantic model, Protocol, `datetime`, or any Python object to `@njit`. NumPy arrays of `dtype=object` are also unsupported. |
| **Numba's typed containers** | `numba.typed.Dict`, `numba.typed.List`, `StructRef` exist but must be created *inside* `@njit` or passed from another `@njit` function. They cannot be constructed from Python objects externally. |

### Current Function Signatures (All Impossible for `@njit`)

```python
# lifecycle.py
@dataclass(frozen=True, slots=True)
class RuntimeEnvironment:
    is_tester: bool = False  # Single bool field

@dataclass(frozen=True, slots=True)
class Tick:
    time: datetime      # ❌ datetime unsupported
    bid: float
    ask: float

# global_state_variable.py
@dataclass(slots=True)
class StrategyRuntimeState:
    # 50+ fields: int, float, bool, str, list[domain_object], domain_object
    time_basis_probe_count: int = 0
    market_state: XauMarketCoordinator = field(default_factory=XauMarketCoordinator)
    # ... many more

# settings.py
class StrategySettings(BaseModel):  # ❌ Pydantic unsupported
    emit_time_basis_probe: bool = False
    run_current_event_loop: bool = False
    # ...

# on_tick.py
def on_tick(
    tick: Tick,
    settings: StrategySettings,
    strategy_runtime: StrategyRuntimeState,
    environment: RuntimeEnvironment | None = None,
    event_loop: EventLoop | None = None,
) -> OnTickResult:  # ❌ Returns dataclass
```

### What NumPy Conversion Would Look Like (And Why It Fails)

```python
# ❌ THIS DOES NOT WORK - conversion is Python-side, @njit still can't receive the dataclass
def on_tick_wrapper(tick, settings, runtime, environment):
    # Convert to numpy arrays in Python
    env_arr = np.array([environment.is_tester], dtype=np.bool_)
    tick_arr = np.array([tick.bid, tick.ask], dtype=np.float64)
    runtime_arr = np.array([runtime.time_basis_probe_count], dtype=np.int64)
    settings_arr = np.array([settings.emit_time_basis_probe], dtype=np.bool_)
    
    # Call @njit with arrays
    return _on_tick_njit(tick_arr, settings_arr, runtime_arr, env_arr)

@njit
def _on_tick_njit(tick_arr, settings_arr, runtime_arr, env_arr):
    # Numba CAN work with arrays, but:
    # 1. The caller had to extract everything manually
    # 2. Mutation of runtime_arr doesn't propagate back to Python object
    # 3. Protocol dispatch (event_loop.process_tick) still impossible
    # 4. Exception handling still impossible
    # 5. OnTickResult construction still impossible
    pass
```

### The Actual Working Pattern: Primitive Extraction

This is already documented in `on_tick_numba_scenarios.md` and `on_tick_numba_compatibility.md`:

```python
# numerical.py - Numba compatible (primitives only)
@njit
def tick_is_valid(bid: float, ask: float) -> bool:
    return (bid > 0.0) and (ask > 0.0) and isfinite(bid) and isfinite(ask)

@njit
def should_emit_probe(emit_flag: bool, probe_count: int, tick_valid: bool, max_probes: int = 5) -> bool:
    return emit_flag and tick_valid and (probe_count < max_probes)

# on_tick.py - Python orchestration (extracts primitives, calls kernels)
def on_tick(tick, settings, strategy_runtime, environment, event_loop):
    # Extract primitives ONCE per call
    bid, ask = tick.bid, tick.ask
    emit_flag = settings.emit_time_basis_probe
    probe_count = strategy_runtime.time_basis_probe_count
    
    # Call @njit kernels with primitives
    tick_valid = tick_is_valid(bid, ask)
    probe_emitted = should_emit_probe(emit_flag, probe_count, tick_valid)
    
    if probe_emitted:
        strategy_runtime.time_basis_probe_count += 1  # Python mutation
    
    # ... rest of orchestration (gate checks, protocol dispatch, result construction)
```

---

## Why `RuntimeEnvironment` Specifically Doesn't Matter

`RuntimeEnvironment` has exactly **one field**: `is_tester: bool = False`.

```python
@dataclass(frozen=True, slots=True)
class RuntimeEnvironment:
    is_tester: bool = False
```

Even if converted to `np.array([False], dtype=np.bool_)`:
- It adds **one boolean** to the call signature
- The conversion overhead exceeds any Numba benefit
- The function still can't be `@njit` due to all other parameters (`Tick`, `StrategySettings`, `StrategyRuntimeState`, `EventLoop`, `OnTickResult` return)

---

## Performance Reality Check

| Operation | Estimated Cost |
|-----------|----------------|
| Extract 5-10 primitives from objects | ~50-100 ns |
| Call `@njit` function (overhead) | ~200-500 ns |
| Pure Python boolean logic (current) | ~20-50 ns |
| **Net result** | **Numba slower for trivial gate checks** |

The "hot path" in `on_tick` is **not** the gate checks—it's `event_loop.process_tick()` which does the actual computation. Numba effort should focus on `EventLoop` implementations, not the orchestration layer.

---

## Numba Features That Might Seem Relevant (But Aren't)

| Feature | Why It Doesn't Apply |
|---------|---------------------|
| `@jitclass` | Requires known-at-compile-time fields; no `datetime`, no nested objects, no Pydantic |
| `StructRef` (experimental) | Must define struct in Numba; cannot map from Python dataclass at runtime |
| `numba.types.Dataclass` | Doesn't exist |
| `numba.from_dtype` | Only for NumPy dtypes, not Python objects |
| `np.ndarray` with `dtype=object` | Explicitly unsupported in nopython mode |

---

## Conclusion

**Converting dataclasses to NumPy arrays does not unlock Numba for `on_tick.py`.**

The correct approach (already documented):
1. **Extract numerical kernels** to `numerical.py` with `@njit` taking only primitives
2. **Keep orchestration in Python** — `on_tick()` is a routing/mutation/coordination function, not a numerical hot path
3. **Focus Numba optimization on `EventLoop` implementations** where actual numerical computation occurs (`process_coordinator_tick`, zone math, etc.)

No further investigation needed. The architectural boundary is correct: Numba for numerical kernels, Python for orchestration.

---

## Related Documents

- `docs/todo/on_tick_numba_compatibility.md` — Task tracking and acceptance criteria
- `docs/todo/on_tick_numba_scenarios.md` — Function-by-function feasibility analysis
- `src/application/xauusd_trading_strategy_1/numerical.py` — Target location for `@njit` kernels (to be created)