---
name: todo-management
description: Use when creating, updating, or completing TODO documentation. All TODOs live in ./docs/todo/ and must be precise, actionable, and incrementally completed.
---

# TODO Management

## Skill synchronization

Skills are synchronized across agent environments via the pre-commit hook. Do not edit local copies independently — apply changes to `.kilo/skills/` and let pre-commit propagate them.

## Location

All TODO documentation is centralized under:

```text
./docs/todo/
```

Do not create TODO documents elsewhere.

## Requirements

TODOs must be **precise, detailed, and actionable**.

Each TODO should clearly define:

- What needs to be changed
- Why it needs to be changed
- Relevant scope/components
- Required behavior or design
- Important constraints
- Acceptance/completion criteria

Avoid vague TODOs such as "improve this", "fix later", or "refactor this".

## Incremental completion

Do **not** wait until the entire TODO document is completed.

When a part is completed:

- Update that part immediately.
- Add a compact explanation of what was implemented.
- Mark the completed part clearly as **DONE**.
- Keep remaining work explicitly identifiable.

The document must continuously reflect the current completion state.

## History

Do not preserve:

- Code evolution history
- Previous TODO versions
- Documentation evolution
- Changelogs inside TODO documents
- Historical approaches that are no longer relevant

The TODO describes the **current remaining work and current completed requirements**, not its historical evolution.