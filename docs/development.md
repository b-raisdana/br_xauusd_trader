# Development

Environment profiles, commands and verification tiers. Companion to
[CURRENT_STATE.md](CURRENT_STATE.md) for state and
[architecture.md](architecture.md) for responsibilities.

## Setup

`pyproject.toml` is the **only** dependency manifest. `requirements.txt` and
`requirements-dev.txt` were removed because they duplicated it and drifted.

```powershell
python -m pip install -e ".[dev]"
```

| Profile | Contents | Needed for |
|---|---|---|
| core (`dependencies`) | pandas, NumPy, pandera, pydantic, pyarrow, duckdb, plotly, typer, br-logging | running the strategy |
| `dev` | ruff, mypy, pytest, pytest-xdist, pytest-asyncio, radon, pre-commit, numba, vectorbt | all offline gates |
| `native` | MetaTrader5 (`sys_platform == 'win32'`) | broker automation, Windows only |
| `report` | pandas-ta, optuna, prophet, pyiceberg, jupyter stack | optional research, no gate depends on it |

Requires Python `>=3.12`. CI runs 3.12. MetaTrader5 is Windows-only and is
never installed on a Linux runner.

## Environment variables

Two independent flags, frequently confused:

| Variable | Read by | Effect |
|---|---|---|
| `DLF_ENVIRONMENT` | `config.Config` (`env_prefix="DLF_"`) | `production` turns **off** `Config.check_assertions`, weakening validation |
| `ENVIRONMENT` | `br_pre_commit` tooling only | hook/pandera wrapper verbosity; **no** effect on application assertions |

Setting `ENVIRONMENT=production` does not silence application assertions. Only
`DLF_ENVIRONMENT=production` does, which is why correctness gates must leave
`DLF_ENVIRONMENT` at `development`. `.env.example` documents both.

`.env` and `.kilo/kilo.json` hold literal local credentials and stay untracked.
Committed examples carry placeholders only.

## Commands

Always go through `scripts/dev.py`. Bare `ruff`, `mypy`, `pytest` and `xenon`
are **not** on `PATH` in the documented environment.

| Command | Kind | Purpose |
|---|---|---|
| `dev.py inspect` | read-only | interpreter, tooling, submodule, branch, dirty count, collected tests |
| `dev.py test <paths>` | read-only | focused serial run; refuses a zero selection |
| `dev.py test --tier <tier>` | read-only | classified selection, add `--parallel auto` where measured |
| `dev.py lint` | read-only | `ruff check` + `ruff format --check` on `src tests scripts` |
| `dev.py format <paths>` | **mutating** | `ruff check --fix` + `ruff format` |
| `dev.py typecheck [paths]` | read-only | mypy |
| `dev.py check --tier <L0..L4\|ratchet\|all>` | read-only | composes gates, preserves nonzero exits |
| `dev.py benchmark` | read-only | times the active controller path |
| `dev.py build [--smoke]` | read-only | builds the wheel; `--smoke` installs it outside the checkout |
| `dev.py docs` | read-only | validates local links and anchors |

Exit codes: `0` pass, the failing tool's own code for a gate failure, `3` for a
contract/precondition error such as a zero test selection.

### Test tiers

| Tier | Selection | Tests | Notes |
|---|---|---|---|
| `unit` | `-m unit` | 178 | deterministic in-process |
| `integration` | `-m integration` | 17 | filesystem, subprocess, packaging, optional tooling |
| `parity` | `-m parity` | 50 | recorded / synthetic comparison |
| `native` | `-m native` | 0 | **empty by design**; exits 3. Native evidence comes from MT5, not pytest |
| `perf` | `-m perf` | 0 | **empty by design**; timing lives in `dev.py benchmark` |
| `offline` | `not native and not perf` | 245 | everything runnable offline |
| `all` | `not perf` | 245 | same set today |

Classification lives in `tests/conftest.py` `TIER_BY_MODULE`. An unclassified
module fails collection instead of silently joining the default selection.

## Measured timings

Windows, Python 3.14.0. Provisional; re-measure before enforcing as budgets.

| Gate | Time |
|---|---|
| L0 `inspect` | ~5 s |
| L1 single node id | 3 s |
| L1 one module (13 tests) | 42 s |
| L2 offline suite, `-n auto` | 52 s |
| L2 offline suite, serial | 135 s |
| L2 lint | 0.5 s |

The unit tier is slow because `@pandera_validate` runs on the hot path. A
whole-module L1 run misses the provisional 30 s target; a node-id run meets it.

## Hooks

`pre-commit run` covers **staged files only**. It does not prove unstaged edits
were checked. `--all-files` is broader and mutating.

There is deliberately no pytest hook: the full unit tier is ~135 s serially and
pytest exits 5 on an empty selection. Use `dev.py test <paths>` while iterating
and CI for the enforced tiers.

The `incremental-ratchet` hook requires bare `ruff`, `mypy` and `xenon` on
`PATH`; it fails with `FileNotFoundError` otherwise. It also prunes
`.br-pre-commit/ratchet/baseline_*.json`, so do not run it casually and restore
any pruned baseline from Git.

## CI

`.github/workflows/ci-python.yml` and `.gitlab-ci.yml` run the same
`dev.py` commands: preflight, lint, offline suite, integration and parity
tiers, docs links, and a wheel build with an installed smoke import.

A green pipeline is **offline regression evidence only**. It is not native
compile and not native runtime parity. No GitLab endpoint is established in this
checkout, so the GitLab pipeline and templates are provided but not executable
here.

## Evidence classes

Not interchangeable; automation must never let them be confused:

1. offline regression (`dev.py test`)
2. recorded comparison (`recorded_runner` **with** `--expected`)
3. MQ5 compile (MetaEditor, Windows)
4. native runtime parity (Strategy Tester)

Replay without `--expected` is not a comparison. `compared=false` never
establishes parity.

## Full mypy

`dev.py typecheck` currently reports **209 pre-existing errors in 76 files**.
The incremental ratchet is the enforced gate. Do not clear this by weakening
types, adding blanket ignores or excluding files. Clearing it is an explicit
reviewed decision, recorded separately.