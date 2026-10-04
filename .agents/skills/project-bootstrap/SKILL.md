---
name: project-bootstrap
description: Use when starting a new repository, when bootstrap placeholders remain, or after a deliberate project reset. Convert the Leader brief into a runnable baseline with minimal questions.
---

# Project Bootstrap

1. Read `AGENTS.md` and `docs/CURRENT_STATE.md`. `PROJECT_BRIEF.md`, `RULES.md`
   and `TODO.md` do not exist in this checkout; take the brief from the current
   Project Leader instruction and record it in `docs/CURRENT_STATE.md`.
2. Inspect the repository/environment with `python scripts/dev.py inspect`
   before assuming anything.
3. Extract goal, success criteria, non-negotiables, risks and non-goals.
4. Ask only for missing Leader-level decisions; choose reversible technical defaults yourself.
5. Populate project dashboard and control docs.
6. Select the smallest stack that can prove the core outcome.
7. Create only needed source/test structure.
8. Establish repeatable local commands for test/run.
9. Initialize Git if needed.
10. Verify baseline.
11. Create the first coherent commit.
12. If GitHub CLI is authenticated and the Leader has authorized repository creation, create a private remote and push.
13. Update `docs/CURRENT_STATE.md`.

Bootstrap is complete when a fresh agent can recover the goal, state, rules, next work and evidence from the repository alone.
