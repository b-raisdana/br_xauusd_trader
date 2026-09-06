---
name: project-decisions
description: Use when choosing architecture, dependency, persistence, configuration, concurrency or other durable technical conventions. Prefer the smallest maintainable design and record only decisions future work needs.
---

# Project Decisions

- YAGNI: current need before hypothetical scale.
- Separate deterministic trading/domain logic from external I/O where practical.
- Prefer mature libraries when they reduce correctness risk.
- Avoid hidden mutable global state in strategy logic.
- One authoritative config path per concern.
- No hard-coded credentials or developer-specific absolute paths.
- Cache only measured/reused expensive results; define cache keys and freshness.
- Measure bottlenecks before adding concurrency/optimization.
- Abstract after real duplication exists.
- Keep errors actionable at data/config/external boundaries.
- Record durable rationale in `DECISIONS.md`; do not log routine local choices.
