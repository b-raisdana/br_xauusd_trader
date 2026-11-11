# Agentic maintenance follow-up

Reviewed against the checkout on 2026-10-19. Only remaining work is listed; completed logging, navigation and skill cleanup are removed. The consumer already pins hook commit `f262014`, including configurable skill mirrors, so no hook-submodule checkpoint remains pending.

## Execution boundaries

This tracker covers reliable agent navigation, source guidance and verification commands. General environment reproducibility is tracked separately as [P2 setup work](environment-reproducibility.md). Sharing a venv alone does not establish a defect or justify P1; per-sidecar environments are optional and are not a prerequisite for this plan.

Implement each item as a separate coherent batch. Preserve unrelated changes, confirmed trading/risk rules and incremental ratchet protections. Keep command captures under `logs/agentic/`. No commits, branches, pushes, PRs or remote CI dispatch without explicit authorization. Native parity and live approval remain outside this maintenance plan.

## Remaining work

### P1: Revalidate MT5 lifecycle documentation against current sources

- Scope: [MT5 README](../../mt5/README.md), focused lifecycle/design documents, [glossary notes](../State-Variables.Glossary.md), [CSV inventory](../State-Variables.Glossary.csv), translated material and [acceptance tracker](MT5-Python.Divergence.md). Use the current EA and release envelope together; archived behavior and Python implementations cannot establish native behavior.
- Check defaults, callback precedence, state set/clear/enforcement/recovery, no-action paths and request-versus-fill semantics. Replace stale property versions, hashes, declaration counts and missing-envelope claims only where current source inspection supports the correction. Preserve unresolved contradictions as explicit gaps.
- Acceptance for documentation: changed claims link to current source symbols/lines; affected tables, glossary entries and translations agree; unverified runtime claims remain marked. Refresh current authoring/configuration claims in the [agentic audit](../AGENTIC_AUDIT.md) where stale, without rewriting dated test evidence.
- Native compile/tester evidence is a separate remaining gate in the acceptance tracker: record EA/envelope hashes, terminal/compiler build, inputs and test provenance together. Documentation completion does not require or establish exact runtime parity, and unavailable native tools must remain an explicit evidence gap.

### P2: Make interpreter selection and verification commands explicit

- Scope: [runbook](../../RUNBOOK.md), agent verification instructions and IDE/terminal interpreter selection. Agents must identify the interpreter and checkout used for evidence rather than assume an activated prompt selects the intended code.
- Check existing guidance first; add only missing instructions for reporting `sys.executable`, Python version and imported project location, invoking checks through the selected interpreter, and ensuring hook analyzer executables are available on process PATH. Preserve the existing shared environment.
- Acceptance: repeatable commands identify the intended interpreter/checkout and run the relevant verification tier without environment mutation. If existing guidance already satisfies this requirement, close it with evidence. A demonstrated wrong import, dependency conflict or blocked required check can justify escalating the specific fault to P1.

### P2: Repair existing lint/type debt in bounded batches

- Scope: broad Ruff/mypy failures reported in the [audit](../AGENTIC_AUDIT.md); those historical counts must be reproduced before being treated as current. Keep navigation/tooling checks clean.
- Capture baseline diagnostics with the same interpreter, configuration and analyzers used for the candidate changes. Group repairs by cause/component; preserve behavior and add regression coverage where behavior could change. Do not weaken assertions, suppress checks wholesale or regenerate ratchet baselines to conceal regressions.
- Acceptance per batch: baseline-versus-candidate diagnostics identify the resolved group, relevant tests pass, changed-file hooks pass and no new violations appear. The overall item remains open until the broad Ruff check, format check and mypy commands configured in CI pass.

### P2: Validate manually dispatched Windows CI

- Prerequisites: [clean-install setup validation](environment-reproducibility.md) and broad lint/type gates above pass locally; the intended root revision and pinned submodule are available remotely through separately authorized Git actions. This hosted-validation prerequisite does not block unrelated agent maintenance. Remote dispatch requires explicit authorization.
- Run the existing manual workflow without reducing configured checks. Acceptance: dependency installation, pinned submodule checkout, repository checker, isolated tooling tests, Ruff, formatting, mypy and the configured full pytest suite execute successfully. Record workflow URL, root/submodule revisions, interpreter and results; fix failures before claiming hosted success.

## Review evidence

2026-10-19: root and submodule working trees were clean before this documentation edit; root `a690a93` pins `br_pre_commit` at `f262014`, matching its checked-out HEAD. Current hook code implements configurable agent slots and the legacy GitHub-slot switch. Repository checker PASS (zero issues); isolated tooling tests PASS (10). Fresh dependency resolution, native compile/tester and hosted CI were not rerun for that review. Earlier validation remains in the [audit](../AGENTIC_AUDIT.md) and is dated evidence, not a current full-gate result; the separate P2 lint/type recheck follows.

2026-10-19 P2 lint/type batch: baseline used `C:\Users\brais\AppData\Local\Programs\Python\Python314\python.exe` 3.14.0, Ruff 0.14.14 and mypy 2.3.1 with root configuration. Baseline reproduced 4 broad Ruff findings and measured 677 mypy errors in 76 files (the audit's 676 errors in 73 files is historical); formatting passed for 158 files. Candidate Ruff and format checks pass (159 files); mypy reports 655 errors in 69 files, with 22 baseline diagnostics removed and none added. The batch corrected all four Ruff findings, removed 13 unused ignores across the consumer and hook submodule, fixed a missing benchmark generic, typed the backtest CLI fixtures, added `Tick.from_ndarray` validation coverage, and escaped a Windows-path regex in the hook test. Focused tests and root/submodule changed-file hooks passed. Captures are in `logs/agentic/`; the broad mypy gate still fails, so this item remains open.
