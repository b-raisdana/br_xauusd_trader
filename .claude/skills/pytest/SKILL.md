---
name: pytest
description: Use whenever writing, running, or debugging a pytest test in this repo. Covers how to execute tests here (use the active Python environment on PATH), plus repo conventions for markers, fixtures, and structure. Load test-strategy first to pick the right test type before writing it.
---

# pytest (this repo)

## Running tests

Fast gate: `pytest -m "unit and not slow"` (< 10s target). Slow subset: `pytest -m slow`. Full run: `pytest`.

Pytest config (pyproject.toml): markers unit (fast isolated unit tests) and slow (slow tests excluded from fast unit gate). ddopts = "-q -n auto" (parallel by default). 	estpaths = ["tests"], pythonpath = ["src", "."].

Conftest: 	ests/conftest.py auto-marks any unmarked test with unit. Autouse fixture _bound_strategy_configs wraps core_vectors.use() and strategy_config.use() for all tests.

TensorFlow warnings are harmless noise; check actual pytest summary.

## Marking slow tests

Only mark a test as @pytest.mark.slow if it is forced to run on huge data or has another concrete limitation that makes it long-running. Do not mark tests slow as a shortcut to hit time budgets; prefer optimizing data sizes or implementation first.

## Performance

- Target: fast gate -m "unit and not slow" runs in < 10s.
- addopts includes -n auto (pytest-xdist). Parallelism is not sufficient alone for the full legacy set.

## Layout

Tests live under 	ests/ (mirrored structure), not colocated with source.

## Structure

Follow Arrange-Act-Assert. One assertion focus per test when practical.

## Fixtures

Use small deterministic synthetic data (5-30 rows) in unit tests. Factory fixtures returning functions are preferred.

## Parametrize

Prefer @pytest.mark.parametrize over copy-pasted near-duplicates.

## Notes

The repo's fast gate for the current optimized subset is pytest -m "unit and not slow". The slow marker is registered in pyproject.toml.

