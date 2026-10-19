# Development environment reproducibility

## P2: Verify a repeatable clean Windows installation

- Rationale: fresh dependency resolution remains unverified. This is development/setup work; no current shared-venv failure has been established by the maintenance review. Promote a specific issue to P1 only when evidence shows a dependency conflict, wrong-checkout import or blocked required validation.
- Scope: [package metadata](../../pyproject.toml), [setup commands](../../RUNBOOK.md#setup) and [Windows CI](../../.github/workflows/ci-python.yml). Use an explicit supported Python version (package minimum is 3.12), initialize the pinned submodule and install the complete editable `.[dev]` dependency set in a disposable isolated environment. Leave shared/global environments unchanged; do not silently remove dependencies or extras.
- After resolution succeeds, document a repeatable dependency snapshot/lock procedure with Python, platform, resolver and resolved versions. Reconcile the declared Python range, runbook and CI interpreter selection with demonstrated support; an existing environment or wheel build alone does not establish fresh installability.
- Acceptance: fresh editable install, `pip check`, repository checker, isolated tooling tests, nonempty unit collection and wheel build succeed. Capture commands, versions and results under `logs/agentic/`; distinguish collection from test execution. Record conflicting constraints and leave the item open if resolution fails.
- Per-checkout `.venv` migration is optional and separate from clean-install verification. Do not migrate sidecars, copy environments or modify `venv-shared-pandas` as part of this task. Separate venvs alone do not isolate writable logs, caches, databases or MT5 outputs.

The [agentic maintenance tracker](agentic-maintenance.md) owns interpreter-selection guidance and verification commands. No environment installation or migration was performed when creating this task.
