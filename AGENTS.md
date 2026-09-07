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
- batched local Git checkpoints;
- optional GitHub synchronization at explicit recovery/release boundaries;
- CI fixes.

## Default Codex execution loop
1. Read current state and relevant rules.
2. Inspect Git status and actual code before changing anything.
3. Recover or update executable TODOs.
4. Choose safe reversible technical defaults without asking the Leader.
5. Implement the largest safe coherent batch that can be verified without crossing a Leader approval boundary; complete several adjacent TODO outcomes when they naturally belong together.
6. Add/update tests.
7. Run targeted checks during the batch; reserve the full quality gate for a major milestone, final MVP candidate or safety-critical change.
8. Update project documentation to match reality.
9. Create one coherent verified local Git checkpoint for a major batch or final MVP candidate; do not commit each micro-slice.
10. Defer GitHub push, PR and remote CI during rapid MVP execution unless the Leader explicitly requests them or a remote backup is materially needed.
11. Treat reports, commits and pushes as checkpoints, not stopping points. Select the next safe `READY` outcome and continue.
12. Report only outcome, evidence, material risk, and genuine Leader decision.

## Persistence and batching
- A delegated project objective remains active until it is achieved, explicitly cancelled/replaced by the Project Leader, or genuinely blocked by an approval boundary, missing authority or external condition.
- Do not stop merely because one module, test slice, commit, push or milestone completed.
- After every verified checkpoint, immediately continue with the next related executable TODO while safe work remains.
- Prefer end-to-end batches that include implementation, tests, integration and documentation over isolated micro-slices. Git/GitHub activity must not interrupt a runnable batch.
- A status request or question from the Project Leader is not a cancellation. Answer it concisely, then resume the active objective unless the latest instruction replaces it.
- Intermediate updates are informational. Never require the Project Leader to reply with “continue” for routine execution.
- If one path is externally blocked, continue other safe in-scope work that reduces the remaining objective. Stop only when no meaningful safe progress remains.
- Persistence does not expand scope, bypass confirmed Rules, weaken tests, authorize live trading, or remove any approval requirement below.

## Context and token efficiency
- Start recovery from `docs/CURRENT_STATE.md`, open TODO items, and the latest local diff; do not reread the full repository when those sources are sufficient.
- Search narrowly and read only relevant ranges. Never dump complete large logs, datasets, generated files, Handoffs, or long documents into model context unless the unresolved issue requires them.
- Parse verbose tool/MT5 output locally and return compact counters, failures, hashes, and selected evidence lines.
- Reuse persisted test evidence. A status or reporting request must not rerun MT5 or an unchanged expensive gate when `docs/FINAL_TEST_REPORT.md` and its structured evidence answer it.
- Keep commentary and final responses concise unless the Leader requests detail. Do not repeat instructions or project history already stored in the repository.
- Use `GPT-5.6 Terra` with medium reasoning as the routine project default when selectable; use Luna/low for mechanical inspection and Sol/medium only for materially difficult debugging or final audit. Do not use high/xhigh routinely.

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

### Rapid MVP mode
- Keep local Git for rollback and provenance; do not remove repository history or `origin`.
- Inspect status/diff when needed, but batch commits at major verified boundaries.
- Do not push, open PRs, or run remote CI routinely. Use one final push only when explicitly requested or when a remote recovery checkpoint is materially justified.
- This optimization never waives strategy, risk, execution, compile, or final acceptance tests.

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
