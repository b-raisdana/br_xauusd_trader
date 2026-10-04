---
name: quality-gate
description: Use before declaring implementation complete, committing a milestone, creating a release candidate or preparing a live gate.
---

# Quality Gate

Run gates through `python scripts/dev.py check --tier <level>`. The wrapper
preserves nonzero exits and refuses empty test selections; running the tools by
hand skips both protections.

## Progression

| When | Gate |
|---|---|
| Before edits; small changes | `check --tier L0` |
| Each fix loop | `dev.py test <path-or-nodeid>` |
| Coherent batch | `check --tier L2` |
| Boundary changes | `check --tier L3` |
| Milestone / release candidate | `check --tier L4` |

Reserve L4 for a major milestone, a final MVP candidate, or a safety-critical
change. Do not rerun an unchanged expensive gate merely to create a Git
checkpoint; reuse the persisted evidence instead.

## Additional pre-commit checks

- Secret scan of the diff, including new config examples. `.kilo/kilo.json` and
  `.env` hold literal local credentials and must stay untracked; committed
  examples carry placeholders only.
- Documentation links resolve: `python scripts/dev.py docs`.
- `git diff` reviewed for unrelated formatting or cleanup.
- Submodule identity and evidence included in the review when the pointer moved.
- Fixture bytes and hashes preserved.

## Live gate

A passing backtest is not permission for real-money deployment. Enabling
real-money trading is always a Project Leader decision and is never implied by a
green gate. Before any demo or live discussion, load the `release-live-gate`
skill.

## Rules

Fix failures caused by the work. Do not disable a check to obtain a green
result, and do not weaken a schema or assertion to make a change pass. Record
evidence with commands, environment, selected counts and skips.