---
name: project-decisions
description: Use when choosing architecture, dependency, persistence, configuration, concurrency or other durable technical conventions. Prefer the smallest maintainable design and record only decisions future work needs.
---

# Project Decisions

- YAGNI: current need before hypothetical scale.
- Separate deterministic trading/domain logic from external I/O where practical.
- Prefer mature libraries when they reduce correctness risk.
- All project strategy/data calculations use complete vectorized pandas DataFrame/Series operations only: column operations, `shift` and `eval`. NumPy and Python iteration are prohibited, including `for`/`while`, comprehensions, row scans, `iterrows`, `apply(axis=1)`, callbacks and alternate array/compiled kernels.
- Put every numeric strategy parameter and configurable column/window count in the component `config/`, validated by its canonical base settings model. Current values are defaults or optimization candidates; never hardcode them in calculations.
- Pass large cross-module data by manifest references to disk artifacts, not by copying/materializing DataFrames. Temporary DataFrames contain only newly derived incremental columns; align/map them to existing data by index when consumed.
- Avoid hidden mutable global state in strategy logic.
- One authoritative config path per concern.
- No hard-coded credentials or developer-specific absolute paths.
- Cache only measured/reused expensive results; define cache keys and freshness.
- Measure bottlenecks before adding concurrency/optimization.
- Abstract after real duplication exists.
- Keep errors actionable at data/config/external boundaries.
- Record durable architectural rationale in `docs/ARCHITECTURE.md` (or a Decisions register if introduced); do not log routine local choices.
