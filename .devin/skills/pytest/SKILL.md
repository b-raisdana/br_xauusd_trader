---
name: pytest
description: Use when writing, running or debugging a pytest test in this repository. Covers the real layout, the tier registry, and how to execute tests. Load test-strategy first to pick the right tier.
---

# pytest (this repository)

Companion to [test-strategy](../../../.agents/skills/test-strategy/SKILL.md)
(which tier to write) and [verification](../../../.agents/skills/verification/SKILL.md)
(which tier to run). This skill covers mechanics only.

## Running tests

Bare `pytest`, `ruff` and `mypy` executables are **not on `PATH`** in the
documented environment. Always go through the wrapper, which uses
`sys.executable -m`:

```powershell
python scripts/dev.py test tests/test_vectorized_where.py
python scripts/dev.py test --tier unit --parallel auto
python scripts/dev.py check --tier L2
```

`dev.py test` counts what pytest would collect and **exits 3 without running
anything** when the selection is empty. A zero selection is never a pass.

There is no pytest pre-commit hook. The unit tier takes ~135 s serially on the
documented machine (dominated by `@pandera_validate`), and pytest exits 5 on an
empty selection, so it is a CI and explicit-command gate, not a commit gate.

## Repo config

Configuration lives in `pyproject.toml` under `[tool.pytest.ini_options]`.
There is no `pytest.ini`.

| Setting | Value |
|---|---|
| `testpaths` | `["tests"]` |
| `pythonpath` | `["src"]` |
| `addopts` | `-q --strict-markers --strict-config` |
| markers | `unit`, `integration`, `parity`, `native`, `perf` |

`--strict-markers` makes an unregistered marker an authoring error.

## Tier registry

`tests/conftest.py` `TIER_BY_MODULE` is the classification authority, applied in
`pytest_collection_modifyitems`. An **unclassified module fails collection** by
design, so register every new test file there.

| Tier | Count | Meaning |
|---|---|---|
| `unit` | 178 | deterministic in-process |
| `integration` | 17 | filesystem, subprocess, packaging, optional tooling |
| `parity` | 50 | recorded/synthetic comparison |
| `native` | 0 | needs MetaTrader5/broker/tester; empty by design |
| `perf` | 0 | timing/memory; empty by design |
| `offline` | 245 | `not native and not perf` |
| `all` | 245 | `not perf` |

Layout is flat: `tests/test_<module>.py`, plus shared helpers
`tests/conftest.py` and `tests/vectorized_fixtures.py`. There are no
`unit/`, `integration/` or `e2e/` subfolders, and `characterization`,
`regression`, `smoke` and `e2e` markers do not exist here.

## Structure: Arrange-Act-Assert

One assertion focus per test. If two behaviors need separate reasoning to debug
a failure, they are two tests.

```python
def test_protection_stages_at_actual_r0(candles):
    # Arrange
    ticks, bars = prepared_ticks(build_ticks)(len(candles)), candles_from_ticks(candles)
    # Act
    state = run_stream(ticks, bars)
    # Assert
    assert state["protection_stage"].iloc[-1] == 3
```

## Fixtures

Shared synthetic builders live in `tests/vectorized_fixtures.py`
(`candles_from_ticks`, `with_native_bootstrap`, `prepared_ticks`,
`calculate_manifest`, `complete_tick_state`) and `tests/conftest.py`. Import
fixtures from these modules, never from another test module, so tier selection
stays stable.

Keep synthetic data small and deterministic. `tests/conftest.py` binds
`core_vectors.use()` and `strategy_config.use()` automatically via an autouse
fixture, so configuration is already context-bound in every test.

Cached OHLCV under `data/` is gitignored and not used by any test tier.

## Naming

`test_<behavior>_<expected>` where it fits on one line. For equivalence
assertions, name the reference, not just the result.

## Parametrize over near-duplicates

```python
@pytest.mark.parametrize("enabled,expected", [("false", False), ("0", False), ("yes", True)])
def test_zone_enabled_parsing(enabled, expected):
    ...
```

Reach for this whenever two tests differ only in literals.

## Evidence discipline

`parity` tests compare against a reference. A comparison without a reference is
not parity, and `recorded_runner` without `--expected` produces no comparison.
Report the evidence class explicitly. See
[strategy-parity](../../../.agents/skills/strategy-parity/SKILL.md).