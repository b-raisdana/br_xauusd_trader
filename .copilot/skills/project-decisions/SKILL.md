---
name: project-decisions
description: Use when choosing architecture, dependency, persistence, configuration, concurrency or other durable technical conventions. Prefer the smallest maintainable design and record only decisions future work needs.
---

# Project Decisions

- YAGNI: current need before hypothetical scale.
- Separate deterministic trading/domain logic from external I/O where practical.
- Prefer mature libraries when they reduce correctness risk.
- Python data processing uses pandas DataFrames first and NumPy ndarrays second. Python per-tick/per-candle iteration, including previous-candle scans, row comprehensions and Python callbacks, is prohibited even for stateful replay. Follow the exact operation priority and compiled Numba fallback in [project-decisions](../../../.codex/skills/project-decisions/SKILL.md#vectorized-pandasnumpy); Python iteration is a last resort only for non-market-row orchestration.
- Avoid hidden mutable global state in strategy logic.
- One authoritative config path per concern.
- No hard-coded credentials or developer-specific absolute paths.
- Cache only measured/reused expensive results; define cache keys and freshness.
- Measure bottlenecks before adding concurrency/optimization.
- Abstract after real duplication exists.
- Keep errors actionable at data/config/external boundaries.
- Record durable rationale in `DECISIONS.md`; do not log routine local choices.
