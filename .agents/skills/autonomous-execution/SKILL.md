---
name: autonomous-execution
description: Use for non-trivial implementation, bug fixes, refactors or multi-step project work. Own large safe batches across planning, implementation, tests, documentation and Git, and continue across checkpoints without returning routine execution to the Leader.
---

# Autonomous Execution

## Before
- Read relevant Rules/Current State/TODO.
- Inspect Git status and actual code.
- Define objective acceptance evidence.

## Execute
1. Maintain the current TODO.
2. Investigate root cause before patching.
3. Make safe reversible technical decisions independently.
4. Group adjacent outcomes into the largest safe coherent batch that can be implemented and verified together.
5. Keep scope focused; larger batches must still serve the active objective.
6. Add/update tests with the implementation.
7. Record durable decisions only when future sessions need the rationale.
8. Log unrelated defects as future TODOs unless they block correctness.

## Continue
- A completed slice, green test run, commit, push or progress report is a checkpoint, not a terminal condition.
- After each checkpoint, choose the next safe executable TODO and continue while meaningful in-scope work remains.
- Status questions do not cancel active execution; answer briefly and resume unless the Leader replaces or cancels the objective.
- Never ask the Leader to say “continue” for routine work.
- Stop only when the objective is achieved or no meaningful safe progress remains without a genuine Leader decision, new authority or external-state change.
- If one dependency is blocked, advance independent safe work before declaring a blocker.

## Verify
- targeted checks first;
- run the full quality gate at a major milestone, final MVP candidate, or after safety-critical changes rather than after every micro-slice;
- never claim PASS without runnable evidence when a runnable check exists.

## Close
- synchronize docs;
- create one coherent local Git checkpoint for a major verified batch;
- during rapid MVP execution, defer routine push/PR/remote CI unless the Leader requests it or remote recovery materially requires it;
- if the objective remains open, immediately continue the next safe batch;
- report outcome/evidence/risk/Leader decision only.
