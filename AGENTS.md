# Agent execution contract

## Start here

Read [current state](docs/CURRENT_STATE.md), inspect `git status --short` and the relevant diff, then use [the task map](docs/ARCHITECTURE.md). Commands and prerequisites live in [RUNBOOK.md](RUNBOOK.md).

## Authority and ownership

- Current explicit Project Leader instructions take precedence. Confirmed trading/risk rules override code; escalate unresolved contradictions. Never turn hypotheses or archived behavior into confirmed rules.
- No consolidated RULES/DECISIONS register currently exists. Consult behavioral documents and the [acceptance tracker](docs/todo/MT5-Python.Divergence.md); code describes behavior but does not prove native parity. If confirmed Rules/Decisions are introduced, they outrank current state, TODOs, README and code, in that order. Experiments and historical evidence never activate rules.
- Project Leader owns scope, scientific acceptance and trading/risk approval. Codex owns implementation, tests, debugging, environment and state synchronization. ChatGPT Work owns research/handoffs and does not modify implementation by default.
- `archive_not_used_trash/` and `mt5/archive.zip` are regression/reference inputs, never active specifications.

## Execute and verify

- Preserve unrelated changes and secrets. Inspect code before editing; choose safe reversible defaults. Correctness > speed > elegance; avoid speculative abstractions and dependencies.
- Complete coherent batches of implementation, tests and documentation. Checkpoints and status questions do not end the authorized objective; continue related safe work without routine approval.
- Use targeted tests during a batch and the appropriate full gate at a major boundary. Never disable checks, weaken assertions or claim PASS without evidence. Reuse unchanged expensive evidence for reporting.
- Update current state and relevant work under `docs/todo/`. Read task-specific skills only when applicable. Edit shared skills under `.agents/skills/`; mirrors exist for tool discovery and must remain identical.
- Use narrow `rg` searches; explicitly name archive/mirror paths when needed. Do not load entire logs, datasets, notebooks or handoffs for routine recovery.
- Keep Git history/origin. Batch local checkpoints when authorized by the active session; do not create commits, branches, pushes or PRs without explicit authorization. Remote CI is manual, not a routine local gate.

## Approval and trading boundaries

- Escalate changes to scope, confirmed rules, acceptance criteria, destructive/irreversible actions, credentials/security, billing, public release, deployment, real-money enablement or increased live risk.
- Routine naming, dependencies, refactoring, tests, formatting and reversible technical choices need no Leader decision.
- Avoid look-ahead, leakage, survivorship bias and hidden cost assumptions. Make material spread, slippage, latency and broker constraints explicit. Small samples do not establish profitability.
- Separate Python research and MT5 execution require parity evidence. Passing tests/backtests and Live-RC filenames never authorize real-money deployment.
