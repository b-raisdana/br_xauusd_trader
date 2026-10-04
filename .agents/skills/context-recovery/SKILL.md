---
name: context-recovery
description: Use at the start of a new chat/session, after context loss, or when asked to continue previous work. Recover project state from repository evidence instead of asking the Leader to repeat history.
---

# Context Recovery

Authority order for this repository. Later items never override earlier ones.

1. Current explicit Project Leader instruction.
2. `AGENTS.md` at the repository root, plus the `AGENTS.md` of any directory you
   are about to edit.
3. `docs/CURRENT_STATE.md` - active paths, dirty-state caveat, READY tasks,
   blockers, latest evidence.
4. `docs/architecture.md` - responsibilities and dependency direction.
5. `docs/todo/` trackers for executable follow-up.
6. `README.md` and component READMEs.
7. Current code behavior.

Several project-control documents referenced by older instructions
(`RULES.md`, `DECISIONS.md`, `TODO.md`, `TEST_STATUS.md`, `EXPERIMENTS.md`,
`FINAL_TEST_REPORT.md`) **do not exist** in this checkout. Do not reconstruct
authority from archived copies or from `legacy_reference/`, and do not report
their absence as a blocker. `legacy_reference/` is regression/forensic input
only.

## Procedure

1. Read the assigned task, then `docs/CURRENT_STATE.md`.
2. `python scripts/dev.py inspect` - interpreter, tooling availability,
   submodule state, branch, dirty count, collected test count. Read-only.
3. `git status`, `git log --oneline -10`, `git submodule status`. Reconcile
   documented state against repository reality.
4. Read the `AGENTS.md` for the working directory before editing anything.
5. Load at most one skill that matches the task trigger.
6. Locate code, callers, contracts and mapped tests. Prefer narrow searches
   scoped to `src tests docs scripts config`:

   ```powershell
   rg -n "process_native_stream|MarketState" src tests
   rg --files src tests docs scripts config
   ```

   Do not search caches, `logs/`, `.kilo/node_modules`, `.kilo/worktrees` or
   frozen archives unless the task requires them.
7. Resolve authority contradictions explicitly. Prefer documented intent over
   inferred intent, and never silently pick one.
8. Execute the next safe `READY` task. Ask the Leader only for a genuine
   Leader-level decision: goal/scope, trading or risk rule, acceptance change,
   destructive action, credential boundary, cost, public release, production
   deployment, or real-money trading.

## Output

A short summary of: the task, the evidence found, the next action, and any real
blocker. Do not dump logs, datasets or long documents into the conversation.