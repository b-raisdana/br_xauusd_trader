# MQL5 to Python conversion plan

## Objective

Convert `mt5/XAUUSD_MVP.mq5` and every `.mqh`/generated dependency into installable, testable Python while preserving the current research-only safety gates. The Python result must expose the same lifecycle stages and deterministic contracts as MQL5, use snake_case names, and keep broker/terminal access behind an optional adapter.

## Non-goals

- Do not enable live or real-money trading.
- Do not infer fills, closes, or broker outcomes from price alone.
- Do not remove the frozen MQL5 baseline or its generated evidence.
- Do not promote historical `legacy_reference/` implementations.
- Do not claim parity from a small replay sample.

## Source-of-truth order

1. Current Project Leader instruction.
2. `docs/RULES.md` and active decisions.
3. `mt5/XAUUSD_MVP.mq5` plus its includes for the conversion target.
4. Existing Python domain behavior where it is verified equivalent.
5. `tests/vectors/core_contracts.json` for the 19 frozen contract vectors.

## Target architecture

| Layer | Destination | Responsibility |
|---|---|---|
| Lifecycle | `src/application/xauusd_trading_strategy_1/` | `on_initialize`, `on_tick`, `on_trade_transaction`, `on_deinit`, runtime state |
| Domain | `src/domain/xau_usd/` | Pure contracts, enums, state machines, signal/risk/execution logic |
| Infrastructure | `src/infrastructure/xau_usd/` | MT5 adapter, tester broker, persistence, audit, native market metadata |
| Configuration | `src/config/` | Validated Pydantic settings and generated vector/zone data |
| Tests | `tests/xauusd_trading_strategy_1/` and `tests/xauusd/` | Unit, integration, parity, and lifecycle regression tests |

The application layer owns orchestration but not MT5 API calls. The infrastructure layer owns MT5 calls and file I/O. Domain modules remain deterministic and importable without MetaTrader5.

## Naming and packaging rules

- Convert MQL5 `CamelCase` and `Inp...` names to Python `snake_case`.
- Keep stable rule IDs and generated vector names stable in serialized data.
- Use typed dataclasses or Pydantic models for MQL5 structs.
- Use explicit timezone-aware `datetime` values; never rely on host-local time.
- Use `Decimal` for money/price contracts and a documented `1e-9` parity tolerance only at the MQL boundary.
- Add package initializers and relative imports.
- Add `src/domain` and `src/application` to the hatch package configuration.
- Keep `MetaTrader5` and `numba` out of the pure lifecycle/domain path.

## Generated CoreVectors configuration

`mt5/generated/CoreVectors.mqh` is already represented by `src/config/core_vectors.py`. Extend that conversion as follows:

- Use a Pydantic `BaseSettings` model with `extra="forbid"` and frozen runtime instances.
- Default to `config/mt5/core_vectors.json` as an optional JSON override source.
- Load explicit JSON paths through `load_core_vectors(path)` for tests and future updates.
- Validate every numeric, date, string, and enum-like vector field at construction.
- Keep generated constants and JSON values synchronized with `tests/vectors/core_contracts.json` through a drift test.
- Do not mutate a loaded vector instance; create a new validated instance for a changed configuration.

## Conversion segments

### Segment 0: package foundation

- Add `src/application/xauusd_trading_strategy_1/__init__.py`.
- Repair package imports and wheel inclusion.
- Replace the broken `GlobalState` stub with a typed `StrategyRuntimeState` while preserving a compatibility `global_state` instance only where existing callers require it.
- Add `g_runtime_requests` and typed collection defaults.
- Add focused import and state initialization tests.

### Segment 1: CoreVectors and generated data

- Finish the Pydantic settings conversion for `CoreVectors`.
- Add `config/mt5/core_vectors.json` with all values from `CoreVectors.mqh`.
- Add JSON override, validation, and generated-header drift tests.
- Convert `generated/DailyZones.mqh` into a validated Python zone-day source without changing canonical `data/ranges.csv`.
- Keep generated artifacts reproducible from their existing generators.

### Segment 2: contract/domain parity

- Verify every function listed in `mt5/include/XauContracts.mqh` against `src/domain/xau_usd/`.
- Preserve the existing public functions where behavior is equivalent; add missing wrappers only when the MQL signature is required by lifecycle code.
- Add or restore deterministic tests for all 19 vectors and boundary cases.
- Record any Decimal/double tolerance difference explicitly.

### Segment 3: execution state and persistence

Port `mt5/include/XauExecution.mqh` into `src/infrastructure/xau_usd/execution.py`:

- `XauExecutionProjection`
- `XauExecutionBinding`
- projection initialization and outcome transitions
- order/position binding and request resolution
- correlated native outcome projection
- atomic TSV persistence, loading, equality, and path escape protection

Use a repository-safe path resolver and injectable storage backend so tests do not write into MT5 terminal directories.

### Segment 4: audit and visual payloads

Port `XauAudit.mqh` and `XauVisual.mqh`:

- typed audit events and JSONL append-before-project behavior
- atomic directory/file handling
- marker/tooltip serialization
- deterministic tests for rejection, allowed requests, corrupt input, and path containment

### Segment 5: native and tester adapters

Port `XauNative.mqh`, `XauTesterBroker.mqh`, and `XauTesterRisk.mqh` behind protocols:

- symbol specification and trade-session queries
- deal classification and native cash-risk/margin calculations
- tester-only execution gate
- prepared-entry submission, protection modification, cancellation, and close
- tester risk snapshots and position risk-free price
- explicit injected outcomes for deterministic tests

The default adapter must fail closed outside an authorized tester/replay context. No adapter may silently become a live trading path.

### Segment 6: state machines

Port `XauState.mqh` into `src/domain/xau_usd/state.py`:

- trend day/candle/tick state
- daily zone engagement and usage
- entry-attempt ledger
- pullback windows, candidates, fills, expiry, and pending removal
- pre-zone trigger and pullback TP state

Keep pure state transitions separate from broker I/O and preserve MQL ordering semantics.

### Segment 7: coordinator and request preparation

Port `XauCoordinator.mqh` and `XauRequests.mqh`:

- coordinator day/bar/tick lifecycle
- signal candidate creation and de-duplication
- bar-close breakout emission
- prepared entry construction
- audit event creation
- durable attempt commit and usage accounting

Add tests for day rollover, bar rollover, duplicate signals, failed attempts, and shared M15 entry slots.

### Segment 8: lifecycle pipeline

Rewrite the application stubs from the MQL entry points:

- `on_initialize(settings, dependencies)` maps `OnInit`.
- `on_tick(tick, settings, runtime, dependencies)` maps `OnTick`.
- `on_trade_transaction(transaction, request, result, settings, runtime, dependencies)` maps `OnTradeTransaction`.
- `on_deinit(reason, settings, runtime)` maps `OnDeinit`.
- Extract the MQL pipeline functions into small, individually testable Python functions with snake_case names.
- Preserve the MQL stage order: symbol specification, day/bar rollover, operational safety, pullback TP, profit protection, conflict closes, candidate processing, coordinator tick processing.
- Keep the time-basis probe optional and bounded.

`on_init.py` and `on_tick.py` must be written to disk before their downstream pipeline modules are considered complete. A function or class is written as soon as its segment contract is understood; it does not wait for the full EA.

### Segment 9: parity and acceptance

- Run all 19 CoreVectors in Python and compare with MQL results.
- Add lifecycle parity fixtures for initialization, day rollover, bar rollover, candidate rejection/acceptance, native fills, protection changes, session flatten, and restart.
- Compare state counters and durable audit records at defined checkpoints.
- Run Ruff, mypy, pytest, and the repository pre-commit gate.
- Update `docs/CURRENT_STATE.md`, `docs/TEST_STATUS.md`, and this plan with measured results.

## Segment acceptance evidence

| Segment | Required evidence |
|---|---|
| Foundation | imports pass; package is included in the wheel; state initializes with no mutable alias bugs |
| CoreVectors | all 119 fields validate; JSON override works; generated-header drift test passes |
| Domain | all 19 vectors and boundary tests pass |
| Execution/audit | lifecycle transitions, persistence, corrupt-input rejection, and path containment tests pass |
| Native/tester | adapter calls are injectable; unauthorized/live paths fail closed; deterministic outcome tests pass |
| State/coordinator/requests | ordering, rollover, usage, and attempt tests pass |
| Lifecycle | initialization and tick-stage tests pass without importing MetaTrader5 in the domain path |
| Final gate | Ruff, mypy, pytest, and pre-commit pass or failures are explicitly attributed |

## Current known gaps

- `on_init.py` is empty.
- `on_tick.py` contains invalid imports, an async Numba decorator, undefined symbols, malformed calls, and a final `NotImplementedError`.
- `global_state_variable.py` has class-body imports, untyped `Any` placeholders, and no runtime-request collection.
- The application package has no initializer.
- The domain package has no public re-exports and its wheel inclusion is incomplete.
- The 19-vector Python runner and conversion-target tests are absent from the current checkout.
- `src/config/__init__.py` points at a removed/mismatched `Config.py` module.
- The MQL execution, state, coordinator, request, audit, native, tester, and visual modules are not yet represented as Python modules.

## Execution order

1. Write this plan and establish package/configuration foundations.
2. Write CoreVectors settings and generated-data conversion.
3. Verify and, where needed, write domain contract modules.
4. Write execution and audit modules.
5. Write native/tester adapters.
6. Write state, coordinator, and request modules.
7. Rewrite lifecycle modules and wire the stage pipeline.
8. Add parity/regression tests and run the final gate.
9. Update project-state documentation and create one coherent local checkpoint only after the verified batch.
