# Current state

## Recover

Use [AGENTS.md](../AGENTS.md), [task map](ARCHITECTURE.md) and [runbook](../RUNBOOK.md); inspect the working tree before editing. No consolidated Rules/Decisions register exists. Do not require removed project-control files or infer live approval from archived evidence.

## Implementation

Python produces columnar signals and optional compiled batch execution replay. MT5 EA and release envelope are present under `mt5/MQL5/Experts/`. Native runtime parity remains unproven; Python reporting is not a parity oracle. [Acceptance tracker](todo/MT5-Python.Divergence.md) and [replay work](todo/vectorized-execution-replay.md) own detailed remaining acceptance requirements.

## Agentic maintenance

The [audit and validation report](AGENTIC_AUDIT.md) records baseline, changes, evidence and limitations. This maintenance work changes navigation/tooling, not trading algorithms or live enablement. Preserve the pre-existing diagram relocation (`docs/diagrams/orders-fsm.drawio` → `docs/ORDER_and_POSITION_management.FSM.drawio`).
