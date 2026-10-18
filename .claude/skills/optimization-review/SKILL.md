---
name: optimization-review
description: Use after finishing a functional change to one or more Python files under src/ (before moving to unrelated work), or when explicitly asked to audit a file/module for optimization debt. Reviews the file against a fixed set of optimization factors, logs weaknesses and concrete optimization opportunities to docs/todo/performance-optimization.plan.md with a priority, and gates any later hot-path edit behind a test/mutation-safety check. Review and logging only — the optimizations themselves are implemented later as separate, normally-reviewed changes.
---

# Optimization review

Goal: never let an optimization opportunity found while working in a file get lost, and never let a later "optimize this" edit silently change behavior. This skill only reviews and logs; it does not implement — implementation is a separate later change that goes through the normal edit + test + pre-commit flow.

## when to run this

After a functional change to a Python file under `src/` is working (tests green), before moving on to the next file or ending the session — review that file once while it's fresh, not retroactively in a batch. Also run on demand as a standalone audit of a chosen file/module (no functional change required), including a batch audit of everything currently modified.

## scoping the review

Enumerate the actual target set with `git status --porcelain` / `git diff --stat` — don't rely on memory of what changed. `--stat` also tells you where to spend time: a file with a 2-10 line diff (an import swap, a mechanical rename) rarely hides more than the diff itself; a file with a 100+-line diff got real logic changes and is worth reading in full, not just the hunk. For any function you're about to flag, grep the repo for near-duplicate names/signatures before logging it as a novel finding — several of the highest-value findings in this repo turned out to be one of two parallel implementations of the same thing (see the duplication/dead-code factor below), which single-file diff-reading alone won't surface.

## optimization factors

Check the modified file against each factor below. Every factor but the last three is already owned by an existing skill — read that skill for the actual how-to; this list exists so a review doesn't skip one.

| factor | what to look for | reference |
| --- | --- | --- |
| vectorization | Python-level loops over rows/samples/dates (`iterrows`, `apply(axis=1)`, manual `while`/`for` slicing) that could be array/DataFrame ops | [project-decisions](../project-decisions/SKILL.md) |
| redundant computation / caching | the same derived data (indicators, labels, any artifact) recomputed or re-fetched across calls with the same effective inputs | [duckdb-cache-persistence](../duckdb-cache-persistence/SKILL.md) |
| concurrency / blocking I/O | sequential network/disk calls or independent CPU-bound work (symbols/timeframes/folds) that could run concurrently | measure independent work before adding concurrency |
| library delegation | hand-rolled algorithm/transform where a well-maintained library already does it, usually faster | prefer existing mature dependencies |
| algorithmic complexity | wrong-order algorithm/data structure for the data size (e.g. linear scan/repeated `.append`+search where a sorted index, set, or hash map gives a better complexity class); no dedicated skill owns this — judge directly against the data volumes in [task map](../../../docs/ARCHITECTURE.md) | — |
| memory / resource footprint | oversized dtypes left at pandas defaults, avoidable `.copy()`s, fully materializing a range that could stream/chunk | measure peak memory and batch sizes |
| complexity as an optimization blocker | a function ranked worse than xenon's `B` (the same threshold `.pre-commit-config.yaml`'s incremental ratchet blocks regressions on) is both a correctness risk and unsafe to optimize until untangled | [pre-commit-check](../pre-commit-check/SKILL.md) |
| duplication / dead code / reuse | two parallel implementations of the same operation (a second read-or-generate flow, a copy-pasted near-duplicate function, a "v2" variant nothing imports), or code with zero external callers (confirm with a repo-wide grep before flagging) | [project-decisions](../project-decisions/SKILL.md) ("don't fork a second copy of a module"), [duckdb-cache-persistence](../duckdb-cache-persistence/SKILL.md) ("one cache per artifact type, not one per caller") |

Log a finding for a real instance of a factor, not a hypothetical one — don't flag "could theoretically use `numba`" without a concrete bottleneck reason tied to this repo's actual data volumes.

## priority

Three inputs, judged together, not summed mechanically:

- **hotness** — is the function on a path executed repeatedly at scale (per-sample, per-quarter, per-training-step, a symbols×timeframes loop — the dataset-generator producer loops calling `train_data_of_mt_n_profit()` ~100x/quarter are the reference shape, see [duckdb-cache-persistence](../duckdb-cache-persistence/SKILL.md)), or is it one-time setup/config/notebook/migration/CLI code?
- **expected win** — order-of-magnitude (a per-row loop vectorized, an O(n)-redundant recompute eliminated — typically 10-1000x only when demonstrated by representative measurements) vs. incremental (<2x, not worth disturbing working code for).
- **change risk** — existing test coverage (characterization/unit/regression — see [test-strategy](../test-strategy/SKILL.md)) and structural complexity (xenon rank) of the function being touched.

| priority | shape |
| --- | --- |
| P0 | hot path + order-of-magnitude win + coverage already exists or is cheap to add |
| P1 | hot path + big win but high risk (prerequisite is writing tests / passing the mutation-safety check below, not the optimization itself yet) — or hot path + moderate win — or cold path with an order-of-magnitude win worth doing opportunistically |
| P2 | cold path regardless of win size, or any path with a marginal (<2x) win |

For dead or duplicate code, confirm dynamic imports, CLI entry points and external consumers before choosing removal or consolidation. Prioritize demonstrated maintenance cost and regression risk; a search with no callers alone does not prove deletion safe.

## logging findings

Append each finding to [docs/todo/performance-optimization.plan.md](../../../docs/todo/performance-optimization.plan.md) under the matching priority section, one line per finding:

```text
- **[P0] `training_datasets.py:142` `train_data_of_mt_n_profit`** — weakness: recomputes `classic_indicators` on every call inside a ~100x/quarter loop. Optimization: hoist into the existing `_cached_training_frames()` memo. Factor: caching. Hot path: yes (dataset-generator producer loop). Coverage: characterization test at `tests/characterization/...`. Mutation-safety: pending.
```

Include: priority, `file:line` + function name, the weakness, the concrete optimization (not "improve this" — name the actual technique/pattern), which factor(s), hot-path justification, current test coverage, and mutation-safety status (`pending` until the check below has actually run). Follow [markdown-formatting](../markdown-formatting/SKILL.md) and [compact-markdown](../compact-markdown/SKILL.md) for the edit itself — one line per entry, no filler.

## mutation-safety gate — required before implementing (not before logging) a P0/P1 finding

Use characterization-test discipline narrowly: one function, once, immediately before its optimization. Do not add routine per-commit mutation-testing overhead.

Applies only when the edit could plausibly change runtime behavior. A purely mechanical change — consolidating import statements, deleting code already confirmed to have zero external callers, comment/dead-code cleanup, a hoist-invariant-out-of-loop where the hoisted expression is provably the same value every iteration — has its equivalence provable by inspection, not by test; don't gate those behind writing tests first, that's overhead the change doesn't need. The gate is for changes where behavior-preservation is genuinely not obvious: replacing a hand-rolled algorithm with a library call, merging two independent implementations into one, changing what gets computed/cached and when.

For a finding that does need it — a function already relied upon on a hot/production path (not new code, not a one-off script) where the edit changes real logic — before making the real optimization edit:

1. Confirm characterization/unit/regression coverage exists for the function's *current actual* behavior — [test-strategy](../test-strategy/SKILL.md)'s characterization discipline: pin what it really outputs today, never a hand-derived "should" value. Write it first if missing.
2. Temporarily introduce one small deliberate behavior-changing edit into the function (a mutant: flip a comparison operator, off-by-one a boundary, swap a branch) — never commit this.
3. Re-run exactly the tests from step 1 and confirm at least one fails. A mutant that survives (all tests still pass) means the coverage is a false safety net — strengthen or add tests until a representative mutant is caught, before proceeding.
4. Revert the mutant, then make the real optimization edit, keeping the same tests green throughout.

Update the todo entry's mutation-safety field to `done (YYYY-MM-DD)` once this has run.

## landing the optimization — pre-commit / QC stays enforced

Already wired for every file under `src/`, nothing new to configure: [.pre-commit-config.yaml](../../../.pre-commit-config.yaml) runs ruff, the mypy/ruff/xenon incremental ratchet, and the pytest fast gate on every commit touching `src/**/*.py` (mechanics: [pre-commit-check](../pre-commit-check/SKILL.md)).

- Never `git commit --no-verify` an optimization commit to dodge a ratchet failure — a new mypy/ruff/xenon violation from an "optimization" is itself a signal the change made the function harder to reason about; fix that before landing, don't bypass it.
- The ratchet blocks new regressions only, not pre-existing debt in the touched file — stay scoped to the optimization, don't scope-creep into unrelated cleanup of the file just because it's open.
- The pytest fast gate is exactly the suite the mutation-safety check exercised, so it should already be green by construction going into commit.

## what this skill does not do

Does not edit the reviewed file's logic, does not implement any listed optimization, does not run the mutation-safety check at review time — those all happen later, as their own change, when a P0/P1 item is actually picked up off the todo.
