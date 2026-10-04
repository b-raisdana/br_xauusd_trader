# AGENTS.md - tests/

Delta to the root contract. Read the root `AGENTS.md` and
[docs/development.md](../docs/development.md) first.

## Classification is mandatory

`TIER_BY_MODULE` in [conftest.py](conftest.py) is the classification authority,
applied in `pytest_collection_modifyitems`. An **unclassified module fails
collection** by design, so register every new test file there.

| Tier | Use for |
|---|---|
| `unit` | deterministic, in-process, no external boundary |
| `integration` | filesystem, subprocess, packaging, optional tooling |
| `parity` | comparison against a recorded or synthetic reference |
| `native` | needs MetaTrader5/broker/tester; currently **empty** |
| `perf` | timing/memory; currently **empty**, never a correctness gate |

Current selection: unit 178, integration 17, parity 50, offline/all 245.
`native` and `perf` being empty is expected; `dev.py test --tier native` exits 3
on purpose. Report that as an external BLOCKED prerequisite, never as a pass.

## Determinism and offline boundaries

- Tests must be deterministic and offline. No network, no broker, no dependency
  on `data/` (gitignored). Real cached OHLCV belongs to no current tier.
- Fixed seeds. Synthetic frames are small and built by the shared fixtures.
- `conftest.py` binds `core_vectors.use()` and `strategy_config.use()`
  automatically through an autouse fixture, so configuration is already
  context-bound in every test.

## Selection and helpers

- Import shared fixtures from [vectorized_fixtures.py](vectorized_fixtures.py)
  or `conftest.py`, never from another test module. Test-to-test imports make
  tier selection unstable.
- Keep the flat `tests/test_<module>.py` layout. There are no
  `unit/`/`integration/`/`e2e/` subfolders, and `characterization`,
  `regression`, `smoke` and `e2e` markers do not exist here.

## Running

```
python scripts/dev.py test tests/test_vectorized_where.py
python scripts/dev.py test --tier unit --parallel auto
```

`dev.py test` counts what pytest would collect and exits 3 rather than running
an empty selection. A zero selection is never a pass. Default focused runs are
serial; use `--parallel auto` where measured.

## Evidence discipline

A `parity` test compares against a reference. A comparison without a reference is
not parity. Report the evidence class explicitly, and never let a green offline
suite stand in for native proof.

## Dead code

A test module that collects zero tests is dead weight and hides real signal
loss. `tests/test_on_tick_vectorbt.py` and `tests/test_dummy.py` were removed
for this reason; `tests/test_optional_dependencies.py` replaced the latter with
a meaningful name. Do not reintroduce placeholder modules.