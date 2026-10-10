# Todo Discipline

A skill that enforces a disciplined todo workflow: create a structured todo list for every task and complete each item as soon as it is safely finishable.

## Purpose

Multi-step work frequently drifts when the agent has no persistent, structured breakdown of what must happen and in what order. Without an explicit todo list, sub-steps get skipped, reordered, or silently deferred, and progress becomes hard to follow.

This skill solves that by mandating two rules for every task:

1. **Todo on each task** — decompose the objective into concrete, ordered `todowrite` items before doing real work.
2. **Finish each item as soon as possible** — mark an item `in_progress` immediately before starting it, complete it (with evidence) the moment it is done, and move to the next, rather than batching completion at the end.

## When to Use

Use this skill for any non-trivial task, especially:

- Code changes spanning multiple files or modules.
- Bug investigations requiring reproduction, root-cause analysis and fix.
- Refactors touching several components.
- Test additions or test-suite migrations.
- Multi-step setup or environment work.
- Any task the agent would otherwise attack as an unstructured bulk edit.

Trigger phrases include:

- "use a todo list", "track this with todos", "break this into steps".
- Any task with 3+ distinct sub-steps.

Trivial single-action requests (e.g. "fix this typo") do not require a todo list.

## How It Works

### Before execution

1. Read the objective and confirm what "done" looks like.
2. Split the objective into ordered, independently verifiable items.
3. Emit the full list via `todowrite` with `pending` status, one item exactly `in_progress`.

### During execution

- Keep exactly one item `in_progress` at a time.
- Start an item only when its prerequisites are satisfied.
- On finishing an item, immediately flip it to `completed` with evidence, then set the next item to `in_progress`.
- Never leave an item half-done while starting another.

### Rules

- **No speculative items** — every todo must map to real, bounded work that can be marked complete.
- **Order matters** — sequence items so each is independently verifiable (read, implement, test, document, verify).
- **Evidence before completion** — an item is `completed` only after the checkable outcome is produced (file written, test passing, command returning the expected result).
- **Continue, don't stop** — a completed todo is a checkpoint, not a reason to pause; proceed to the next item until the list is empty.
- **Stop only when blocked** — halt at a genuine blocker (missing authority, external dependency, Leader decision) and surface it.

### Template

```
- Read context and confirm objective
- <step 1>
- <step 2>
- ...
- Verify final outcome
```

## Anti-Patterns to Avoid

| Avoid | Why | Instead |
|-------|-----|---------|
| Bulk-editing everything then marking all done | Items never reflect real progress | Complete + verify each item before moving on |
| Vague todos like "work on feature" | Not independently verifiable | Name the concrete outcome |
| Multiple items `in_progress` at once | Loses ordering and accountability | Keep one active item |
| Empty/stale todo lists | No signal of what remains | Keep the list live until the objective is done |

## License

MIT
