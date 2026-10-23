# Current state

## Recover

Use [AGENTS.md](../AGENTS.md), [task map](ARCHITECTURE.md) and [runbook](../RUNBOOK.md); inspect the working tree before editing. No consolidated Rules/Decisions register exists. Do not require removed project-control files or infer live approval from archived evidence.

## Implementation

Python produces columnar signals and optional compiled batch execution replay. MT5 EA and release envelope are present under `mt5/MQL5/Experts/`. Native runtime parity remains unproven; Python reporting is not a parity oracle. [Acceptance tracker](todo/MT5-Python.Divergence.md) and [replay work](todo/vectorized-execution-replay.md) own detailed remaining acceptance requirements.

The [Farsi signal-to-order FSM](SIGNALs_to_ORDERS.FSM.fa.drawio.svg) translates all 118 labels of the English diagram and retains editable Draw.io data. Graph structure and rendered layout were checked on 2026-10-19; this translation does not revalidate the original diagram's historical source claims.

The project configures the local Draw.io MCP server in `.codex/config.toml` (`npx -y @drawio/mcp`). Codex loads project MCP settings only for trusted projects; restart or reload Codex after trusting this checkout. Use the server for `*.drawio.svg` files as embedded Draw.io graphs, keeping graph data and SVG rendering synchronized.

## Agentic maintenance

File logging and agent command captures belong under repository `logs/`; see [execution contract](../AGENTS.md). Application logging defaults to `logs/`, and hook reports use `logs/pre-commit/`. The [maintenance tracker](todo/agentic-maintenance.md) records the source check.

Agentic maintenance covers navigation, source guidance and repeatable verification. [Clean-install reproducibility](todo/environment-reproducibility.md) is separate P2 setup work; sharing a venv alone does not establish a fault, and per-sidecar venv migration is optional.

Shared skills originate in `.agents/skills/`; only Claude and Kiro need physical mirrors. Copilot, Kilo and Devin use the shared folder. `.kilo/skills/` retains only `kilo-only-todo-discipline`; `.devin/` was empty and has been removed, including all empty skill directories. Kilo and Devin are excluded from sync sources and destinations. Root sync settings are paired with pinned hook-submodule commit `f262014`. The [maintenance tracker](todo/agentic-maintenance.md) now lists only remaining work; its 2026-10-19 review passed the repository checker and 10 isolated tooling tests; the audit's 2026-10-17 counts describe its earlier baseline.

The [audit and validation report](AGENTIC_AUDIT.md) records baseline, changes, evidence and limitations. The 2026-10-19 P2 lint/type batch passes broad Ruff/format checks and removes 22 mypy diagnostics; broad mypy remains open at 655 errors in 69 files. This maintenance work changes navigation/tooling, not trading algorithms or live enablement. Preserve the pre-existing diagram relocation (`docs/diagrams/orders-fsm.drawio` → `docs/ORDER_and_POSITION_management.FSM.drawio`).
