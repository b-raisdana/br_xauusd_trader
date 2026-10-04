# XAUUSD EA and Python research pipeline

Repository for an M15 XAUUSD price-action strategy using daily zones. MT5 strategy and Python signals/offline replay are separate implementations with documented behavioral differences.

## Current source and status

- [MT5 source](mt5/MQL5/Experts/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5) replaces the former MVP/include/generated set. [MT5 README](mt5/README.md) describes actual inputs and visible lifecycle.
- **No compile or runtime proof yet:** the EA and its `XauRobustLiveEnvelope.mqh` envelope are both present under `mt5/MQL5/Experts/`, but no MetaEditor compile or Strategy Tester run has been performed, so neither a successful build nor native parity is claimed.
- [Python package](src/application/xauusd_trading_strategy_1_vector/README.md) implements signals and optional execution replay. Its CLI supports explicit replay economics through `--execution-config`; default mode remains signals-only.
- [Divergence report](docs/todo/MT5-Python.Divergence.md) records current flow, defaults and state differences.
- [State glossary](docs/State-Variables.Glossary.md) explains the [143-row CSV](docs/State-Variables.Glossary.csv).
- [Parity follow-up](docs/todo/MT5-Python.Divergence.md) defines remaining acceptance work. The 2026-09-30 source port has regression coverage; native compile and exact runtime parity remain pending.

## Working in this repository

Start at [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md): active paths, entry
points, the measured verification baseline and the READY task list.

1. Read [AGENTS.md](AGENTS.md), then the `AGENTS.md` of the directory you are
   about to edit (`src/`, `src/application/xauusd_trading_strategy_1_vector/`,
   `tests/`, `mt5/`).
2. `python scripts/dev.py inspect` - read-only environment and repository report.
3. Run every check through `python scripts/dev.py`. Bare `ruff`, `mypy`, `pytest`
   and `xenon` are not on `PATH` here. Tiers, commands and measured timings are
   in [docs/development.md](docs/development.md); responsibilities are in
   [docs/architecture.md](docs/architecture.md).
4. Link and skill consistency: `python scripts/dev.py docs --skills`.

Several former project-control documents have been removed; do not treat their
old links or archived test claims as present acceptance evidence. The Project
Leader owns scope and trading/risk approval; Codex owns implementation and
verification; ChatGPT Work owns research discussion/documentation.

`src/` contains Python implementation; `mt5/` contains the EA and its
documentation; `docs/` contains current state, architecture, development and the
comparison/glossary; `docs/todo/` contains executable follow-up.
`archive_not_used_trash/` and `legacy_reference/` are frozen historical
reference and do not override the current source.
