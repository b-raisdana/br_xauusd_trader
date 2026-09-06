---
name: test-strategy
description: Use when adding or changing strategy logic, risk logic, data handling, execution adapters or bug fixes. Select objective tests that prove confirmed behavior and prevent regression.
---

# Test Strategy

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
3. prove old bug fails before fix when feasible;
4. run nearby regression scope.

For separate research/live implementations:
- maintain shared deterministic fixtures;
- compare outputs at defined checkpoints;
- record parity tolerance explicitly.
