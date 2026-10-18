---
name: pytest
description: Use whenever writing, running, or debugging pytest tests in this repo. Covers this checkout's markers, pre-commit gate, CI suite, and fast testing of internal logic without compiled-backend startup.
---

# Pytest

Load [test-strategy](../test-strategy/SKILL.md) first when choosing what behavior and test type to add. This skill covers test execution and runtime boundaries.

## Commands and selection

- Tests live in `tests/`; pytest configuration and marker definitions are in `pyproject.toml`.
- `python -m pytest -q -m unit` is the pre-commit gate. `.pre-commit-config.yaml` runs this command for source, test, and pytest-config changes.
- `python -m pytest` runs the complete suite. `.github/workflows/ci-python.yml` runs it in the manually dispatched CI workflow, including slow integration tests.
- `-n auto --dist=load` is configured globally. xdist starts one worker per detected CPU; work is load-balanced across workers. Do not add a second parallelization layer inside tests.
- Measure worker counts in this checkout before tuning xdist. Timings from other checkouts are not evidence for this suite; startup and repeated imports can dominate small selections. Use `-n 0` for focused diagnosis.
- An unmarked test is assigned `unit` by `tests/conftest.py`. Any explicit marker prevents that default, so mark slow tests explicitly.

## Runtime boundaries

- Unit tests must check isolated logic and stay below 500 ms each. They belong in the pre-commit gate.
- Tests that initialize Numba, Vectorbt, compiled replay scans, or exercise the full native-to-execution pipeline must use both `@pytest.mark.integration` and `@pytest.mark.slow` (or module-level `pytestmark`). They stay in the full CI suite and are excluded from pre-commit's `-m unit` selection.
- Integration tests should stay below 5 seconds when practical. Keep genuine compiled-backend and end-to-end checks even when slower; run them in CI, not on every local commit.
- Current examples include `tests/test_dummy.py` (Numba JIT and Vectorbt import), `tests/test_vectorized_breakouts.py` (full strategy scans), `tests/test_batch_execution_replay.py` (compiled execution replay), and `test_leveraged_report_preserves_fills_costs_streams_and_real_time` (Vectorbt simulation and report export).

## Keep pre-commit fast without losing logic coverage

- Split preparation, validation, projection, state transitions, and dispatch from compiled or I/O boundaries when that makes the behavior independently testable.
- Avoid eager imports of optional indicator or execution backends in native strategy modules. Use `TYPE_CHECKING` for annotation-only imports and local imports at the execution boundary; `helper.importer.ta` loads `pandas_ta` only when requested.
- Unit-test those helpers with small deterministic arrays/frames and fakes. For a Numba dispatcher, call `.py_func` to exercise the Python implementation without compiling; retain at least one marked integration test for the compiled boundary.
- Patch expensive constructors and persistence/reporting boundaries in orchestration tests. Assert the arguments and outputs exchanged between layers rather than launching the full pipeline.
- Validate malformed input before importing or initializing Vectorbt when possible; invalid-input tests should not pay backend startup costs.
- Do not mock the behavior being tested, weaken expected values, or remove integration coverage just to reduce runtime.
- Profile the slowest calls (`pytest --durations=20`) and classify the actual cause. Wall duration is elapsed test-run time; xdist call durations overlap across workers and cannot be summed to infer wall time.

## Fixtures and conventions

- Prefer deterministic, in-memory inputs small enough to expose edge cases. Avoid network, real market data, disk persistence, Numba compilation, or Vectorbt imports in unit tests.
- Use factory fixtures when tests need different input sizes/shapes. Keep each test focused on one behavior; parametrize cases that differ only by data values.
- Register any new marker in `pyproject.toml`; strict marker validation is preferred so spelling mistakes fail collection.
- Run the active project Python environment (`python -m pytest ...`) so pytest, xdist, and project dependencies match pre-commit and CI.
