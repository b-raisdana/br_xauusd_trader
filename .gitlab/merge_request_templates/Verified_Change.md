---
name: Verified Change
description: Merge request body that carries reproducible, scoped verification evidence
---

## Goal

What behavior changed, in one or two sentences.

## Scope

Files and areas touched. Call out mechanical relocation separately from
behavior change, and submodule pointer updates separately from submodule
implementation.

## Source

- Branch / base:
- Pinned submodule commit:
- Inputs used (files, recordings, hashes):

## Verification actually run

Commands, in order, with the real result. A command that was not run must be
listed under Skips, never under Results.

| Command | Result |
|---|---|
| `python scripts/dev.py inspect` | |
| `python scripts/dev.py lint` | |
| `python scripts/dev.py test --tier <tier>` | |
| `python scripts/dev.py check --tier L2` | |

Environment: interpreter version, platform, dependency profile installed.

## Skips and BLOCKED prerequisites

Anything not executed and why. Zero-selection test tiers must be reported here,
not omitted.

## Evidence class

- [ ] offline regression
- [ ] recorded comparison
- [ ] MQ5 compile
- [ ] native runtime parity

A green offline pipeline is **not** native parity. Replay without `--expected`
is **not** a comparison.

## Risk and native limits

What could be wrong that these checks cannot detect. Explicitly state whether
native compile or tester evidence was produced.

## Artifacts

Paths to retained outputs (wheels, recordings, checkpoint dumps, reports).

## Rollback

How to revert safely, and whether fixture bytes or hashes must be restored.

## Related issue

Closes #<issue>.