# XAUUSD EA

Repository-based scientific design, implementation and validation of an M15 XAUUSD price-action strategy using instructor-provided daily Zones.

## Leader dashboard
| Item | Current value |
|---|---|
| Goal | Auditable MVP → Shadow/Demo |
| Market | XAUUSD / M15 / MT5 Real Ticks |
| Current milestone | Engineering reconstruction: Zone/Trend contracts first |
| Status | Repository/runtime baseline audited and executable; strategy implementation pending |
| Live state | Research only |
| Next Leader decision | None |
| GitHub | Not configured; no remote and no GitHub CLI |

## Roles
- Project Leader: goals, priorities, confirmed trading/risk rules, high-impact approvals.
- ChatGPT Work: scientific research and documentation.
- Codex: implementation, tests, environment, Git/GitHub.

## Start a new Work chat
`Read CHATGPT_WORK.md and recover the project from this repository before discussing the scientific question.`

## Start a new Codex chat
`Read AGENTS.md, recover the project from the repository, and continue the next executable task autonomously.`

## Core source of truth
- `docs/PROJECT_BRIEF.md`
- `docs/RULES.md`
- `docs/RULES_ARCHIVE_FUTURE.md`
- `docs/CURRENT_STATE.md`
- `docs/TODO.md`


## Standard control files
- `docs/DECISIONS.md`
- `docs/EXPERIMENTS.md`
- `docs/TEST_STATUS.md`
- `docs/LIVE_GATES.md`
- `docs/RUNBOOK.md`

This level is the default recommendation for a strategy expected to reach Demo or Live.

## Historical material

- `data/ranges.csv` is the canonical migrated daily-Zone input.
- `legacy_reference/PREVIOUS_TECHNICAL_BUNDLE/` preserves historical code, research scripts, settings and test evidence. It is a Regression reference and must not override `docs/RULES.md`.

## Folder structure

```text
XAUUSD_PROJECT_MIGRATION_FINAL_v3/
├─ docs/                 # Source of Truth, decisions, evidence status and runbook
├─ data/                 # Canonical small inputs; ranges.csv is included
├─ src/                  # New current implementation only
├─ tests/                # Current deterministic and integration tests
├─ config/               # Non-secret reproducible configuration
├─ integrations/mt5/     # MT5 integration instructions and adapters
├─ artifacts/            # Regenerable current outputs
└─ legacy_reference/     # Intact historical technical bundle for Regression/Audit
```
