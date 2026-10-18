# XAUUSD EA and Python research pipeline

M15 XAUUSD price-action research using daily zones. Python columnar signals and optional compiled execution replay are separate from the MT5 EA; exact native runtime parity remains unproven.

## Start

- [Agent contract](AGENTS.md): authority and safety.
- [Current state](docs/CURRENT_STATE.md): recovery and active work.
- [Architecture and task map](docs/ARCHITECTURE.md): ownership, contracts and tests.
- [Runbook](RUNBOOK.md): setup, search and validation.
- [Acceptance tracker](docs/todo/MT5-Python.Divergence.md): remaining native differences.

## Components

| Location | Responsibility |
| --- | --- |
| [Python strategy](src/application/xauusd_trading_strategy_1_vector/README.md) | Columnar signals, optional compiled batch replay, orchestration |
| `src/domain/` | Shared schemas, zone geometry and enums |
| `src/infrastructure/` | MT5 data acquisition, cache and result persistence |
| [MT5 EA](mt5/README.md) | Native strategy and release envelope under `MQL5/Experts/` |
| `tests/` | Regression and marked compiled integration tests |
| `br_pre_commit/` | Git submodule providing hooks and schema validation |
| `docs/todo/` | Focused implementation and acceptance work |

[Pipeline design](docs/TICKs_and_ZONEs_to_SIGNALs.md), [signal-to-order design](docs/SIGNALs_to_ORDERS.md), [order/position design](docs/ORDER_and_POSITION_management.md) and [state glossary](docs/State-Variables.Glossary.md) provide focused behavioral context. Persian translations are companion explanations; resolve discrepancies against source and acceptance evidence.

Archives and local data are retained but excluded from default source search. No profitability or live-readiness claim follows from available source/tests.
