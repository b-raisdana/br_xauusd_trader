---
name: Agent Task
description: Bounded, independently executable engineering task for a coding agent
title: "[P0-P3][READY|BLOCKED] <short behavior change>"
labels: ["agent-task", "needs-review"]
assignee: ""
---

## Goal

One sentence describing the observable behavior change. Not a topic, not a
question.

## Status

`READY` | `IN_PROGRESS` | `BLOCKED` | `REVIEW` | `DONE`

`READY` requires all four of: clear authority, bounded scope, acceptance
criteria, and executable verification commands.

## Context and current behavior

What the code does today, with `path:line` evidence. What authority document
applies. If a referenced control document does not exist, say so instead of
linking it.

## Scope

Files and directories this task may change. Everything else is out of scope.

## Constraints

- Do not change confirmed trading or risk rules.
- Do not enable real-money trading.
- Do not introduce a dependency without stating why an existing one is not enough.
- Preserve documented native-proof limits.
- Keep tests deterministic and offline unless the task is explicitly native.

## Relevant implementation, callers, contracts and tests

| Concern | Location |
|---|---|
| Implementation | |
| Callers | |
| Contracts / schemas | |
| Existing tests | |

## Expected behavior

The behavior after the change, stated so a reviewer can falsify it.

## Acceptance criteria

- [ ] Positive case:
- [ ] Negative / rejection case:
- [ ] No unrelated behavior changed:
- [ ] Documentation updated to match reality:

## Verification

Exact commands, in order. All must be runnable from a clean checkout.

```
python scripts/dev.py inspect
python scripts/dev.py test tests/<module>.py
python scripts/dev.py check --tier L2
```

Prerequisites (interpreter, submodule, MT5, recording, credentials):
Expected artifacts and where they are written:

## Evidence class

State explicitly which of these the task produces. They are not
interchangeable.

- [ ] offline regression
- [ ] recorded comparison
- [ ] MQ5 compile
- [ ] native runtime parity (requires a Windows MT5 runner; cannot be produced offline)

## Dependencies

Other issues, decisions or external conditions. Use `BLOCKED` and name the
external condition if work cannot proceed.

## Out of scope

Explicitly excluded work, so it is not silently absorbed.

## Rollback

How to revert this change safely.