---
name: task-handoff
description: Use when converting research, a Leader instruction or an audit finding into an executable bounded task. Produces a READY task or an explicit BLOCKED statement.
---

# Task handoff

A handoff is executable only if a fresh agent can act on it without asking a
question. Template:
`.gitlab/issue_templates/Agent_Task.md`.

## Required sections

1. **Goal** - one sentence describing the observable behavior change.
2. **Status** - `READY` | `IN_PROGRESS` | `BLOCKED` | `REVIEW` | `DONE`, plus a
   `P0`-`P3` label.
3. **Context and current behavior** - with `path:line` evidence and the
   authority document that applies. If a referenced control document does not
   exist, say so instead of linking it.
4. **Scope** - the files and directories that may change.
5. **Constraints** - no trading/risk rule changes, no real-money enablement, no
   unjustified dependency, preserve native-proof limits.
6. **Relevant implementation, callers, contracts, tests** - the map from
   [docs/architecture.md](../../../docs/architecture.md).
7. **Expected behavior** - falsifiable.
8. **Acceptance criteria** - positive case, negative/rejection case, no
   unrelated change, docs updated.
9. **Verification** - exact commands, runnable from a clean checkout, plus
   prerequisites and artifact paths.
10. **Evidence class** - offline regression / recorded comparison / MQ5 compile /
    native runtime parity, stated explicitly.
11. **Dependencies** and **out of scope**.

## READY criteria

`READY` requires all four of: clear authority, bounded scope, acceptance
criteria, and executable verification commands. Anything less is `BLOCKED`, and
the blocking condition must be named.

## Rules

- Split offline work from externally blocked native evidence. A task that needs
  MetaEditor cannot be closed by a Python test run.
- One owner for acceptance criteria. Do not duplicate acceptance across issues
  and TODO trackers; link instead.
- Do not mark a task DONE on a green offline suite when it claims native proof.
- Preserve the limits: a passing backtest is not deployment approval, and real
  money is always a Project Leader gate.

## Post-implementation

Update `docs/CURRENT_STATE.md` when the verified state, measured baseline or
READY list changes. Generate later summaries from stored evidence rather than
rerunning the experiment.