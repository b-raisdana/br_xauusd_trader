# Agentic maintenance follow-up

## Completed

- DONE: Require file loggers and captured agent command output under repository `logs/` in `AGENTS.md`. Source inspection confirms the application FileHandler uses `app_config.path_of_logs` (default `logs/`; explicit `DLF_LOGS_ROOT` overrides remain supported), and the hook wrapper writes reports/summaries under `logs/pre-commit/`. Existing root log captures remain untouched.
- DONE: Make `.agents/skills/` the shared authoring location; remove Copilot/Kilo/Devin duplicates after documented discovery checks, retain Claude/Kiro mirrors, configure sync targets and disable the legacy GitHub commit-skill slot. Preserve staged work; no commit or push is authorized. Discovery sources and configuration contract: [runbook](../../RUNBOOK.md#search-and-skills).
- DONE: Remove 26 empty shared-skill directories left under `.kilo/skills/`; preserve `kilo-only-todo-discipline/README.md`. Confirm the existing `agents = ["agents", "claude", "kiro"]` configuration excludes Kilo from both sync path classification and mirror destinations.
- DONE: Repair deleted navigation links, stale persistence/optimization guidance, checkout-specific timing claims and Git-authorization conflicts. Check canonical skill links and actual sync-pattern matching; test configurable mirrors and retired-slot exclusion without mutating the real index.

- DONE: Repair root recovery, source ownership, stale component entry points, packaging, CI prerequisites and mirrored-skill guidance; add scoped search and read-only repository checks. Evidence: [audit](../AGENTIC_AUDIT.md).

## Remaining

- P1: Save verified hook-submodule changes and root configuration together when Git actions are explicitly authorized. Acceptance: commit the hook implementation first, pin that commit in the consumer, preserve unrelated staged changes and run normal hooks. Until then, a clean checkout of the current pinned submodule does not implement the new mirror settings.

- P1: Revalidate native lifecycle notes in `mt5/README.md` against the current EA/envelope, then update the focused design/glossary and translated material where behavior changed. Do not treat historical property versions, hashes or missing-envelope claims as current evidence. Acceptance: source-linked lifecycle claims and matching compile/tester provenance; exact runtime parity remains a separate acceptance gate.
- P1: Establish reproducible dependency resolution on a clean Windows Python environment using `pyproject.toml`, including submodule initialization; add a lock only after confirming the complete declared dependency set resolves. Acceptance: fresh editable install, repository checker, unit collection and wheel build; no silent dependency removal or global environment changes.
- P2: Triage broad existing lint/type errors separately from this navigation/tooling batch. Preserve behavior and incremental ratchet protections. Acceptance: reproduce violations on baseline, fix coherent groups with relevant regression coverage, and leave new checker/tests clean.
- P2: Validate manually dispatched Windows CI on the remote only when explicitly authorized. Acceptance: dependency installation, submodule checkout and complete configured gates execute; local configuration checks alone do not prove hosted success.

## Verification

2026-10-19 Kilo cleanup: removed 26 empty shared-skill directories; only `kilo-only-todo-discipline` remains. Consumer runtime configuration/classification check PASS (Kilo excluded); repository checker PASS (zero issues); isolated tooling tests PASS (10); synchronization tests PASS (35). Existing sync settings already satisfy the requested exclusion and remain unchanged.

2026-10-18: repository checker PASS (zero issues); isolated tooling tests PASS (10); synchronization tests PASS (35); consumer settings/import check PASS; targeted tooling Ruff/format/mypy PASS; changed-file hooks PASS in root and submodule, including unit gates and the submodule ratchet. The submodule gate initially exposed missing analyzer executables on process PATH and tests coupled to former default platform slots; adding the installed Scripts directory and explicit test configuration resolved both. Sync mutation was not invoked against the real index because pre-existing staged skill versions must remain intact; read-only mirror equality and isolated sync tests cover this batch. Native/runtime integration and hosted CI were not rerun; trading implementation is unchanged.
