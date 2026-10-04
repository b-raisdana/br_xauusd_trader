---
name: pre-commit-check
description: Use after finishing any code modification in this repo, before the final response, to run the repository gates and confirm the edits did not break formatting, linting, documentation links, or test tiers.
---

# Pre-Commit Check

## End-of-Edit Gate

Run the wrapper, not raw tools. Bare `ruff`, `mypy`, `pytest` and `xenon` are
not on `PATH` in the documented environment:

```powershell
python scripts/dev.py lint                 # read-only
python scripts/dev.py test <paths>         # focused, serial
python scripts/dev.py check --tier L2      # offline suite + lint
python scripts/dev.py docs                 # local links and anchors
```

`pre-commit run` covers **staged files only**. It does not prove unstaged edits
were checked. `--all-files` is broader and mutating. Use it only for broad
changes or shared configuration.

## Performance budgets

No pytest pre-commit hook exists, so there is no commit-time test budget. The
measured costs on the documented machine (Windows, Python 3.14) are: single node
id 3 s, one module ~42 s, offline suite ~52 s with `-n auto` versus ~135 s
serial. `@pandera_validate` dominates. These are baselines to re-measure, not
enforced budgets.

## Failure Handling

If a hook auto-modifies files, inspect the diff, keep intended fixes, and rerun.

If a gate fails:

- Fix failures caused by the current edits.
- Do not clean up unrelated pre-existing failures unless they block proving the
  current change and the smallest practical fix is clear.
- For test failures, use the `pytest` skill before debugging or rerunning.
- For Python files under `src/`, the `performance-review` skill still applies
  after functional edits.

### The incremental mypy/ruff/xenon/loc ratchet

The `incremental-ratchet` hook runs `python -m br_pre_commit.src.ratchet` from
the pinned `br_pre_commit/` submodule over `src/**/*.py`.

**Environment precondition:** the submodule invokes `ruff`, `mypy` and `xenon`
as **bare executables**. In an environment where only `python -m <tool>` works,
the hook fails with `FileNotFoundError`. Use
`python scripts/dev.py check --tier ratchet`, which reports that precondition
explicitly instead of failing obscurely.

**Mutation warning:** running the ratchet **prunes**
`.br-pre-commit/ratchet/baseline_*.json`. Do not invoke it casually, and restore
any pruned baseline from Git with
`git restore .br-pre-commit/ratchet/` before committing.

It blocks only when a vector's **project-wide** count regresses past
`baseline*.json` **and** staged `src/` Python files report a nonzero count for
that vector, never for pre-existing debt alone. When it blocks:

- Added files (`A`) have no pre-existing version; every violation on them is
  attributable to this change and must be fixed.
- Modified files (`M`) only need violations this edit introduced; diff the error
  count against `git show HEAD:<path>` through the same tool if unclear.

A blocked gate means the commit did not happen. Never report the task done
while it is blocked without saying so explicitly.

## Reporting

State whether the gate passed. If not, name the failing hook or tier and say
whether the failure looks related to the current edits.
