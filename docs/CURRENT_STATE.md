# Current state

Last verified: 2026-10-04. Written from repository evidence, not from chat
history. If this file disagrees with the working tree, the working tree is
newer: re-run `python scripts/dev.py inspect` and update this file.

## What this project is

An M15 XAUUSD price-action strategy using daily zones, implemented twice:

- **MT5** - the reference EA `mt5/MQL5/Experts/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5`
  plus its envelope `mt5/MQL5/Experts/XauRobustLiveEnvelope.mqh`.
- **Python** - a vectorized strategy engine under
  `src/application/xauusd_trading_strategy_1_vector/` that ports the EA's
  visible transitions and adds an offline execution replay.

The two are separate implementations with documented behavioral differences.
Exact native parity is **not** established. See
[docs/todo/MT5-Python.Divergence.md](todo/MT5-Python.Divergence.md).

## Authority

1. Current explicit Project Leader instruction.
2. Root `AGENTS.md`, plus the `AGENTS.md` of the directory being edited.
3. This file.
4. [docs/architecture.md](architecture.md) for responsibilities and dependencies.
5. [docs/development.md](development.md) for commands, tiers and environment.
6. `docs/todo/` trackers for executable follow-up.
7. Code behavior.

`RULES.md`, `DECISIONS.md`, `TODO.md`, `TEST_STATUS.md`, `EXPERIMENTS.md`,
`FINAL_TEST_REPORT.md`, `LIVE_GATES.md`, `RUNBOOK.md` and `PROJECT_BRIEF.md`
**do not exist** in this checkout. Older instructions referencing them are
stale. Do not reconstruct authority from `legacy_reference/` or
`archive_not_used_trash/`.

## Active paths

| Concern | Location |
|---|---|
| Strategy engine | `src/application/xauusd_trading_strategy_1_vector/` |
| Domain models and schemas | `src/domain/` |
| Datastore, MT5 adapters, result IO | `src/infrastructure/` |
| CLI and offline reports | `src/presentation/` |
| Configuration | `src/config/` |
| Verification wrapper | `scripts/dev.py` |
| Link/anchor checker | `scripts/check_docs_links.py` |
| Active benchmark | `scripts/benchmark_tick_stages.py` |
| Tests | `tests/` (classification in `tests/conftest.py`) |
| MT5 reference source | `mt5/MQL5/Experts/` |
| Verification hook submodule | `br_pre_commit/` (pinned) |
| Review baselines | `.br-pre-commit/ratchet/` |

## Entry points

| Command | Purpose |
|---|---|
| `python -m application.xauusd_trading_strategy_1_vector` | strategy run; signals-only by default, `--execution-config` for replay, `--backtest` for the vectorbt report |
| `python -m application.xauusd_trading_strategy_1_vector.recorded_runner` | recorded native replay and checkpoint comparison |
| `python scripts/dev.py <subcommand>` | all verification |

The cTrader CLI and its `ctrader-open-api`/`twisted` dependencies were removed.
`ctrader-cli` is no longer a console script. Live CTRADER_* credentials remain
in some local `.env` files and must be revoked at cTrader.

## Verified baseline

Measured on Windows / Python 3.14.0, `pandas 3.0.6`, `numpy 2.5.3`,
`pandera 0.33.1`. Re-measure before treating any number as a budget.

| Check | Command | Result |
|---|---|---|
| Collection | `dev.py test --tier offline` | 245 tests collected |
| Offline suite | `dev.py test --tier offline --parallel auto` | 245 passed, ~52 s |
| Unit tier | `dev.py test --tier unit` | 178 passed, ~135 s serial |
| Integration tier | `dev.py test --tier integration` | 17 passed, ~8 s |
| Parity tier | `dev.py test --tier parity` | 50 passed, ~4 s |
| Native tier | `dev.py test --tier native` | **0 tests, exits 3 by design** |
| Focused | `dev.py test tests/test_vectorized_where.py` | 13 passed, ~42 s |
| Lint | `dev.py lint` | pass, ~0.5 s |
| Docs links | `dev.py docs` | 0 broken local links |
| Full mypy | `dev.py typecheck` | **209 pre-existing errors in 76 files** |

`@pandera_validate` dominates test wall time; that is real cost, not noise.

## Known environment constraints

- **No bare tool executables.** `ruff`, `mypy`, `xenon` and `pytest` are not on
  `PATH`; only `python -m <tool>` works. Always use `scripts/dev.py`.
- **The ratchet hook cannot run here.** The pinned `br_pre_commit` submodule
  invokes `ruff`, `mypy` and `xenon` by bare name, so
  `python -m br_pre_commit.src.ratchet` fails with `FileNotFoundError`. It also
  **prunes** `.br-pre-commit/ratchet/baseline_*.json` when run, so do not invoke
  it casually; restore any pruned baseline from Git.
- **Full mypy is not a gate.** The ratchet is the incremental gate. Do not
  "fix" the 209 errors by weakening types or excluding files to get green.
- **`.kilo/kilo.json` holds a literal bearer token** and must stay untracked.
  `.kilo/kilo.json.example` is the sanitized template.

## READY tasks

Ordered, bounded and independently verifiable. Each maps to the checklist in
[docs/todo/agentic-development-optimization.plan.md](todo/agentic-development-optimization.plan.md).

1. Replace the market-row iteration in `the_strategy.py:process_native_stream`
   with an ordered, state-equivalent pandas/NumPy or compiled-kernel
   implementation. Coordinate with
   [vectorized-operation-improment.plan.md](todo/vectorized-operation-improment.plan.md);
   do not start a parallel implementation. Currently recorded as technical debt
   against a confirmed rule.
2. Establish MQ5 compile evidence. Requires MetaEditor on Windows and the
   matching envelope, settings and `ranges.csv` recorded together. No compile
   has been run.
3. Close the remaining gaps in
   [docs/todo/MT5-Python.Divergence.md](todo/MT5-Python.Divergence.md).
4. Reconcile the CLI `.csv` acceptance with `save_results_to_file`, which
   always writes Parquet, and the accepted-but-unused `debug` option.
5. Extract result-processing functions from the strategy `__main__.py` into
   `infrastructure/result_processing/pipeline.py` to remove the bidirectional
   package coupling. Audit imports with AST first.

## Blocked (external)

| Item | Condition |
|---|---|
| Native compile / Strategy Tester evidence | MetaEditor plus a Windows terminal; not runnable offline |
| GitLab Issues/Boards/CI execution | No GitLab endpoint is established in this checkout; `.gitlab-ci.yml` and templates exist but cannot be executed here |
| GitLab MCP | Only if CLI/API proves cumbersome; no endpoint configured |
| Full mypy cleanup | 209 pre-existing errors; needs an explicit baseline decision, not ad-hoc suppression |

## Dirty-state caveat

This file describes the committed state. Always confirm with
`git status` and `python scripts/dev.py inspect` before acting; the working tree
may be ahead of it.