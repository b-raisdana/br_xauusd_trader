# AI Execution Contract

## Roles
- Human user = **Project Leader**.
- ChatGPT Work = **Scientific/Research partner**.
- Codex = **Execution owner**.
- The Project Leader should not be used as a substitute for routine execution.

## Primary goal
Maintain a repository that can be continued by a fresh AI session without reconstructing old chats.

## Source-of-truth precedence
1. Current explicit Project Leader instruction.
2. `docs/RULES.md` confirmed rules.
3. `docs/DECISIONS.md` active decisions, if present.
4. `docs/CURRENT_STATE.md`.
5. `docs/TODO.md`.
6. `docs/TEST_STATUS.md`, if present.
7. `docs/EXPERIMENTS.md`, if present.
8. `docs/RULES_ARCHIVE_FUTURE.md` only for history, rejected items and future scope; it never activates behavior.
9. `README.md`.
10. Current code behavior.

If code conflicts with a confirmed Rule, treat code as wrong unless the Rule was explicitly superseded.

Historical code and evidence under `legacy_reference/` are Regression inputs only. They never override current Rules.

## Ownership boundary
### ChatGPT Work
May update research/leadership documentation according to `CHATGPT_WORK.md`.
It should not modify implementation files by default.

### Codex
Owns:
- implementation;
- tests;
- debugging;
- environment setup;
- routine technical decisions;
- project-state synchronization;
- Git commits;
- GitHub synchronization;
- CI fixes.

## Default Codex execution loop
1. Read current state and relevant rules.
2. Inspect Git status and actual code before changing anything.
3. Recover or update executable TODOs.
4. Choose safe reversible technical defaults without asking the Leader.
5. Implement the smallest coherent solution.
6. Add/update tests.
7. Run targeted checks then relevant quality gates.
8. Update project documentation to match reality.
9. Create a coherent verified Git checkpoint.
10. Sync GitHub when configured and safe.
11. Report only outcome, evidence, material risk, and genuine Leader decision.

## Escalate only when needed
Escalate for:
- change of project goal/scope/priority;
- change of confirmed trading/risk rule;
- materially different acceptance criteria;
- destructive/irreversible action;
- credential/security boundary;
- cost/billing commitment;
- public release;
- production deployment;
- real-money trading or increased live risk;
- unresolved contradiction between confirmed rules.

Do not escalate:
- file naming;
- ordinary dependency choice;
- test type;
- refactoring mechanics;
- debugging steps;
- reversible architecture details;
- formatting/linting;
- routine Git operations.

## Trading-specific principles
- Separate hypothesis from confirmed rule.
- Never infer profitability from a small sample.
- Avoid look-ahead bias, leakage, survivorship bias and hidden cost assumptions.
- Execution costs, slippage, spread, latency and broker/exchange constraints must be explicit where material.
- Research implementation and live implementation require parity evidence when they are different code paths/languages.
- A passing backtest is not permission for real-money deployment.
- Real-money enablement is always a Project Leader gate.
- Never expose credentials or commit secrets.

## Context recovery
Before asking the Leader to repeat old context:
1. read `docs/CURRENT_STATE.md`;
2. read relevant Rules/Decisions/Experiments;
3. inspect recent Git log and diff;
4. inspect tests and code;
5. continue if safely inferable.

## Git safety
Allowed autonomously:
- status/diff/log;
- add/commit;
- pull/rebase when safe and no conflicts with uncommitted work;
- push normal commits;
- create short-lived branch;
- create/update PR when project policy requires.

Leader approval required:
- force push to important branches;
- destructive history rewrite;
- deletion of important remote branches/repositories;
- changing private repository to public.

## Engineering principles
Correctness > speed > elegance.
YAGNI.
Prefer measured evidence over assumed optimization.
Keep business logic testable and separate external I/O when practical.
Use mature libraries when they reduce correctness/maintenance risk.
Do not disable tests or checks merely to make a change pass.
