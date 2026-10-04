# AGENTS.md - src/

Delta to the root contract. Read the root `AGENTS.md` first; this file does not
repeat it.

## Dependency direction

Intended: `presentation -> application -> domain`, with `infrastructure`
implementing ports the application needs. `config` and `helper` are leaves.

**Known violation:** `application` imports `infrastructure.result_processing`,
which imports `application...domain.schema`. Bidirectional package coupling, not
a runtime circular import. Audit with AST before moving contracts; see
[docs/CURRENT_STATE.md](../docs/CURRENT_STATE.md).

Do not migrate to `src/xauusd/` or rename the strategy package without a
demonstrated benefit.

## Rules for code in this tree

- Any function with a `pt.DataFrame[Schema]`-annotated parameter or return must
  carry `@pandera_validate` (from `br_pre_commit`). An annotation without the
  decorator is silently unenforced. Negative schema tests are required, not
  optional.
- **No Python per-tick or per-candle iteration.** `for`/`while`, `iterrows`,
  `itertuples`, row comprehensions, `zip`/`enumerate` over market rows, row-wise
  `apply`, and `map` with a Python callback are all violations. Python iteration
  is a last resort only over non-market-row units (files, daily partitions,
  instruments, fixed config fields). The operation priority and the compiled
  Numba fallback rule are in
  [.agents/skills/project-decisions/references/vectorized-pandas-numpy.md](../.agents/skills/project-decisions/references/vectorized-pandas-numpy.md).
- Configuration binds through the `BaseContextConfig.use()` context mechanism.
  Do not mutate module-level config objects implicitly.
- No hard-coded credentials or developer-specific absolute paths. Derive
  repository roots from `__file__`.
- No bare `except`. Catch specific exception types. No ambiguous single-letter
  variable names such as `l`.
- Keep the ratchet budget in mind: `src/` is the ratchet target (300 lines max
  per file, plus mypy/ruff/xenon regression counts). Check with
  `python scripts/dev.py check --tier ratchet` rather than adding a new hook.
- Legacy vector helpers are a **compatibility surface**. Do not treat them as
  the active path, and do not benchmark them as if they were.

## Verification

```
python scripts/dev.py lint
python scripts/dev.py test --tier unit --parallel auto
python scripts/dev.py test --tier parity
```

Full mypy is not a gate (209 pre-existing errors); the ratchet is. Do not clear
that backlog by weakening types or excluding files.