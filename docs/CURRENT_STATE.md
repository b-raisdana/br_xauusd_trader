# Current state

## Recover

Use [AGENTS.md](../AGENTS.md), [task map](ARCHITECTURE.md) and [runbook](../RUNBOOK.md); inspect the working tree before editing. No consolidated Rules/Decisions register exists. Do not require removed project-control files or infer live approval from archived evidence.

## Implementation

Python produces columnar signals and optional compiled batch execution replay. MT5 EA and release envelope are present under `mt5/MQL5/Experts/`. Native runtime parity remains unproven; Python reporting is not a parity oracle. [Acceptance tracker](todo/MT5-Python.Divergence.md) and [replay work](todo/vectorized-execution-replay.md) own detailed remaining acceptance requirements.

## Agentic maintenance

File logging and agent command captures belong under repository `logs/`; see [execution contract](../AGENTS.md). Application logging defaults to `logs/`, and hook reports use `logs/pre-commit/`. The [maintenance tracker](todo/agentic-maintenance.md) records the source check.

Shared skills originate in `.agents/skills/`; only Claude and Kiro need physical mirrors. Copilot, Kilo and Devin use the shared folder. `.kilo/skills/` retains only `kilo-only-todo-discipline`; Kilo is excluded from sync sources and destinations. Root sync settings and the accompanying hook-submodule revision must travel together. Current checks and remaining prerequisites are recorded in the [maintenance tracker](todo/agentic-maintenance.md); the audit's 2026-10-17 counts describe its earlier baseline.

The [audit and validation report](AGENTIC_AUDIT.md) records baseline, changes, evidence and limitations. This maintenance work changes navigation/tooling, not trading algorithms or live enablement. Preserve the pre-existing diagram relocation (`docs/diagrams/orders-fsm.drawio` → `docs/ORDER_and_POSITION_management.FSM.drawio`).
