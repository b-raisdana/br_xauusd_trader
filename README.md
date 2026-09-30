# XAUUSD EA and Python research pipeline

Repository for an M15 XAUUSD price-action strategy using daily zones. MT5 strategy and Python signals/offline replay are separate implementations with documented behavioral differences.

## Current source and status

- [MT5 source](mt5/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5) replaces the former MVP/include/generated set. [MT5 README](mt5/README.md) describes actual inputs and visible lifecycle.
- **Build dependency missing:** `XauRobustLiveEnvelope.mqh`. Final platform callbacks/release guards cannot be verified from the supplied file. The live-RC filename is not deployment approval.
- [Python package](src/application/xauusd_trading_strategy_1_vector/README.md) implements signals and optional execution replay. Its CLI supports explicit replay economics through `--execution-config`; default mode remains signals-only.
- [Divergence report](docs/Divergence%20Report%20-%20MT5%20vs%20Python%20vs%20Documentation.md) records current flow, defaults and state differences.
- [State glossary](docs/State-Variables.Glossary.md) explains the [143-row CSV](docs/State-Variables.Glossary.csv).
- [Parity follow-up](docs/todo/Vectorization.Remaining%20not-implemented%20placeholders.md) defines remaining acceptance work. The 2026-09-30 source port has regression coverage; native compile and exact runtime parity remain pending.

## Working in this repository

Read [AGENTS.md](AGENTS.md), inspect the current working tree and follow the linked current evidence. Several former project-control documents have been removed; do not treat their old links or archived test claims as present acceptance evidence. The Project Leader owns scope and trading/risk approval; Codex owns implementation and verification; ChatGPT Work owns research discussion/documentation.

`src/` contains Python implementation; `mt5/` contains the supplied EA and its documentation; `docs/` contains the comparison/glossary; `docs/todo/` contains executable follow-up. `mt5/archive.zip` is historical reference and does not override the supplied current source.
