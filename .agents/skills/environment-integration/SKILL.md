---
name: environment-integration
description: Use when setting up Python, MT5, exchange APIs, local data paths, virtual environments or repeatable run commands.
---

# Environment Integration

1. Detect installed tools/versions first: `python scripts/dev.py inspect`.
2. Prefer a project-local Python virtual environment.
3. Install only dependencies needed now; `pyproject.toml` is the only manifest.
4. Put repeatable setup/run commands in `docs/development.md`.
5. Keep secrets outside Git. `.env` and `.kilo/kilo.json` hold literal local
   credentials; committed examples carry placeholders only.
6. Build paths from configurable roots.
7. Add a smoke check for each external integration. `dev.py build --smoke`
   installs the wheel outside the checkout and imports it.
8. For MT5, distinguish:
   - Python Terminal API connectivity;
   - MQL5 compile/Strategy Tester path;
   - live execution path.
9. Never assume Strategy Tester can directly execute Python strategy code.
10. Remember bare `ruff`/`mypy`/`pytest`/`xenon` executables are absent from
    `PATH` in the documented environment; invoke tools through `scripts/dev.py`.
