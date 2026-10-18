# Agentic maintenance follow-up

## Completed

- DONE: Repair root recovery, source ownership, stale component entry points, packaging, CI prerequisites and mirrored-skill guidance; add scoped search and read-only repository checks. Evidence: [audit](../AGENTIC_AUDIT.md).

## Remaining

- P1: Revalidate native lifecycle notes in `mt5/README.md` against the current EA/envelope, then update the focused design/glossary and translated material where behavior changed. Do not treat historical property versions, hashes or missing-envelope claims as current evidence. Acceptance: source-linked lifecycle claims and matching compile/tester provenance; exact runtime parity remains a separate acceptance gate.
- P1: Establish reproducible dependency resolution on a clean Windows Python environment using `pyproject.toml`, including submodule initialization; add a lock only after confirming the complete declared dependency set resolves. Acceptance: fresh editable install, repository checker, unit collection and wheel build; no silent dependency removal or global environment changes.
- P2: Triage broad existing lint/type errors separately from this navigation/tooling batch. Preserve behavior and incremental ratchet protections. Acceptance: reproduce violations on baseline, fix coherent groups with relevant regression coverage, and leave new checker/tests clean.
- P2: Validate manually dispatched Windows CI on the remote only when explicitly authorized. Acceptance: dependency installation, submodule checkout and complete configured gates execute; local configuration checks alone do not prove hosted success.
