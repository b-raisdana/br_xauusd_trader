---
name: context-recovery
description: Use at the start of a new chat/session, after context loss, or when asked to continue previous work. Recover project state from repository evidence instead of asking the Leader to repeat history.
---

# Context Recovery

1. Read `docs/CURRENT_STATE.md`.
2. Follow the task map in `docs/ARCHITECTURE.md`; read relevant confirmed rules if present.
3. Read only relevant acceptance/TODO evidence linked from current state; optional Decisions/Experiments/Test Status need not exist.
4. Inspect `git status`, recent `git log`, current branch and remote.
5. Inspect relevant code/tests/results.
6. Compare documented state with repository reality.
7. Fix stale state documentation if evidence is clear.
8. Continue the next safe executable task.
9. Ask the Leader only if a true Leader-level contradiction remains.
