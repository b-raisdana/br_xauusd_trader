---
name: autonomous-execution
description: Use for non-trivial implementation, bug fixes, refactors or multi-step project work. Own planning, implementation, tests, documentation and Git without returning routine execution to the Leader.
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
4. Keep scope focused.
5. Add/update tests with the implementation.
6. Record durable decisions only when future sessions need the rationale.
7. Log unrelated defects as future TODOs unless they block correctness.

## Verify
- targeted checks first;
- then relevant quality gate;
- never claim PASS without runnable evidence when a runnable check exists.

## Close
- synchronize docs;
- create a coherent Git checkpoint;
- push when configured and safe;
- report outcome/evidence/risk/Leader decision only.
