---
name: test-strategy
description: Use when adding or changing strategy logic, risk logic, data handling, execution adapters or bug fixes. Select objective tests that prove confirmed behavior and prevent regression.
---

# Test Strategy

## Classification is mandatory

Every new test module must be registered in `tests/conftest.py`
`TIER_BY_MODULE`; an unclassified module fails collection by design. Pick the
tier by what the test needs, not by how convenient it is to run:

- `unit` - deterministic, in-process, no external boundary.
- `integration` - filesystem, subprocess, packaging or optional tooling.
- `parity` - comparison against a recorded or synthetic reference.
- `native` - needs MetaTrader5/broker/tester (currently empty).
- `perf` - timing/memory (currently empty; never a correctness gate).

Prefer deterministic tests for:
- signal conditions;
- boundary prices/times;
- trend/zone state transitions;
- risk sizing;
- stop/target management;
- trading-session rollover;
- gaps and missing data;
- order lifecycle state;
- cost calculations.

For bugs:
1. reproduce with a failing regression test/fixture;
2. fix the root cause;
3. prove the old bug fails before the fix when feasible;
4. run the nearby regression scope.

For separate research/live implementations:
- maintain shared deterministic fixtures;
- compare outputs at defined checkpoints;
- record parity tolerance explicitly;
- never let a comparison without a reference be reported as parity.

Shared helpers belong in `tests/vectorized_fixtures.py` or `tests/conftest.py`,
not in another test module, so tier selection stays stable.
