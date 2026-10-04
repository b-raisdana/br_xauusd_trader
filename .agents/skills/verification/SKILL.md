---
name: verification
description: Use when verifying a change, choosing a test tier, or deciding whether evidence is sufficient. Produces a verification record with nonempty selections and preserved failures.
---

# Verification

Run the correct tier through `scripts/dev.py`. Never invoke bare `ruff`,
`mypy`, `pytest` or `xenon` executables: they are absent from `PATH` in the
documented environment. Always go through the wrapper.

## Tiers

| Tier | Command | Measured on the documented machine |
|---|---|---|
| L0 preflight | `python scripts/dev.py inspect` | ~5 s |
| L1 focused | `python scripts/dev.py test <path-or-nodeid>` | 3 s single node, 42 s per module |
| L2 offline | `python scripts/dev.py check --tier L2` | ~52 s |
| L3 boundary | `python scripts/dev.py check --tier L3` | ~12 s |
| L4 full | `python scripts/dev.py check --tier L4` | measure before enforcing |

Targets are provisional and were measured on Windows / Python 3.14. Re-measure
before treating a number as a budget. The unit tier is slow because
`@pandera_validate` dominates; that is a real cost, not measurement noise.

## Classification authority

`tests/conftest.py` `TIER_BY_MODULE` is the single source of truth. An
unclassified module fails collection rather than falling through into the
default selection. Add a module there whenever you add a test file.

- `unit` - deterministic in-process regression.
- `integration` - filesystem, subprocess, packaging, optional tooling.
- `parity` - comparison against a recorded or synthetic reference.
- `native` - requires MetaTrader5/broker/tester. Currently **empty**; native
  evidence comes from the MT5 toolchain, not pytest.
- `perf` - timing/memory. Never part of a correctness gate.

## Contracts

- **A zero selection is a failure, not a pass.** `dev.py test` counts what
  pytest would collect and exits 3 before running anything. If a tier is
  legitimately empty, report it as an external BLOCKED prerequisite.
- Preserve nonzero exits. Do not wrap a failing check in something that
  swallows its status.
- Default focused runs to serial. Use `--parallel auto` only where measured
  beneficial (the offline suite: 52 s parallel versus 135 s serial).
- `pre-commit run` checks staged files only. It does not prove unstaged edits
  were checked, and `--all-files` is broader and mutating.

## Evidence classes

These are not interchangeable, and automation must never let them be confused:

1. offline regression
2. recorded comparison
3. MQ5 compile
4. native runtime parity

Replay without `--expected` is not a comparison. `compared=false` never
establishes parity. A green offline pipeline is not native parity.

## Recording

Record: commands run in order, environment, selected test count, skips with
reasons, and artifact paths. Reuse a persisted record instead of rerunning an
unchanged expensive gate.