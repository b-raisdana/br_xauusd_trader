# Agentic coding audit

## Baseline and scope

Audited 2026-10-17 at baseline commit `f688d70`. Initial tracked tree: 578 entries, including 186 archive files, 135 source-tree entries, 32 test files and 156 skill copies across six agent directories (26 shared skills; initially identical). `br_pre_commit` is a Git submodule and was inspected without editing its implementation. User diagram relocation was present before this work and remains untouched.

Python ≥3.12, Hatchling, pandas/NumPy/Pandera, Numba, Vectorbt, Pydantic settings, DuckDB/Iceberg and Windows MetaTrader5 form the main stack. Pytest/xdist, Ruff, mypy and a staged incremental ratchet provide validation. Production signals use columnar processing; execution uses a compiled batch kernel. Scalar replay and archived alternatives have regression/reference roles. No repository-owned semantic index, embedding service or dependency graph tool was found in the inspected configuration; existing Python symbols, scoped search and tests are sufficient for this batch.

## Prioritized implementation

| Priority | Problem and solution | Benefit / cost | Risk and validation |
| --- | --- | --- | --- |
| P0 | CI selected Linux/Python 3.11 despite Windows MT5 and ≥3.12; use Windows and derive Python from package metadata, initialize hook submodule | Removes contradictory prerequisites; small config edit | Fresh resolution and hosted CI remain unverified; validate YAML/config locally |
| P0 | Root/research recovery required deleted registers; replace with actual state/task navigation, retain authority/safety | Reliable session recovery; small docs edit | Preserve approval and trading boundaries; review diff and links |
| P1 | Wheel listed nonexistent `src/xauusd`; remove that entry | Accurate package ownership; one-line edit | Inspect wheel contents; no source package relocation |
| P1 | Stale missing-envelope, scalar-production and replay-rejection claims; repair against current code | Avoids incorrect implementation choices; focused docs edits | Native parity still unproven; no trading logic changed |
| P1 | `.agents` edits did not trigger skill sync; extend hook filter, repair stale paths/budgets in identical mirrors | Consistent instructions across tools; modest mirrored diff | Keep existing sync implementation and tool compatibility; compare mirrors |
| P1 | Archives/mirrors pollute discovery; add targeted `.ignore` | Less irrelevant default ripgrep output; small config | Preserve explicit reference retrieval, Git and tests; verify source remains discoverable |
| P2 | Commands/module ownership required rediscovery; add runbook/task map and read-only repository checker | Direct task → files → tests navigation; modest maintenance | Standard library only; negative checker tests and link checks |
| P3 | Broad file splits, dependency removal, new index service or scalar-oracle deletion | Benefit unproven | Deferred: uncertain behavior/maintenance cost exceeds evidence |

## Authority and changed files

- `AGENTS.md`: universal contract; `CHATGPT_WORK.md`: research-only responsibilities. The former duplicate `CHATGPT_WORK copy.md` is a compatibility pointer.
- `docs/CURRENT_STATE.md`: small recovery index; `docs/ARCHITECTURE.md`: current module/contract ownership; `RUNBOOK.md`: executable workflow. Detailed behavioral work remains in existing design and acceptance documents.
- `pyproject.toml`: package/dependency/test/lint configuration. `.pre-commit-config.yaml`: hook selection; `.github/workflows/ci-python.yml`: manual hosted orchestration derived from package Python metadata.
- `.kilo/skills/`: shared skill authoring convention; existing tool mirrors remain byte-equivalent. No competing synchronization implementation was introduced.
- `.ignore`: ripgrep discovery policy only. No editor/global settings, Git tracking, test collection or archive ownership changed.
- `scripts/check_repository.py`: read-only navigation/package/mirror/workflow checks; `scripts/tests/`: isolated standard-library regression tests without application startup.
- Component READMEs, acceptance reference boundary and journal-comparison links were corrected. Detailed native lifecycle notes are explicitly marked for revalidation rather than represented as audited current behavior.

## Validation

Completed checks:

- `py -3.14 scripts/check_repository.py`: PASS, zero issues. Checks local link destinations (not heading anchors), package existence, shared mirrors and workflow prerequisites.
- `py -3.14 -m unittest discover -s scripts/tests`: PASS, 6 tests, including missing-link/package/mirror and workflow-drift rejection.
- `py -3.14 -m pytest -m unit -n 0`: PASS, 83 passed / 203 deselected, 176.90 s. Baseline collection found the same 83 unit tests. No trading implementation changed.
- Targeted Ruff check/format and mypy for both new Python files: PASS.
- `py -3.14 -m ruff format --check src scripts tests`: PASS, 158 files.
- `py -3.14 -m hatchling build -t wheel`: PASS; inspected wheel contains application/config/domain/helper/infrastructure/presentation and distribution metadata.
- `py -3.14 -m pre_commit validate-config` and diff whitespace check: PASS.
- Initial `pre_commit run --all-files`: FAILED. Existing whitespace/line-ending and Ruff fixes occurred outside the intended batch and were restored; system hooks also hit the broken Windows Store Python alias. After prepending the installed interpreter to process PATH, targeted pre-commit checks passed. The final config/skill pass skipped `pytest-fast` (reused the unit evidence above) and `sync-skill-files` (it mutates/stages; edits remain unstaged); the read-only checker verified mirror equality. Source-only ratchet/Pandera hooks did not apply because runtime source was unchanged.
- Broad `ruff check src scripts tests`: FAILED with 4 existing violations in benchmark_tick_stages.py, config/base.py, schemas/tick.py and date_utils/core.py; no fixes retained outside this scope.
- Broad `mypy src scripts tests`: FAILED, 676 errors in 73 existing files under corrected package discovery. The new files pass independently. Original configuration had invalid per-module global flags; attempting its configuration with the added namespace tests hits a duplicate-module error, so totals are not a comparable improvement metric.

No full compiled/integration suite, native compile/tester, clean-environment install or hosted CI run was performed. No dependency upgrade, live trading, commit or push occurred. Detailed existing debt and acceptance work remain in [follow-up](todo/agentic-maintenance.md).

## Before and after

| Dimension | Before | After |
| --- | --- | --- |
| Clarity | Missing recovery files; outdated production-path description | Current-state entry and task-to-module/test map |
| Authority | Duplicate research contract and contradictory guidance | One research contract, pointer compatibility and explicit current authority |
| Context | 146-line root contract; archives and skill copies exposed to broad discovery | Compact universal contract, scoped retrieval and retained explicit reference access |
| Search | No targeted repository search policy | Narrow ripgrep defaults; source/tests/contracts remain visible |
| Architecture | Production/oracle roles confused in package README | Columnar/batch/oracle boundaries documented without a rewrite |
| Workflow | Unsupported CI prerequisites and nonexistent wheel package | Metadata-derived supported workflow and package paths |
| Reliability | No cheap repository navigation consistency gate | Read-only checks and negative regression coverage |
| Maintainability | Manual rediscovery; stale duplicated claims | Existing tooling reused, no new dependency or service |

Measured on the final working tree: `rg --files --hidden -g !.git/**` lists 264 files with `.ignore`, versus 722 with `--no-ignore-dot` (same tree, other Git exclusions retained). Explicit archive search still returns reference matches. Root instructions shrank from 146 to 28 lines; the datastore README from 433 to 22 lines, with prior notes retained as non-authoritative archive reference. These are discovery/size measurements, not measured agent latency/token savings. Search counts measure discoverability only; no profitability, trading performance or native parity improvement is claimed.
