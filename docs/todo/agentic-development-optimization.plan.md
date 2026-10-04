# Agentic Development Optimization Plan

Assessment: 2026-10-04. Status: **OPEN — proposed optimization work; no implementation authorized by creation of this document**. Owner: Codex for execution; Project Leader for scope, rule and approval boundaries.

## Executive summary

Approximate overall agent readiness: **4.5/10**. The repository has useful foundations: layered Python packages, strategy regression tests, Pandera contracts, context-bound configuration, lazy public imports, recorded-native replay and strict state comparison. Its main constraint is inconsistent instructions, navigation and verification rather than missing tools.

Optimize in this order: accurate source status and recovery; reproducible verification; canonical skills; bounded GitLab tasks; specific architectural boundaries; measured context/performance improvements. Preserve `src/`, pytest, Ruff, mypy, pre-commit and the shared hook submodule. Use GitLab Self-Managed Issues/Boards/MRs/CI/CD for the requested workflow. Do not introduce Docker, Dev Containers, external project-management systems, Sonar, Sentry or unnecessary services.

This plan distinguishes **existing**, **missing**, **recommended** and **optional** capabilities. Estimates and performance targets are provisional until measured. Completion does not establish profitability, native parity or permission for real-money trading.

## Current-state assessment

The original analysis inspected the working tree, status/history/remotes, source/test inventories, packaging, dependencies, CI, hooks, skills, documentation and representative runtime flows. It did not run tests, builds, hooks, benchmarks, terminal sessions or MCP operations, install packages or modify files. This document saves those findings; it is not a fresh runtime audit. Revalidate each finding before implementation because the working tree is changing independently.

| Evidence | Inspected state |
|---|---|
| Python source | 105 `.py` files under `src/` |
| Tests | 20 `test_*.py` modules; 129 textual test definitions before parameter expansion; not a passing/collected count |
| Packages | `application`, `domain`, `infrastructure`, `presentation`, `config`, `helper` |
| Strategy entry point | `application.xauusd_trading_strategy_1_vector.__main__` |
| Public exports | Lazy `VectorizedXauUsdStrategy`, `ZoneCache` |
| Production calculation | Ordered `MarketState`, optional `ExecutionReplay`, retained across manifest partitions |
| Native replay | `recorded_runner.py`, `NativeRecording`, strict checkpoint comparison and MQ5 hash validation |
| Packaging | Hatchling; Python `>=3.12` |
| pytest | `tests/`, `pythonpath=src`, `-q -n auto`; only `unit` registered; no explicit unit/integration markers found in inspected tests |
| Hooks | Mutating Ruff check/format, full pytest, incremental ratchet |
| CI | Manual GitHub Actions workflow using Python 3.11 |
| Git hosting | GitHub origin and GitHub-hosted hook submodule; no GitLab endpoint established |
| GitLab files | No `.gitlab/` templates or `.gitlab-ci.yml` found |
| Recovery documents | `CURRENT_STATE`, `RULES`, `DECISIONS`, `TODO`, `TEST_STATUS`, `EXPERIMENTS`, `FINAL_TEST_REPORT` absent under `docs/` during analysis |
| Documentation | Six files under `docs/` during analysis, including three under `docs/todo/` |
| Skills | 12 `.agents/skills`, 16 `.codex/skills`, further agent copies; `.kilo/skills/` absent |
| MT5 | MQ5, envelope and EX5 present under untracked `mt5/MQL5/Experts/`; previous root-level tracked files marked deleted |
| Search noise | Caches, hook backups/logs, agent dependencies/worktrees and terminal runtime files |
| Links | Simple relative-path scan found 45 missing targets across README/docs/inspected skills; anchors and advanced Markdown were not checked |

Installed agent versions, GitLab configuration, MCP availability, coverage and runtime timings remain unverified. Local Kilo configuration contains literal authentication material; do not copy it into committed examples or diagnostics. No committed-secret leak was established.

Evidence: [root contract](../../AGENTS.md), [packaging/tests](../../pyproject.toml), [hooks](../../.pre-commit-config.yaml), [CI](../../.github/workflows/ci-python.yml), [entry-point tracker](vectorized-entrypoint-flow.md), [parity tracker](MT5-Python.Divergence.md), [strategy README](../../src/application/xauusd_trading_strategy_1_vector/README.md), [datastore README](../../src/infrastructure/datastore_engine/README.md).

Preserve explicit native-proof limits, `.use()` configuration binding, negative schema tests, manifest handling, strict first differences, recording hashes, lazy imports/import-isolation tests, pinned submodule/baselines and human trading approval.

## Scores

Scores measure agent usability and reproducibility, not trading performance or live readiness.

| Area | Score / 10 | Justification |
|---|---:|---|
| Project structure | 6 | Recognizable layers; application/infrastructure coupling and obsolete entry points impede navigation |
| Agent instructions | 4 | Strong ownership/safety contract; absent recovery prerequisites and missing local deltas |
| Skills | 3 | Useful workflows with obsolete paths, conflicting status/names and unwired synchronization |
| Automated verification | 4 | Tests/static checks/ratchet exist; incompatible CI and unclassified tests prevent progressive gates |
| Task structure | 4 | Concrete TODO acceptance work; no consistent metadata or GitLab templates |
| Documentation | 4 | Useful parity/state detail; stale source status, broken links and mixed current/planned content |
| MCP readiness | 4 | Local native endpoints configured; access/provenance/availability unverified |
| Agent commands | 3 | Direct commands exist; no coherent interface or environment preflight |
| Observability / feedback | 6 | Strict comparisons and native diagnostics; artifact errors/provenance need context |
| Git workflow | 6 | Conventional commits, feature branch and rollback contract; binaries/source moves complicate review |
| Context efficiency | 3 | Large/mirrored skills, missing index, legacy/runtime files and broken references |
| Overall agent readiness | 4.5 | Implementation foundations are stronger than coordination and reproducibility |

## Top bottlenecks

P0 = unblock trustworthy execution; P1 = next high-value work; P2 = bounded follow-up; P3 = optional. Severity describes impact; priority describes scheduling. Efforts are estimates.

| ID / severity | Problem and repository evidence | Agent impact | Recommended solution | Effort / priority |
|---|---|---|---|---|
| B1 Critical | Latest inspected project-decisions prohibits market-row Python iteration; `the_strategy.py:process_native_stream` uses `zip`/`enumerate`/`itertuples` and candle-derived lists | Existing code is not a compliant pattern; rushed vectorization can change causal transitions | Record gap; implement separate pandas/NumPy/compiled-kernel task preserving ordering/state and native-proof limits | 3–8+ days; P0 classification, P1 implementation |
| B2 Critical | CI Python 3.11 conflicts with `>=3.12`; Ubuntu install includes MetaTrader5; checkout omits runtime-required submodule initialization | CI is not a reproducible application acceptance gate | Align Python/dependency profiles; initialize pinned submodule; split offline and Windows/native checks | 1–3 days; P0 |
| B3 High | Root/recovery skills require absent control documents; README acknowledges removals | Fresh agents reconstruct authority from conflicting sources | Add compact state index and explicit missing-document handling | 0.5 day; P0 |
| B4 High | pytest skill describes `app/tests`, `pytest.ini`, strict markers and marked fast tests; actual `tests/` is unmarked and hook runs full pytest | Fast selection may be empty or expensive | Classify tests, reject zero selections, align hook tiers | 1–2 days; P0 |
| B5 High | Duplicate `project-decisions`; persistence skill says pending while code/README expose decorator; root hook lacks claimed skill sync | Agents implement conflicting conventions | Consolidate names/authority/references and discovery/sync checks | 1–2 days; P0 |
| B6 High | READMEs/parity tracker point to deleted root MT5 source and missing envelope, present under untracked Experts tree | False blockers and wrong source/binary comparisons | Complete intended relocation separately; distinguish availability/compile/runtime proof | 0.5–1 day; P0 |
| B7 High | Wheel declares absent `src/xauusd`; cTrader CLI imports absent `infrastructure.ctrader_client`; manifests differ | Packaging/public commands misdescribe product | Audit wheel/commands/dependencies; restore supported code or retire obsolete declarations in bounded task | 1–3 days; P1 |
| B8 High | GitLab files absent; remote/contract mention GitHub; TODOs mix completed/planned/blocked work | No uniform executable task/review boundary | GitLab templates, minimal board and issue-to-TODO links with one acceptance owner | 1–2 days plus access; P1 |
| B9 Medium | Benchmark targets legacy private helpers, not active controller; reports fastest repetition | Measures wrong path and understates variance | Deterministic active benchmark, correctness check, median and warm/cold timing | 1–2 days; P1 |
| B10 Medium | Broad searches enter caches/backups; tracked `src/output.txt`; ~32 KB decision skill, ~43 KB journal guide, ~249 KB glossary CSV | High startup/search/context cost | Scoped navigation/exclusions, small skills with references, on-demand evidence | 0.5–2 days; P1 |

Low-priority opportunities: generated API docs, broader coverage, additional local instruction files and OpenTelemetry. None precedes the high-priority fixes.

## Detailed findings by priority

### Project structure

**Existing:** six useful Python layers. **Missing:** a map linking functionality, public interfaces, callers and tests. **Recommended:** retain the layout; avoid wholesale migration to `src/xauusd/` or renaming the strategy package without demonstrated benefit.

| Functionality | Implementation | Relevant tests |
|---|---|---|
| Acquisition/orchestration | Strategy `__main__.py`, `runner.py`, `infrastructure/mt5/` | `test_vectorized_validation`, `test_mt5_input_validation` |
| Ordered transitions | `market.py`, `the_strategy.py` | `test_robust_mt5_parity`, `test_vectorized_pipeline` |
| Execution/risk | `replay.py`, `domain/replay.py`, `domain/robust.py` | `test_vectorized_execution`, `test_robust_mt5_parity` |
| Recorded callbacks | `native_replay.py`, `recorded_runner.py`, native/recording contracts | `test_recorded_native_replay` |
| Zones | `zone_loader.py`, `zone_cache.py`, `domain/xau_usd/zone.py` | `test_mt5_zone_loader`, `test_vectorized_cache` |
| Artifacts/contracts | Strategy `domain/schema.py`, `infrastructure/result_processing/` | `test_result_manifest`, `test_datetime_schemas` |
| Optional reports | `backtest.py`, `reporting.py`, presentation reports | `test_backtest_signals`, `test_backtest_import_isolation`, `test_on_tick_vectorbt` |
| Datastore | `infrastructure/datastore_engine/` | Coverage/ownership map needs completion |

Label legacy vector helpers as compatibility surfaces. Extract callable result-processing functions from `__main__.py` to a named module with temporary compatibility imports. Clarify strategy-owned versus shared schema ownership. Application imports result-processing infrastructure, which imports application schemas: this is bidirectional package coupling, not proof of a runtime circular import. Build an AST/caller inventory before moving contracts. `replay.py` was 827 lines; split only a cohesive protected responsibility, not by line count.

### AGENTS.md and Skills

**Existing:** clear ownership, batching and approval boundaries. **Missing:** executable recovery and consistent local invariants. **Recommended:** retain safety requirements, correct paths, explicitly handle absent authority documents, use unique canonical skills and separate analysis-only from implementation workflows.

### Automated verification

**Existing:** pytest, Ruff, mypy, pre-commit, ratchet. **Missing:** reliable tiers, environment profiles, installed-wheel smoke and structured evidence. **Recommended:** implement the hierarchy below; measure timing before enforcing budgets. Coverage was not configured in inspected root files; begin with critical transitions/contracts rather than an arbitrary whole-repo percentage.

### Task / issue structure

**Existing:** concrete parity IDs and acceptance requirements. **Missing:** GitLab templates, uniform READY/BLOCKED metadata and exact verification commands. **Recommended:** use existing GitLab Self-Managed ecosystem. Server-side issue conventions were inaccessible and are not assessed as nonexistent.

### Documentation

**Existing:** detailed parity/state/journal guidance. **Missing:** accurate source links and current/planned/evidence separation. **Recommended:** correct incorrectly rooted `../../../src/...` journal links; keep detailed reference on demand, with a compact operational entry path.

### MCP services

**Existing:** ignored local Kilo MetaEditor/terminal endpoint configuration. **Missing:** verified health, permission boundaries and portable setup. **Recommended:** minimum external capability; sanitized examples; do not publish literal local credentials.

### Agent commands

**Existing:** module entry points, direct checks, recorded replay and benchmark. **Missing:** command contract/preflight and read-only versus mutating classification. **Recommended:** one standard-library command wrapper.

### Observability / feedback

**Existing:** initialization diagnostics, MT5 error codes, checkpoint differences, source hashes and DataFrame dumps. **Missing:** complete provenance and contextual artifact failures. CLI accepts `.csv` but `save_results_to_file` always writes Parquet. Recorded runner can succeed without `--expected`; `compared=false` must never count as proven parity.

### Git conventions

**Existing:** conventional commits, feature branch, pinned dependency and safety policy. **Missing:** source-move/binary/evidence/submodule review conventions. **Recommended:** focused reversible batches and explicit artifact ownership.

### Context optimization

**Existing:** instructions favor scoped searches and compact evidence. **Missing:** reliable index/discovery. **Recommended:** remove ambiguity before bulk; do not replace repository navigation with a semantic service.

## Recommended target architecture

`[new]` means proposed, not implemented. Retain current package boundaries and create directories only when populated.

```text
AGENTS.md
README.md
CHATGPT_WORK.md
pyproject.toml
.pre-commit-config.yaml
.gitlab-ci.yml                         [new]
.gitlab/                               [new]
  issue_templates/Agent_Task.md
  merge_request_templates/Verified_Change.md
.agents/skills/                        canonical shared workflows
  context-recovery/
  project-decisions/
  verification/
  strategy-parity/
  dataframe-contracts/
  performance-review/
  task-handoff/
docs/
  CURRENT_STATE.md                     [new]
  architecture.md                      [new]
  development.md                       [new]
  State-Variables.Glossary.md
  State-Variables.Glossary.csv
  MT5-Journal-Python-Comparison.md
  todo/
    agentic-development-optimization.plan.md
    MT5-Python.Divergence.md
    vectorized-entrypoint-flow.md
    ...
src/
  AGENTS.md                           [new]
  application/xauusd_trading_strategy_1_vector/
    AGENTS.md                         [new]
    README.md
    ...
  domain/
  infrastructure/
    datastore_engine/README.md
    result_processing/pipeline.py     [new extraction]
    mt5/
  presentation/
  config/
  helper/
tests/
  AGENTS.md                           [new]
  conftest.py
  vectorized_fixtures.py
  vectors/
  test_*.py
scripts/
  dev.py                              [new]
  benchmark_tick_stages.py
  backup/
config/
  README.md
  mt5/
mt5/
  AGENTS.md                           [new]
  README.md
  MQL5/
    Experts/                          intended source location to verify
    Files/ranges.csv                  input provenance policy required
br_pre_commit/                        retained pinned submodule
.br-pre-commit/ratchet/                retained reviewed baselines
archive_not_used_trash/                frozen reference
```

Do not create a top-level `skills/` tree or empty test categories. Classify tests before optionally moving them into `unit/`, `integration/`, `native/`. Do not promote current code or historical research into confirmed `RULES.md`; importing confirmed external rules is a separate authority task.

Navigation: task → current state → applicable instructions → responsibility map → affected contracts/code → mapped tests → command/evidence.

## AGENTS.md strategy

| Location | Responsibility |
|---|---|
| Root | Authority, ownership, approvals, recovery, commands and Git boundaries |
| `src/` | Dependency direction, config, typing, persistence and operation priority |
| Strategy package | Causal windows, state lifetime, stream isolation, callbacks and assumptions |
| `tests/` | Markers, deterministic fixtures, offline boundaries and selection |
| `mt5/` | Build/source identity, account requirements, compile/tester evidence and execution gates |

Local files contain deltas, not repeated root text. Aim for roughly 100 root lines without removing authority/safety requirements. Add datastore-local instructions only if README/skill cannot express its distinct rules concisely.

Nested discovery depends on launch directory/harness; root instructions must explicitly require applicable local files before editing. Codex documents root-to-working-directory discovery: [official guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

- [ ] Replace nonexistent mandatory recovery paths with the actual authority map.
- [ ] Keep persistence bounded by assigned objective and distinguish read-only tasks.
- [ ] Separate model preferences from repository correctness policy.
- [ ] Preserve pandas-first/NumPy-second/compiled fallback requirements; classify existing Python row iteration as debt, not an exception.
- [ ] Replace unconditional archive searches with task-relevant historical lookup.
- [ ] Replace blanket log-before-every-raise with boundary-owned diagnostics/exception chaining, avoiding duplicate logs and sensitive dumps.

Instruction precedence and trading-rule interpretations require Leader review.

## Skills strategy

Propose `.agents/skills/` as canonical. Current official documentation supports it for both tools; verify installed-version discovery before retiring mirrors: [Codex](https://learn.chatgpt.com/docs/build-skills), [Kilo](https://kilo.ai/docs/customize/skills).

- [ ] Inventory names/descriptions/references/conflicting copies.
- [ ] Assign unique names; merge useful active content and put long material in `references/`.
- [ ] Verify discovery in installed Codex/Kilo.
- [ ] Retain generated adapters only where needed; change shared sync through a reviewed submodule task.
- [ ] Add read-only consistency validation. Existing sync can create/stage mirrors and propagate deletions; do not run it blindly.

| Skill / purpose | Trigger / required context | Workflow | Verification | Expected output |
|---|---|---|---|---|
| `context-recovery` / executable state | New session; state, status, relevant TODO | Recover → inspect diff/submodule → bounded next task | Existing paths and matching evidence | Task/evidence/blocker summary |
| `verification` / correct gate | Implementation handoff; commands/changed paths | Preflight → focused → broader → summary | Nonempty selection, exits, environment/fingerprint | Verification record |
| `strategy-parity` / native comparison | State/risk/callback changes; schemas/recording/source | Invariant → regression → ordered comparison → native proof | First difference, consumed operations, IDs/order/hashes | Reproducer and explicit parity status |
| `dataframe-contracts` / schema preservation | Frame/schema/persistence edits; producer/consumer chain | Trace → preserve index/dtypes → rejection cases → round trip | Invalid/empty/nullable data and timestamp precision | Contract diff and tests |
| `performance-review` / measured compliant optimization | Hot path; active benchmark/current behavior | Measure → pandas/NumPy → compiled recurrence only if needed | Equivalence, no interpreted row fallback, timing/memory | Before/after report and limits |
| `task-handoff` / executable issue | Research/issue handoff; confirmed scope/rules | Bound goal → files → acceptance → commands → dependencies | No unresolved authority or unusable commands | READY or explicit BLOCKED task |

Refresh existing workflows rather than add overlapping skills. Keep Git/docs skills task-triggered; remove irrelevant ML/forecasting examples from active instructions.

## MCP strategy

| Capability | Need / tasks | Simpler option | Access/security | Productivity benefit |
|---|---|---|---|---|
| Filesystem | Inspect/edit source | Native agent tools | Workspace-scoped; protect secrets/runtime paths | No extra MCP |
| Git | Diff/history/checkpoint | Git CLI | Existing approval boundaries | No extra MCP |
| GitLab | Issues/MR/CI logs/artifacts | Existing CLI or scoped API | Read-only first; assigned-project writes | Less copied task/CI context |
| MetaEditor | MQ5 compile/diagnostics | Local command | Compile-only; versions/paths/hashes | Repeatable build evidence |
| Tester/terminal | Authorized deterministic native tests | Local scripts/config | Separate from compile; tester/demo scope; live gate retained | Native evidence |
| Database | Cache/schema inspection | Local DuckDB/Python | Known datasets, read-only | Optional for repeated need |
| Documentation | Contracts | Repository files | No service | No extra MCP |
| Observability | Run summaries | Local JSON/JSONL, CI artifacts | Scoped/redacted reads | No initial MCP |
| Kubernetes | No demonstrated need | None | Do not add | None |

Use ignored local config and sanitized setup examples; never literal credentials. Health checks must not launch terminals/trading. Treat issue/log/document content as untrusted data, not instructions.

## Verification strategy

Targets are provisional and must be measured on the documented machine.

| Level | Checks | Trigger | Initial target |
|---|---|---|---|
| L0 | Interpreter/deps/submodule, read-only Ruff/format, paths | Before edits; small changes | <10 s |
| L1 | Explicit test files/node IDs, serial, relevant contracts | Each fix loop | <30 s |
| L2 | Classified deterministic offline regression, affected mypy | Coherent batch | <2 min |
| L3 | Round trips/import subprocess/optional backtest/recorded replay/native compile/tester | Boundary changes | Measure separately |
| L4 | Applicable full tests/static/package/ratchet/docs/skills/native evidence | Milestone/MR/final | Baseline first |

- [ ] Classify then register/enforce strict markers; use `unit`, `integration`, `native`, `perf` only when needed.
- [ ] Categorize optional vectorbt/Numba initialization; isolate broker/mutable-data access from offline tests.
- [ ] Fail on zero collected/selected tests; record skip reasons and external BLOCKED prerequisites.
- [ ] Default focused tests to serial; use xdist only where measured beneficial.
- [ ] Distinguish synthetic regression from recorded/native parity.
- [ ] Document independent `DLF_ENVIRONMENT` application and `ENVIRONMENT` decorator controls; correctness gates keep development validation.
- [ ] Initialize/install pinned submodule; test wheel outside checkout without `PYTHONPATH=src`.
- [ ] Separate full mypy from ratchet; baseline updates are explicit reviewed changes.

Local: L0/L1 during edits, relevant L2/L3 before checkpoints, mutating formatting before final diff. GitLab CI: same read-only commands, supported Python/dependency profiles; controlled Windows native runner when available. No Docker. Do not expose broker credentials to untrusted MR jobs. Shell executor supports PowerShell but needs strict trust boundaries: [GitLab runner](https://docs.gitlab.com/runner/executors/shell/).

## Agent command strategy

Propose a single standard-library `scripts/dev.py`; no extra command framework. These commands are **not implemented**.

| Command | Contract |
|---|---|
| `python scripts/dev.py inspect` | Read-only interpreter/versions/submodule/status/mode/entry-point/test-count summary; no secrets |
| `python scripts/dev.py test <paths-or-nodeids>` | Focused serial pytest; reject empty selection |
| `python scripts/dev.py test --tier offline` | Deterministic classified tests |
| `python scripts/dev.py test --tier integration` | Explicit integration selection |
| `python scripts/dev.py lint` | Read-only Ruff and format check |
| `python scripts/dev.py format <paths>` | Explicit mutating fixes/formatting |
| `python scripts/dev.py typecheck [paths]` | Existing mypy, consistent scope/config |
| `python scripts/dev.py check --tier <level>` | Compose gates, preserve nonzero exits |
| `python scripts/dev.py benchmark` | Active-path timing plus correctness |
| `python scripts/dev.py build` | Wheel build/installed smoke |

Current focused syntax after environment validation:

```powershell
python -m pytest -o addopts= tests/test_recorded_native_replay.py
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m mypy src scripts tests
```

Existing native replay requires actual input files and writes output; it was not run in the analysis:

```powershell
python -m application.xauusd_trading_strategy_1_vector.recorded_runner recording.json --reference mt5/MQL5/Experts/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5 --expected native-checkpoints.jsonl --output python-checkpoints.jsonl
```

Document staged hook scope: `pre-commit run` does not prove all unstaged edits were checked; `--all-files` is broader and can mutate. Preflight derives repository roots rather than requiring developer-specific paths; commands do not install packages or access network implicitly.

## Documentation strategy

| Document | Responsibility |
|---|---|
| Root README | Purpose, modes, prerequisites, commands/navigation |
| `CURRENT_STATE.md` | Active paths, dirty-state caveat, READY tasks, blockers and latest evidence |
| `architecture.md` | Responsibilities/dependency direction/interfaces/state/artifact contracts |
| `development.md` | Environment profiles, commands, tiers/platform prerequisites |
| Strategy README | Active/compatibility surfaces, `.use()`, inputs/outputs/assumptions |
| Datastore README | Actual persistence mechanism/migration boundary |
| Parity tracker | Remaining executable gaps and proof |
| Journal guide | Quick reproduction plus on-demand detailed reference |
| Glossary | State ownership/source references, not mandatory startup reading |

- [ ] Repair links and envelope status without asserting compile/parity proof.
- [ ] Reconcile CSV export behavior and unsupported debug option through bounded tasks.
- [ ] Correct obsolete skill paths/scripts/infrastructure references.
- [ ] Keep glossary detail out of architecture summaries.
- [ ] Store full evidence as structured artifacts with compact current-state summary.
- [ ] Add path/anchor checker returning file/line/target; exclude generated mirrors appropriately.

## Git strategy

- [ ] One branch per issue/coherent batch; related implementation/tests/docs together.
- [ ] Separate mechanical MT5 relocation from behavior changes and shared-submodule implementation from parent pointer update.
- [ ] Include submodule identity/evidence in reviews; preserve fixture bytes/hashes.
- [ ] Define EX5 artifact policy before untracking; prefer reproducible GitLab artifacts where practical.
- [ ] Review tracked `src/output.txt` and skill-bundled workflow examples; `.github/git-commit/workflows/` is not active root CI.
- [ ] Conventional behavior-oriented commits; avoid whole-tree formatting or unrelated cleanup.
- [ ] Normal reversible history; no automatic remote cleanup or origin rewrite.

Start GitLab adoption with templates/CI. Remote mapping/access is a separate explicit step; no endpoint is established in this checkout. MR body: goal, scope, commands/environment/source/results/skips/artifacts, risk/native limits, rollback and issue link.

## Context optimization strategy

Startup reads assigned task, root instructions, current state, applicable local instructions, one skill and affected contracts/code/tests/diff. Read archives/glossaries/full logs/history only for an unresolved requirement.

```powershell
rg --files src tests docs scripts config
rg -n "ResultFilesManifest" src tests
rg -n "process_native_stream|MarketState" src/application tests
```

- [ ] Exclude caches/logs/backups/local dependencies/worktrees/terminal runtime from ordinary navigation, not from required task scope.
- [ ] Keep deliberate access to `br_pre_commit/src` for hook/decorator work.
- [ ] Turn large decision skill into small index/references; remove repeated names/discovery metadata.
- [ ] Put quick workflow atop journal guide; search glossary variables rather than load CSV.
- [ ] Emit compact failures and retain full artifacts with source/config/input identities for responsible evidence reuse.
- [ ] Use existing IDE navigation/mypy first; add AST import checks only for concrete dependency/cycle/API needs.

No vector database, repository chatbot or persistent semantic service without a measured unresolved navigation problem.

## Agent workflow

1. Receive bounded task with acceptance/verification.
2. Inspect branch/status/submodule/local changes.
3. Read current state and applicable instructions/skill.
4. Resolve authority contradictions; locate code/contracts/callers/tests.
5. Preflight environment and available verification.
6. Implement smallest coherent task-completing change.
7. Run focused tests/static checks; diagnose first failure with compact state/input evidence.
8. Fix and repeat affected checks; run required broader tiers.
9. Update docs/evidence; review diff/secrets/artifacts/submodule.
10. Run final applicable gate after last edit; checkpoint and prepare authorized MR.
11. Continue safe related work only while the assigned objective remains unfinished.

Analysis-only tasks stop at the requested analysis output. Saving this TODO authorizes documentation creation, not execution of the roadmap.

| Concern | Codex/Kilo shared target |
|---|---|
| Instructions | Root contract plus explicitly read local deltas |
| Skills | Unique canonical workflows and installed-version discovery check |
| Terminal/tests | Same preflight, commands, tiers and nonempty selections |
| Git | Same scoped checkpoint/MR contract |
| MCP | Same capability boundaries; ignored per-agent config |
| Context | Same state/responsibility maps |
| Acceptance | Same evidence/skips/native-proof requirements |

Kilo documents AGENTS.md as primary instructions; avoid independent custom-prompt rulesets: [official guidance](https://kilo.ai/docs/customize/custom-instructions).

## Phased implementation roadmap

Efforts assume valid Python access. GitLab/native tasks have external prerequisites. Coordinate market-row work with the existing [vectorization plan](vectorized-operation-improment.plan.md); do not create a parallel implementation.

### Phase 0 — Quick wins

Each item is individually under one day; the whole phase can take longer.

| Change | Reason | Files | Approach | Benefit | Effort | Dependencies | Priority |
|---|---|---|---|---|---|---|---|
| Source status/links | False blocker | READMEs/parity/journal | Verify intended paths; separate source/build/runtime | Accurate recovery | 2–4 h | Relocation intent | P0 |
| Current-state index | Missing recovery | State/root instructions | Active source/work/evidence/blockers | <5 min startup | 2–4 h | Diff review | P0 |
| Workflow claims | Contradictory skills | pytest/pre-commit/persistence skills | Align current paths/status/unwired features | Correct commands/design | 4–6 h | Skill ownership | P0 |
| Entry-point classification | Missing cTrader implementation | README/packaging task | Active/unsupported inventory and restore/retire criteria | Fewer dead ends | 2–3 h | Removal scope | P1 |
| Navigation | Generated search noise | Development/search config | Include roots/exclusions | Less context | 1–2 h | None | P1 |
| Validation controls | Separate environment flags | Development/benchmark docs | Explain both flags | No silent bypass | 1–2 h | Decorator source | P0 |

### Phase 1 — Agent foundation

| Change | Reason | Files | Approach | Benefit | Effort | Dependencies | Priority |
|---|---|---|---|---|---|---|---|
| Hierarchical instructions | Implicit local invariants | Root/src/strategy/tests/MT5 instructions | Root plus deltas | Fewer mistakes | 1 d | Authority map | P1 |
| Canonical skills | Conflicting discovery/mirrors | Skills/adapters/submodule sync | Merge, discover, read-only verify | Multi-agent consistency | 1–2 d | Installed agents | P0 |
| Command interface | Inconsistent preflight/checks | `scripts/dev.py`, docs | Standard-library wrapper | Predictable loops | 1–2 d | Valid environment | P1 |
| Test/hook tiers | Full suite called fast | Tests/pyproject/hooks | Classify/nonempty/timing | Faster meaningful checks | 1–2 d | Commands | P0 |
| Dependencies/package | Manifest/API drift | pyproject/requirements | Core/dev/native/report profiles, wheel smoke | Reproducible setup | 1–3 d | API decision | P0 |
| GitLab foundation | Requested workflow absent | Templates/CI | Shared-command offline/native jobs | Reviewable acceptance | 1–2 d | Endpoint/runner | P1 |

### Phase 2 — Repository architecture

| Change | Reason | Files | Approach | Benefit | Effort | Dependencies | Priority |
|---|---|---|---|---|---|---|---|
| Responsibility map | Unclear change locations | Architecture/component docs | Interfaces/state/tests/dependencies | Fast navigation | 1 d | Inventory | P1 |
| Market-row compliance | Current policy gap | Strategy/replay/tests | Characterize; pandas/NumPy; compiled recurrence if required | Compliance/throughput | 3–8+ d | Regressions/active benchmark/vectorization plan | P1 |
| Result boundary | Package coupling | Result pipeline/schema/callers | AST audit; named module; move only shared contracts | Lower coupling | 2–4 d | Contract/import tests | P2 |
| Test helpers | Test-to-test imports | Fixtures/tests | Existing shared fixture module | Stable selection | 0.5–1 d | Classification | P2 |
| Cohesive module extraction | Large replay context | Replay/related modules | Protected responsibility slices | Smaller reviews | 2–4 d per justified slice | Coverage/callers | P2 |

### Phase 3 — Agent workflows

| Change | Reason | Files | Approach | Benefit | Effort | Dependencies | Priority |
|---|---|---|---|---|---|---|---|
| READY tasks | Bounded autonomous inputs | Templates/TODO links | One owner for criteria/commands/dependencies | Fewer clarifications | 0.5–1 d | GitLab | P1 |
| Structured evidence | Unreliable reuse | Commands/CI/state | Hashes/counts/skips/artifacts | Fast status/debugging | 1–2 d | Tiers | P1 |
| Native parity workflow | Source tests insufficient | Skill/replay/build tooling | Build/input hashes, ordered recording, comparison | Defensible proof | 2–5 d plus recordings | MT5 | P1 |
| Contextual failures | Missing artifact state | Manifest/validation/replay | Stream/day/category/event/invariant, redact | Root-cause speed | 1–2 d | Diagnostics contract | P2 |
| Scoped external access | Native/GitLab evidence transfer | MCP examples/docs | GitLab reads, compile-only, separate tester | Less manual transfer | 1–2 d | Access/security | P2 |

### Phase 4 — Advanced optimization

| Change | Reason | Files | Approach | Benefit | Effort | Dependencies | Priority |
|---|---|---|---|---|---|---|---|
| Active benchmark | Legacy measurements | Script/perf fixtures | Equivalence, warm/cold, median/memory | Trustworthy optimization | 1–2 d | Deterministic active fixtures | P1 |
| Context measurements | Quantify gains | Trial summaries | Same tasks before/after; reads/tokens/time | Proven efficiency | 0.5–1 d | Navigation | P2 |
| AST boundaries | Prevent coupling regressions | Small script/test | Agreed narrow rules, explicit baseline | Architecture reliability | 1–2 d | Dependency map | P2 |
| Targeted coverage | Protect critical transitions | Tests/CI | Risk/protection/replay/contracts first | Safer edits | 1–2 d | Stable tiers | P2 |
| OpenTelemetry | Only unresolved multi-stage latency | Runtime boundaries | Coarse spans after local timing insufficient | Cross-stage diagnosis | 2–4 d | Measured need | P3 optional |

## Prioritized action list

Every item starts OPEN. When completed, mark its checkbox and add compact implementation/evidence status; do not accumulate historical changelogs.

### Critical

- [ ] **A01:** Record accurate source availability and instruction-compliance gaps; acceptance: current paths and prohibited processing are explicit, with no false native-proof claim.
- [ ] **A02:** Reproducible CI environment; acceptance: supported interpreter/dependencies/submodule and executable offline/native job boundaries.
- [ ] **A03:** Separate evidence classes; acceptance: offline regression, recorded comparison, compile and runtime parity cannot be confused by automation.

### High

- [ ] **A04:** Recovery index/authoritative links; acceptance: fresh session identifies source/task/checks within five minutes and links resolve.
- [ ] **A05:** Canonical skills/status/discovery; acceptance: unique names and consistent installed Codex/Kilo guidance.
- [ ] **A06:** Deterministic test tiers; acceptance: nonempty selections, meaningful offline isolation and aligned fast hook.
- [ ] **A07:** Dependencies/wheel/commands; acceptance: clean installed package and all advertised supported entry points import outside checkout.
- [ ] **A08:** Minimal command interface; acceptance: documented read-only/mutating contracts and preserved failures.
- [ ] **A09:** GitLab templates/CI; acceptance: independently executable issues and shared-command MR evidence.
- [ ] **A10:** Active benchmark; acceptance: measures controller path with correctness, median, warm/cold and memory evidence.

### Medium

- [ ] **A11:** Local instructions/responsibility map; acceptance: code/callers/contracts/tests discoverable without broad rereads.
- [ ] **A12:** Compliant market-row implementation; acceptance: no interpreted row fallback, causal/order/state equivalence and explicit native limits.
- [ ] **A13:** Artifact errors/evidence; acceptance: failing stage identifies stream/day/category/invariant and reproducible state without secrets.
- [ ] **A14:** Result ownership/shared helpers; acceptance: documented dependencies and stable selective test imports.
- [ ] **A15:** Context/search cleanup; acceptance: relevant scoped searches omit generated noise and long references remain accessible on demand.

### Low / optional

- [ ] **A16:** AST checks/targeted coverage only for agreed gaps; acceptance: protects critical boundaries without redundant infrastructure.
- [ ] **A17:** GitLab MCP only if CLI/API proves cumbersome; acceptance: project-scoped access and measurable transfer savings.
- [ ] **A18:** OpenTelemetry only for demonstrated diagnostic gaps; acceptance: coarse useful spans without per-tick overhead or sensitive state.

GitLab task template: Goal; Context/current behavior/authority; Scope; Constraints; Relevant implementation/callers/contracts/tests; Expected behavior; Acceptance including negative cases; exact Verification/prerequisites/artifacts; Dependencies; Out of scope. Use `READY`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE` with P0–P3 labels. READY requires clear authority, scope, acceptance and executable commands. Split offline work from externally blocked native evidence; link TODOs without duplicated acceptance ownership. [GitLab description templates](https://docs.gitlab.com/user/project/description_templates/)

## Success criteria

Baseline first; measure comparable tasks and the documented machine.

| Outcome | Acceptance |
|---|---|
| Recovery | Both agents identify entry point/authority/next task/check within 5 min |
| Navigation | Implementation/callers/contracts/tests for three representative changes within 2 min each |
| Instructions | No conflicting active names or obsolete layouts |
| Documentation | Zero broken local links in authoritative docs/canonical skills |
| Test selection | Advertised tiers select tests; zero selection fails |
| Focused loop | Representative L1 under 30 s |
| Offline suite | L2 under 2 min, subject to measured baseline |
| Packaging | Wheel imports outside checkout without source-path assistance |
| CI | Same Python/dependencies/commands/submodule identity locally and GitLab |
| Native proof | Source/include/input/build identity recorded; replay without comparison never establishes parity |
| Context | At least 30% fewer startup reads/tokens across comparable tasks |
| Debugging | Boundary/invariant/expected/actual/reproducer available for representative failures |
| Review | Issue/MR/diff explain behavior/tests/limits/rollback |
| Security | No literal credentials in committed examples/diagnostics/evidence |
| Tool restraint | Added capability fixes measured gap; optional tools remain absent otherwise |

Completion means fresh agents recover the project, execute bounded work, verify changes and prepare reviewable checkpoints without reconstructing chats or following contradictory guidance. It does not authorize live trading.
