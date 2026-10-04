---
name: project-decisions
description: Use when choosing architecture, dependency, persistence, configuration, concurrency or other durable technical conventions. Prefer the smallest maintainable design and record only decisions future work needs.
---

# Project Decisions

Durable conventions. Read the linked reference for the detailed policy instead
of loading long material up front.

## Principles

- YAGNI: current need before hypothetical scale.
- Correctness before speed. Measure before optimizing.
- Separate deterministic trading/domain logic from external I/O where practical.
- Prefer mature libraries when they reduce correctness risk.
- Avoid hidden mutable global state in strategy logic.
- One authoritative config path per concern.
- No hard-coded credentials or developer-specific absolute paths.
- Cache only measured/reused expensive results; define cache keys and freshness.
- Measure bottlenecks before adding concurrency.
- Abstract after real duplication exists.
- Keep errors actionable at data/config/external boundaries.

## Hard prohibitions

- **No Python per-tick or per-candle iteration**, including `for`/`while`,
  `iterrows`, `itertuples`, row comprehensions, `zip`/`enumerate` over market
  rows, row-wise `apply`, and `map` with a Python callback. Stateful
  dependencies and MT5 parity do not permit a Python outer loop.
  `np.vectorize`, generators, or moving the loop into a helper do not
  vectorize it. Python iteration is a last resort **only over non-market-row
  units** (files, daily partitions, instruments, fixed config fields).
- No bare `except`. Catch specific exception types.
- No ambiguous single-letter variable names such as `l`.
- No disabling a check to obtain a green result.

## References

| Reference | Read when |
|---|---|
| [Vectorized pandas/NumPy policy](references/vectorized-pandas-numpy.md) | Writing or reviewing any Python data processing: strategy, replay, indicators, labels, OHLCV, persistence, reporting. Also the canonical operation-priority order and the compiled-Numba fallback rule. |
| [Data, path and logging conventions](references/data-and-path-conventions.md) | Naming timestamps/timeframes, choosing config or CLI libraries, helper imports, DRY merges, log-on-raise, comment policy. |

## Recording

Record durable rationale in `docs/DECISIONS.md` when it exists. Do not log
routine local choices, and do not invent a decisions file that the repository
does not have; state the rationale in the change instead.