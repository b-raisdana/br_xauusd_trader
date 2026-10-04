---
name: performance-review
description: Use when optimizing a hot path or reviewing an optimization claim. Requires measured equivalence, compliance with the vectorization rule, and honest warm/cold reporting.
---

# Performance review

Correctness before speed. Measure before optimizing, and measure the **active**
path.

## Measure the active controller

Benchmark the public controller, not private helpers or legacy vector utilities.
For this project that is `VectorizedXauUsdStrategy` via
`python scripts/dev.py benchmark`. Timing `_process_tick_operations` or any
other underscore method measures internals that are free to change and will
mislead the next reader.

## Requirements for an optimization claim

1. **Equivalence first.** Output values, order, index and state must match the
   pre-change implementation exactly, or the difference must be explained and
   accepted. Run the `parity` and affected `unit` tiers.
2. **Compliance.** No interpreted row fallback. See
   [project-decisions](../project-decisions/references/vectorized-pandas-numpy.md)
   for the operation priority and the compiled-Numba fallback rule.
3. **Honest statistics.** Report the **median**, not the fastest repetition.
   Report warm and cold timings separately: first-call import, JIT and cache
   effects routinely dominate a single run.
4. **Memory.** Record peak memory when the change alters allocation behavior,
   especially when replacing an in-memory accumulation with a write-through path.
5. **Environment.** Interpreter version, platform, dependency versions and row
   count. A timing without these is not evidence.

## Reporting

State the measured before/after with median and spread, the equivalence
evidence, the commands, and the limits. If a target is missed, say so; do not
quietly drop the measurement. Provisional targets in
[docs/development.md](../../../docs/development.md) are baselines, not budgets,
until re-measured on the documented machine.

## Known cost, not noise

`@pandera_validate` on the hot path dominates test and pipeline wall time. That
is a real cost worth raising as its own bounded task; it is not an excuse to
skip equivalence checks or to disable validation to make a number look better.