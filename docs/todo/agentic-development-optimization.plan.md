# Agentic Development Optimization Plan

Assessment: 2026-10-04. Status: **ACTIVE — Phases 0 and 1 implemented 2026-10-04; Phases 2-4 remain, see the action list for per-item status.** Owner: Codex for execution; Project Leader for scope, rule and approval boundaries.

Implementation record: [docs/CURRENT_STATE.md](../CURRENT_STATE.md) holds the verified baseline and the READY list; [docs/development.md](../development.md) holds commands, tiers and measured timings; [docs/architecture.md](../architecture.md) holds the responsibility map. Verification entry point is `python scripts/dev.py`.

## What the 2026-10-04 implementation changed

- **cTrader retired** (Project Leader decision): `src/presentation/ctrader/`, the `ctrader-cli` script and the `ctrader-open-api`/`twisted`/`requests`/`service_identity` dependencies are gone. `requirements.txt` and `requirements-dev.txt` were deleted so `pyproject.toml` is the only manifest.
- **Packaging fixed**: the wheel declared an absent `src/xauusd`, so it could not build. `dev.py build --smoke` now builds and imports all six top-level packages outside the checkout.
- **`scripts/dev.py`**: one read-only/mutating-separated command interface. Bare `ruff`/`mypy`/`pytest`/`xenon` are absent from `PATH` here, which is why the ratchet hook fails; the wrapper always uses `python -m`.
- **Test tiers**: `tests/conftest.py TIER_BY_MODULE` is the classification authority and fails collection for an unclassified module. 178 unit / 17 integration / 50 parity; `native` and `perf` are empty by design and exit 3 rather than passing.
- **CI**: Python 3.12 (was 3.11), submodule initialized, no MetaTrader5 on Linux, and GitHub Actions plus `.gitlab-ci.yml` run the same `dev.py` commands.
- **Recovery**: `docs/CURRENT_STATE.md`, `docs/architecture.md`, `docs/development.md`, and local `AGENTS.md` deltas for `src/`, the strategy package, `tests/` and `mt5/`.
- **Skills**: `.agents/skills` is canonical (17 skills); the shared set in `.codex/skills` is 10 skills mirrored across five agents. The duplicate `project-decisions` is resolved, the 32 KB skill is split into an index plus `references/`, and `dev.py docs --skills` validates name uniqueness and byte-identical mirrors read-only.
- **Links**: 25 broken local links fixed; `dev.py docs` reports zero.
- **Measured, not assumed**: L1 node id 3 s, L1 module 42 s, L2 offline 52 s parallel / 135 s serial. The plan's provisional 30 s L1 target is met per node id but missed per module, because `@pandera_validate` dominates.

Full mypy remains 209 pre-existing errors in 76 files. It is not a gate; the ratchet is. Clearing it is an explicit reviewed decision.

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
| B7 High | Wheel declared absent `src/xauusd`, so the wheel could not build; the `ctrader-cli` script imported absent `infrastructure.ctrader_client`; manifests disagreed with the installed environment | Packaging/public commands misdescribe product | Audit wheel/commands/dependencies; restore supported code or retire obsolete declarations in bounded task | 1–3 days; P1 |
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

- [x] Replace nonexistent mandatory recovery paths with the actual authority map. Done: `context-recovery` and `docs/CURRENT_STATE.md` name the real authority order and list the control documents that do not exist.
- [x] Keep persistence bounded by assigned objective and distinguish read-only tasks. Done: `autonomous-execution` and the read-only/mutating table in `docs/development.md`.
- [x] Separate model preferences from repository correctness policy. Done: measured timings are labelled provisional baselines, and the vectorization rule is stated as repository policy rather than preference.
- [x] Preserve pandas-first/NumPy-second/compiled fallback requirements; classify existing Python row iteration as debt, not an exception. Done: decision skill plus `src/AGENTS.md` and the strategy `AGENTS.md` name `process_native_stream` as debt.
- [x] Replace unconditional archive searches with task-relevant historical lookup. Done: `context-recovery` scopes searches to `src tests docs scripts config` and forbids archive search unless the task requires it.
- [x] Replace blanket log-before-every-raise with boundary-owned diagnostics/exception chaining, avoiding duplicate logs and sensitive dumps. Done: stated in the decision reference and the `dataframe-contracts` skill; no blanket-log audit was performed across `src/`, so existing violations may remain.

Instruction precedence and trading-rule interpretations require Leader review.

## Skills strategy

Propose `.agents/skills/` as canonical. Current official documentation supports it for both tools; verify installed-version discovery before retiring mirrors: [Codex](https://learn.chatgpt.com/docs/build-skills), [Kilo](https://kilo.ai/docs/customize/skills).

- [x] Inventory names/descriptions/references/conflicting copies. Done: 12 canonical + 16 shared before, one duplicate name (`project-decisions`) and five skills foreign to this repository (`duckdb-cache-persistence`, `markdown-formatting`, `optimization-review`, `sqlalchemy-duckdb-orm`, `use-aget-skills`).
- [x] Assign unique names; merge useful active content and put long material in `references/`. Done: the 32 KB `project-decisions` is now a 2 KB index plus `references/vectorized-pandas-numpy.md` and `references/data-and-path-conventions.md`.
- [ ] Verify discovery in installed Codex/Kilo. **OPEN** — the installed agent binaries were not re-run to confirm they load `.agents/skills`; only on-disk consistency is validated.
- [ ] Retain generated adapters only where needed; change shared sync through a reviewed submodule task. **OPEN** — the sync hook is still not wired into `.pre-commit-config.yaml`, and mirror maintenance is currently a manual step.
- [x] Add read-only consistency validation. Done: `dev.py docs --skills` runs `scripts/check_skills_sync.py`, which checks name uniqueness and byte-identical mirrors and never writes, stages or propagates deletions.

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

- [x] Classify then register/enforce strict markers; use `unit`, `integration`, `native`, `perf` only when needed. Done: five registered markers with `--strict-markers`, plus `parity` because A03 required a distinct comparison class.
- [x] Categorize optional vectorbt/Numba initialization; isolate broker/mutable-data access from offline tests. Done: lazy imports retained; the optional-tooling check is isolated in the `integration` tier; no test reads `data/` or a broker.
- [x] Fail on zero collected/selected tests; record skip reasons and external BLOCKED prerequisites. Done: `dev.py test` counts the selection and exits 3; empty `native`/`perf` tiers are documented as external BLOCKED.
- [x] Default focused tests to serial; use xdist only where measured beneficial. Done: serial by default; `-n auto` measured at 52 s versus 135 s serial for the offline suite.
- [x] Distinguish synthetic regression from recorded/native parity. Done: `parity` tier plus the four evidence classes in `docs/development.md`.
- [x] Document independent `DLF_ENVIRONMENT` application and `ENVIRONMENT` decorator controls; correctness gates keep development validation. Done: `DLF_ENVIRONMENT` is the app `Config` override that disables `check_assertions`; bare `ENVIRONMENT` only affects `br_pre_commit` tooling. Both `.gitlab-ci.yml` and `.env.example` pin `DLF_ENVIRONMENT=development` with the reason.
- [x] Initialize/install pinned submodule; test wheel outside checkout without `PYTHONPATH=src`. Done: CI uses `submodules: recursive`; `dev.py build --smoke` builds a wheel and imports all six packages in a throwaway venv outside the checkout.
- [x] Separate full mypy from ratchet; baseline updates are explicit reviewed changes. Done: mypy is documented as a non-gate with 209 pre-existing errors; the ratchet is the gate, and `dev.py check --tier ratchet` reports the bare-executable precondition instead of failing obscurely.

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

- [x] Repair links and envelope status without asserting compile/parity proof. Done: 25 broken links fixed; the false "missing envelope" claim is replaced by an explicit no-compile/no-tester statement.
- [ ] Reconcile CSV export behavior and unsupported debug option through bounded tasks. **OPEN** — recorded as READY task 4 in `docs/CURRENT_STATE.md`; not implemented here.
- [x] Correct obsolete skill paths/scripts/infrastructure references. Done: `pytest` and `pre-commit-check` rewritten against reality; `pandera-dataframe-validation` repointed from `app/helper/pandera.py` to `br_pre_commit`; five foreign skills removed.
- [x] Keep glossary detail out of architecture summaries. Done: `docs/architecture.md` links the glossary instead of restating it.
- [ ] Store full evidence as structured artifacts with compact current-state summary. **PARTIAL** — `docs/CURRENT_STATE.md` carries a compact measured baseline, but no structured evidence artifact (JSON) exists yet.
- [x] Add path/anchor checker returning file/line/target; exclude generated mirrors appropriately. Done: `scripts/check_docs_links.py`, reached through `dev.py docs`; mirrors are checked once via `.codex/skills` and mirror agreement is a separate check.

## Git strategy

- [x] One branch per issue/coherent batch; related implementation/tests/docs together. Done: this batch is coherent and the remote is unchanged; no branch was created because no commit was requested.
- [ ] Separate mechanical MT5 relocation from behavior changes and shared-submodule implementation from parent pointer update. **OPEN** — convention recorded; no relocation was performed, since the intended layout already matches the tracked tree.
- [ ] Include submodule identity/evidence in reviews; preserve fixture bytes/hashes. **OPEN** — recorded in the MR template and `mt5/AGENTS.md`; no MR was produced.
- [ ] Define EX5 artifact policy before untracking; prefer reproducible GitLab artifacts where practical. **OPEN** — `mt5/MQL5/Experts/XAUUSD_ROBUST_FINAL_LIVE_RCv2.ex5` remains tracked; the policy decision is unmade.
- [x] Review tracked `src/output.txt` and skill-bundled workflow examples; `.github/git-commit/workflows/` is not active root CI. Done: `src/output.txt` untracked and ignored; foreign skill examples removed. `.github/git-commit/workflows/` is a bundled skill example and remains untouched.
- [x] Conventional behavior-oriented commits; avoid whole-tree formatting or unrelated cleanup. Done: formatting was applied only to `scripts/`, `tests/conftest.py` and the new test module.
- [x] Normal reversible history; no automatic remote cleanup or origin rewrite. Done: no history or remote operation was performed.

Start GitLab adoption with templates/CI. Remote mapping/access is a separate explicit step; no endpoint is established in this checkout. MR body: goal, scope, commands/environment/source/results/skips/artifacts, risk/native limits, rollback and issue link.

## Context optimization strategy

Startup reads assigned task, root instructions, current state, applicable local instructions, one skill and affected contracts/code/tests/diff. Read archives/glossaries/full logs/history only for an unresolved requirement.

```powershell
rg --files src tests docs scripts config
rg -n "ResultFilesManifest" src tests
rg -n "process_native_stream|MarketState" src/application tests
```

- [x] Exclude caches/logs/backups/local dependencies/worktrees/terminal runtime from ordinary navigation, not from required task scope. Done: `ruff` exclude list, `.gitignore` (`.kilo/node_modules`, `.kilo/worktrees` ignored individually so project config stays trackable), `src/.mypy_cache` already ignored, and scoped-search guidance in `context-recovery`.
- [x] Keep deliberate access to `br_pre_commit/src` for hook/decorator work. Done: `src/AGENTS.md` names the submodule as the `pandera_validate` provider, and the benchmark adds the repository root to `sys.path` for it.
- [x] Turn large decision skill into small index/references; remove repeated names/discovery metadata. Done: 32 KB skill became a 2 KB index plus two references.
- [x] Put quick workflow atop journal guide; search glossary variables rather than load CSV. Done: the journal guide keeps its detailed reference on demand and the glossary stays a CSV lookup rather than a startup read.
- [ ] Emit compact failures and retain full artifacts with source/config/input identities for responsible evidence reuse. **PARTIAL** — `dev.py` prints compact one-line gate summaries and preserves each tool's exit code, but per-failure artifacts with input identities are A13, still open.
- [x] Use existing IDE navigation/mypy first; add AST import checks only for concrete dependency/cycle/API needs. Done: no AST infrastructure was added; the dependency map is documented in `docs/architecture.md` instead.

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

Retired 2026-10-04 by Project Leader decision: the cTrader surface was deleted outright rather than restored, so this row is closed.
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

- [x] **A01:** Record accurate source availability and instruction-compliance gaps; acceptance: current paths and prohibited processing are explicit, with no false native-proof claim. **Done** — the `XauRobustLiveEnvelope.mqh` "missing dependency" claim was false (present at `mt5/MQL5/Experts/`) and is replaced by an explicit no-compile/no-tester statement in `README.md`, `mt5/README.md` and `docs/todo/MT5-Python.Divergence.md`. The `process_native_stream` market-row iteration is recorded as debt in the decision skill and in `docs/CURRENT_STATE.md`.
- [x] **A02:** Reproducible CI environment; acceptance: supported interpreter/dependencies/submodule and executable offline/native job boundaries. **Done for offline** — Python 3.12, `pip install -e ".[dev]"`, `submodules: recursive`, MetaTrader5 excluded on Linux by a `sys_platform` marker, shared `dev.py` commands in both `.github/workflows/ci-python.yml` and `.gitlab-ci.yml`. The native job boundary is **declared, not executable here** (needs a Windows MetaEditor runner).
- [x] **A03:** Separate evidence classes; acceptance: offline regression, recorded comparison, compile and runtime parity cannot be confused by automation. **Done** — a `parity` marker separates comparison evidence from `unit` regression; `native`/`perf` are empty by design and `dev.py test` exits 3 on a zero selection; the four classes are stated in `docs/development.md`, the strategy `AGENTS.md`, `tests/AGENTS.md` and the MR template.

### High

- [x] **A04:** Recovery index/authoritative links; acceptance: fresh session identifies source/task/checks within five minutes and links resolve. **Done** — `docs/CURRENT_STATE.md` plus `dev.py inspect`; 25 broken links fixed, `dev.py docs` reports zero across 51 files.
- [x] **A05:** Canonical skills/status/discovery; acceptance: unique names and consistent installed Codex/Kilo guidance. **Done** — `.agents/skills` canonical (17), shared set (10) mirrored across five agents, duplicate `project-decisions` removed, 32 KB skill split into index + `references/`, five foreign skills removed, `pytest` and `pre-commit-check` rewritten against reality, and `dev.py docs --skills` validates uniqueness and byte-identical mirrors read-only. Discovery in each installed agent binary was not re-verified by running them.
- [x] **A06:** Deterministic test tiers; acceptance: nonempty selections, meaningful offline isolation and aligned fast hook. **Done** — registry-enforced classification, zero-selection refusal, parallel only where measured (52 s versus 135 s). The pytest **hook** was removed rather than realigned, because a ~135 s serial unit tier is not a commit-time gate; CI enforces it. Two zero-collecting placeholder modules were deleted.
- [x] **A07:** Dependencies/wheel/commands; acceptance: clean installed package and all advertised supported entry points import outside checkout. **Done** — single `pyproject.toml` manifest with core/dev/native/report profiles aligned to the measured environment; `pytz` was missing from the declared set and is now declared; wheel builds and all six top-level packages import outside the checkout; the dead `ctrader-cli` entry point is gone.
- [x] **A08:** Minimal command interface; acceptance: documented read-only/mutating contracts and preserved failures. **Done** — `scripts/dev.py` with `inspect`/`test`/`lint`/`format`/`typecheck`/`check`/`benchmark`/`build`/`docs`, documented in `docs/development.md`. Exit codes: tool code for gate failure, `3` for contract failure.
- [x] **A09:** GitLab templates/CI; acceptance: independently executable issues and shared-command MR evidence. **Templates and `.gitlab-ci.yml` delivered.** Not executable in this checkout: no GitLab endpoint is established, so remote access remains a separate explicit step.
- [x] **A10:** Active benchmark; acceptance: measures controller path with correctness, median, warm/cold and memory evidence. **Done** — `dev.py benchmark` now times the public `process_native_stream`, reuses the shared test fixtures, reports cold/warm/median/min-max/rows-per-second, digests outputs to prove repetitions agree, and can report peak traced memory. It previously timed private stage helpers and reported the fastest repetition.

### Medium

- [x] **A11:** Local instructions/responsibility map; acceptance: code/callers/contracts/tests discoverable without broad rereads. **Done** — `AGENTS.md` deltas for `src/`, the strategy package, `tests/` and `mt5/`, plus `docs/architecture.md`.
- [ ] **A12:** Compliant market-row implementation; acceptance: no interpreted row fallback, causal/order/state equivalence and explicit native limits. **OPEN** — deliberately not started here; it belongs to [vectorized-operation-improment.plan.md](vectorized-operation-improment.plan.md) and must not become a parallel implementation.
- [ ] **A13:** Artifact errors/evidence; acceptance: failing stage identifies stream/day/category/invariant and reproducible state without secrets. **OPEN** — contract stated in the `dataframe-contracts` skill; no diagnostic implementation yet.
- [ ] **A14:** Result ownership/shared helpers; acceptance: documented dependencies and stable selective test imports. **PARTIAL** — the coupling is documented in `docs/architecture.md` and the extraction is a READY task; the benchmark now imports the shared fixture module instead of duplicating candle construction.
- [x] **A15:** Context/search cleanup; acceptance: relevant scoped searches omit generated noise and long references remain accessible on demand. **Done** — `ruff` excludes `.git` and agent runtime (`ruff check .` previously failed on `.git/modules`), `.kilo/node_modules` and `.kilo/worktrees` are ignored individually instead of blanket-ignoring `.kilo`, tracked `src/output.txt` (a 15 KB captured log) is untracked, and the long decision skill moved to `references/`.

### Low / optional

- [ ] **A16:** AST checks/targeted coverage only for agreed gaps. **OPEN** — the dependency map exists in `docs/architecture.md`; no AST rule or coverage target has been agreed, so neither was added.
- [ ] **A17:** GitLab MCP only if CLI/API proves cumbersome. **OPEN and not indicated** — no endpoint is configured, and `.kilo/kilo.json` holds a literal bearer token that must stay untracked. `.kilo/kilo.json.example` is the sanitized template.
- [ ] **A18:** OpenTelemetry only for demonstrated diagnostic gaps. **OPEN and not indicated** — local timing already isolates every stage; no unresolved multi-stage latency was demonstrated.

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
