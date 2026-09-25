# Current State

## Snapshot

- Project: XAUUSD EA
- Project level: STANDARD
- Current activity: MVP v2 technical freeze candidate complete; awaiting separate Demo/Shadow authorization and environment acceptance
- Strategy target: MVP v2 Consolidated Rulebook
- Rule status: Active Rulebook implementation is complete for Python contracts and guarded MQL Breakout/Reversal/Pullback protected-entry and Native lifecycle
- Research handoff: MERGED_READY_FOR_IMPLEMENTATION
- Last verified date: 2026-09-08
- Current branch: main
- GitHub sync: PRIVATE `origin/main` — rapid-MVP mode; routine push/PR/remote CI deferred, local Git retained
- Live state: RESEARCH_ONLY

## Source-of-Truth files

The 2026-09-24 vectorized signal update completes reversal and pullback candidate generation; 33 focused tests pass in `.venv`. Pullback fill/pending feedback is optional and explicit; action/execution integration remains a placeholder. The repository gate still fails on a retired test import and missing ratchet module; see `TEST_STATUS.md` for evidence.

The 2026-09-20 entry-point review repaired CLI/debug dispatch, full-day fetch boundaries, causal candle context, export and MT5 error/symbol handling. Twenty focused tests pass; the repository gate remains blocked. Core edits were concurrent and execution placeholders remain; see [flow findings and remaining work](todo/vectorized-entrypoint-flow.md).

- `PROJECT_BRIEF.md`: goal, scope, limits and success criteria
- `RULES.md`: the only active rules; detailed structure and function-like names
- `RULES_ARCHIVE_FUTURE.md`: superseded/rejected/post-MVP and historical crosswalk
- `DECISIONS.md`: rationale for stable decisions
- `EXPERIMENTS.md`: evidence and planned experiments
- `TEST_STATUS.md`: actual status of proofs and gates
- `TODO.md`: execution ledger up to freeze
- `CURRENT_STATE.md`: quick recovery and next action

## Baseline active documented state

- Daily input zones, chain merge under 1.5 USD, and Priority High/Normal.
- Daily trend `NONE → N1 → N2 → N3` without prior-day carry.
- Breakout with Trend at Close and strict 1 USD buffer.
- Reversal Market Touch; Normal max1 and High max2 per broker day.
- Pullback Conservative with 0.20 penetration, five-candle window, Normal1/High∞ and Multi-PB per BO.
- Strict Pullback Trend with Current Candle/Same-Bar, pre-zone 1 USD, Reversal block on real touch, and reversible one-step TP extension.
- Free Space must be strictly greater than 3 USD (`<=3` blocks), Initial Stop cap 6 USD, and Initial Target at least 6 USD from entry.
- Native RF and unlimited Profit Protection on `BASE_R_USD=6`.
- Fixed lot 0.01, concurrency 3/5 for 200/300 USD, Daily Loss 20% and GROSS15.
- Session flatten 5 minutes before end and Restart fail-closed.

This baseline is `IMPLEMENTED/TESTED/FROZEN` at version `mvp-v2.0.0` for Research/Strategy Tester; this state is not authorization for Demo or Live.

## Status glossary

- `CURRENT CONFIRMED RULE`: a rule confirmed, even if not yet implemented/tested.
- `TESTED HISTORICAL CONTROL`: behavior with historical evidence that may be superseded.
- `APPROVED FOR TEST`: before promotion, a rule is not considered executable.
- `REJECTED / RETIRED`: should not be implemented in the current MVP.
- `POST-MVP`: retained but not an MVP blocker.
- `UNRESOLVED`: not guessable without a Project Leader decision.

## Current blocker

- None for local code production, isolated Strategy Tester smoke, or normal GitHub synchronization.
- Final Rulebook/Code freeze does not require visual review; it requires complete stored acceptance evidence and the canonical final report.

## Leader decisions

- No open decisions are needed to start code production.
- Quantitative acceptance criteria, duration of Shadow, Broker Live, capital Live, and any subsequent risk increase all require a Project Leader decision after evidence is presented.

## Next autonomous action

The MVP package is ready for Freeze/Tag. The next action is preparation and execution of Demo/Shadow in the target broker environment only after separate leader authorization; Live and risk increases remain prohibited.
