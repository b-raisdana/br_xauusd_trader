---
name: quality-gate
description: Use before declaring implementation complete, committing a milestone, creating a release candidate or preparing a live gate.
---

# Quality Gate

Run the checks appropriate to the project:
1. syntax/build/compile;
2. formatter/lint;
3. unit tests;
4. affected regression/integration tests;
5. strategy-specific correctness checks;
6. secret check;
7. platform-specific smoke test when available.

During rapid MVP execution, run affected targeted checks after each implementation batch and reserve this complete gate for a major milestone, final MVP candidate, or safety-critical change. Do not rerun unchanged expensive checks merely to create a Git checkpoint.

Fix failures caused by the work.
Do not disable checks to get a green result.
Update `TEST_STATUS.md` with evidence.
