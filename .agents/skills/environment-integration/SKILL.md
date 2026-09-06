---
name: environment-integration
description: Use when setting up Python, MT5, exchange APIs, local data paths, virtual environments or repeatable run commands.
---

# Environment Integration

1. Detect installed tools/versions first.
2. Prefer a project-local Python virtual environment.
3. Install only dependencies needed now.
4. Put repeatable setup/run commands in `RUNBOOK.md`.
5. Keep secrets outside Git.
6. Build paths from configurable roots.
7. Add a smoke check for each external integration.
8. For MT5, distinguish:
   - Python Terminal API connectivity;
   - MQL5 compile/Strategy Tester path;
   - live execution path.
9. Never assume Strategy Tester can directly execute Python strategy code.
