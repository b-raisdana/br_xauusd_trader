---
name: project-decisions
description: Use for any of — adding a "fetch/compute and persist" function (cache-or-generate); placing a new module/file under src/ (code-layers); adding network I/O or CPU-heavy fan-out (concurrency-and-blocking); before hand-rolling a new algorithm/transform (lib-first); building a filesystem path, CLI entrypoint, or settings/validation model (paths-cli-config); deciding what test type a change needs (test-strategy); writing/reviewing pandas/numpy code (vectorized-pandas-numpy); touching a file that reads/writes the OHLCV/indicator/label disk cache (feather/ZSTD migration-on-touch); adding/renaming a column or index level that holds timestamps (timestamp-column-naming); or a function about to duplicate another's shape with only a small explicit difference (merge-duplicated-logic-dry). One skill, several independent sections — read only the one(s) that match.
---

# Project decisions

- [Cache or generate](#cache-or-generate)
- [Code layers and folder ownership](#code-layers-and-folder-ownership)
- [Concurrency & blocking](#concurrency--blocking)
- [Check "archive_not_used_trash/"](#check-archive_not_used_trash)
- [Lib-first](#lib-first)
- [Paths, CLI & config libraries](#paths-cli--config-libraries)
- [Test strategy](#test-strategy)
- [Vectorized pandas/numpy](#vectorized-pandasnumpy)
- [Feather/ZSTD migration on touch](#featherzstd-migration-on-touch)
- [Timeframes and pandas frequencies](#timeframes-and-pandas-frequencies)
- [Timestamp column naming](#timestamp-column-naming)
- [Merge duplicated logic (DRY)](#merge-duplicated-logic-dry)
- [No no-op calls](#no-no-op-calls)

## Cache or generate

Trigger: adding a "fetch or compute this data" function, or a function called repeatedly with the same effective inputs.

**Disk-level** (persists across restarts): `read_file()` in `src/helper/data_preparation.py` (`ExtendedDf.read_file()` is the pandera-bound variant). Reads feather/ZSTD first, falls back to legacy CSV-zip (auto-migrates to feather/ZSTD and deletes the zip on a full read), else calls `generator(time_range_str)` and re-reads. New persisted artifacts: reuse `read_file()` with a `data_frame_type` + `generator` — don't invent a new naming/read/write scheme. Generators write via `write_data_file(df, data_frame_type, time_range_str, file_path)` (feather/ZSTD), never `to_csv(...zip...)`. An LRU memo (~32 entries) sits in front of the disk read, keyed on `(data_frame_type, time_range_str, file_path, skip_rows, n_rows)`; skipped for `timerange_is_not_cachable()` ranges (touch the live/incomplete present — never memoize, never leave cached on disk).

**In-memory** (derived from an already-in-RAM object, doesn't need to survive the process): cache on `df.attrs[private_key]`, not a dict — `pd.DataFrame` is unhashable. Self-bounded by the owning object's lifetime. Example: `_cached_training_frames()` in `training_datasets.py`, avoiding ~100x/quarter recompute of indicators/labels in the dataset-generator producer loops.

Rules:

- Key on exactly what the computation depends on — no more, no less.
- Always return a copy on a cache hit, never the cached object (mutation must not corrupt the cache).
- Never cache/memoize a `timerange_is_not_cachable()` range.
- Bound disk-level caches (fixed-size LRU, evict-oldest); in-memory caches self-bound via object lifetime.
- One cache per artifact type — don't add a second read-or-generate branch for data already cached elsewhere (Repository design pattern).

## Code layers and folder ownership

Trigger: adding/moving a module/file under `src/`, reviewing a layer boundary, or designing a feature/use case.

Target architecture: **Clean Architecture + DDD + Repository Pattern + feature/vertical-slice organization**. This repository is an offline trading pipeline, so `Presentation` includes CLI, report, notebook, and plotting adapters; an HTTP request/response cycle is not required.

### Conceptual layers

| Layer | Owns | May depend on | Must not depend on |
|---|---|---|---|
| `Presentation` | HTTP/API/UI/CLI controllers, request/response schemas, and user-facing adapters | `Application`; `Domain` only when genuinely required | `Infrastructure`; orchestration or business-policy bypasses |
| `Application` | Use cases, application services, orchestration, transaction boundaries, application DTOs/schemas, and application-defined ports | `Domain` and its own port contracts | Concrete infrastructure, Presentation, or framework-specific code |
| `Domain` | Entities, value objects, domain services, business rules, domain events, specifications, and repository interfaces | Standard library, third-party libraries, and its own contracts | `Application`, `Infrastructure`, `Presentation`, configuration mechanisms, frameworks, databases, and external I/O |
| `Infrastructure` | Databases, external services, messaging, filesystem, framework-specific implementations, and adapters | `Domain` contracts/value objects; `Application` ports only when implementing them | Presentation behavior and independent business policy |
| `Configuration` | Application-wide and cross-cutting settings loaded at the outer boundary | Standard-library or third-party settings mechanisms only | Domain or business logic |

### DDD and Clean Architecture mapping

Paths are physical paths under `src/`; Python imports omit the leading `src.`. Create subfolders only when they contain code. Track an empty required folder with `.gitkeep`, remove the marker when the first module is added, and do not create `__init__.py` solely for an empty folder.

| Concept | Place it in | Responsibility |
|---|---|---|
| Shared entity | `domain/<concept>/entities/` | Identity and lifecycle |
| Shared value object | `domain/<concept>/value_objects/` | Immutable value without persistent identity |
| Shared domain service | `domain/<concept>/services/` | Stateless business operation that does not naturally belong to an entity/value object |
| Domain event | `domain/<concept>/events/` | Business fact recorded by the domain; no side effects |
| Shared specification/rule | `domain/<concept>/` | Reusable business predicate or rule |
| Feature-private rule/value object | `application/<feature>/` | Rule or value owned by one use case |
| Repository/specification port | `domain/<concept>/repositories/` or `application/<feature>/ports/` | Contract owned by the layer/use case that consumes it |
| Use case | `application/<feature>/` | Transaction/workflow orchestration |
| Adapter | `infrastructure/<feature>/` | Implementation of a port for an external system or persistence mechanism |
| API/UI/CLI controller and schema | `presentation/<feature>/` | Driving adapter and transport-specific contract |

No separate global `interfaces/` folder is required: port contracts live beside their consumer, and implementations live in the owning Infrastructure feature adapter. Any layer may use `helper/` for a genuinely cross-cutting pure utility; `helper/` must not import a layer module or become a dependency hub.

### Dependency rules

Dependencies point inward toward the Domain.

Allowed dependencies:

```text
Presentation -> Application
Presentation -> Domain          # only when genuinely required
Application -> Domain
Infrastructure -> Domain
Infrastructure -> Application   # only when implementing an application-defined port/interface
```

Avoid:

```text
Domain -> Application
Domain -> Infrastructure
Domain -> Presentation
Application -> Presentation
Application -> Infrastructure
Presentation -> Infrastructure
```

Repository interfaces belong on the Domain side or in an explicitly defined Application port package. Repository implementations belong in Infrastructure. Application code depends on the abstraction; concrete adapters are supplied through dependency injection or outer-boundary composition.

### Request/use-case flow

A typical flow is:

```text
Client
  -> Presentation validates/parses the request
  -> Application use case/service orchestrates the operation
  -> Domain entities/value objects/services apply business rules
  -> Repository interface
  -> Infrastructure repository implementation
  -> Database or external system
  -> Application result/DTO
  -> Presentation serializes the response
  -> Client
```

For this offline pipeline, `Client` may be a CLI command, report, notebook, or backtest runner. Infrastructure is normally reached indirectly through an Application/Domain port; do not put broker, database, filesystem, or configuration calls in Domain business logic.

### Feature/use-case locality

Organize code around features/use cases, not only technical categories. Do not create global `schemas/`, `services/`, `validators/`, or `utils/` directories for code owned by one feature. Keep a complete feature-private set together, for example:

```text
src/
├── application/<feature>/
│   ├── service.py
│   ├── schemas.py
│   ├── rules.py
│   ├── value_objects.py
│   └── exceptions.py
├── domain/<shared-concept>/
├── infrastructure/<feature>/
│   └── repositories/
├── presentation/<feature>/
│   └── schemas.py
└── config/
```

A feature-private file may contain domain logic while physically living inside the feature package, such as `application/<feature>/rules.py`, when the rule is meaningful only to that use case. Promote a concept to shared `domain/` only when it is genuinely shared or independently meaningful. Prefer high cohesion and locality over large global technical-category directories.

### Configuration ownership

- Application-wide and cross-cutting configuration belongs in `src/config/`.
- Infrastructure configuration belongs in Infrastructure or in `src/config/` when shared.
- Presentation configuration belongs in Presentation.
- Feature/use-case-specific configuration belongs inside that feature.
- Domain business rules and constants belong in Domain when they represent business concepts rather than deployment settings.
- Load configuration at the application boundary and inject it into components. Domain code must not read environment variables, `.env` files, configuration frameworks, databases, or infrastructure settings directly.

Maintain `src/config/README.md` as a **registry only**. It must contain only the list of configuration file paths under `src/config/`; do not describe file contents, purpose, ownership, settings, behavior, or implementation details. Update it whenever a configuration file is added, removed, renamed, or moved.

### Placement rules

| Responsibility | Place it in |
|---|---|
| Feature-private code | Its feature/use-case package |
| Shared domain concepts | `domain/` |
| Use-case orchestration | `application/<feature>/` |
| Application-specific DTO/schema | `application/<feature>/` |
| API/request/response schema | `presentation/<feature>/` |
| Repository abstraction/interface | `domain/.../repositories/` or an explicit `application/.../ports/` |
| Persistence/external-service implementation | `infrastructure/<feature>/` |
| Global configuration | `src/config/` |
| Feature-specific configuration | The owning feature package |
| Genuinely cross-cutting pure utility | `helper/`, only when it is not feature or domain logic |

Do not move code to a shared layer merely because it is technically reusable. Do not use `helper/` as a catch-all. If one module has two responsibilities, split it at the layer boundary. Do not fork duplicate modules for a new pipeline; migrate or extend the existing module in a coherent, tested batch.

Existing mappings and migration constraints:

- `src/xauusd/` currently mixes Domain and Application responsibilities. Do not duplicate it; migrate or extend it in coherent batches while preserving tests.
- `src/ctrader_client/` is an Infrastructure adapter package. Preserve its external-client boundary and move implementation under `infrastructure/` when refactored.
- `scripts/` contains legacy entrypoints. New entrypoints belong in `Presentation`.
- Legacy `config/` data is not a reason to add configuration coupling to Domain; new global configuration belongs in `src/config/`.
- `integrations/` contains integration documentation; executable adapters belong in `Infrastructure`.
- `tests/` mirrors the layer or concern under test and is not production code.

Hard rules:

- Never import Presentation, Application, Infrastructure, or Configuration from Domain.
- Application depends on port contracts, not concrete adapters.
- Infrastructure may depend on Domain/Application contracts, never on Presentation.
- Presentation calls Application; it must not bypass Application to call Infrastructure directly. Presentation may call Domain only when genuinely required.
- Keep configuration and state explicit; inject them instead of reading module globals from Domain.
- Keep feature-private code close to its owner while preserving the dependency direction above.
- Keep `src/config/README.md` synchronized with the actual configuration files.


Splitting an oversized file (~500+ lines, by responsibility not raw count): extract one cohesive cluster per commit (few/no external callers first — check via grep), re-export moved names (`from new_module import name as name`) so callers keep working unchanged in that commit, log remaining clusters as follow-up instead of a full-file rewrite in one pass.

## Concurrency & blocking

Trigger: adding network/exchange I/O or CPU-heavy fan-out (indicators across symbols/timeframes, dataset gen, backtesting sweeps). Pick the cheapest primitive for the actual bottleneck — don't add threads/processes reflexively. Single-process offline pipeline (no services) — concurrency means in-process asyncio/thread-pool/process-pool, never standing up separate services.

- **I/O-bound** (CCXT fetch, disk read/write): don't block a loop over symbols/timeframes with a sync wait — `ccxt.async_support` + `asyncio.gather`, or `ThreadPoolExecutor` if a full asyncio rewrite isn't worth it yet (threads release the GIL while blocked on I/O).
- **CPU-bound** (indicator computation, dataset gen, training, backtesting sweeps): threads don't help (GIL). Vectorize first (see vectorized-pandas-numpy below) — usually removes the need for parallelism entirely; only if still a measured bottleneck, split independent units (symbols/timeframes/folds/Optuna trials) across `ProcessPoolExecutor`/`joblib.Parallel`.

Rules:

- No network/disk call inside a tight loop over more than a handful of independent items without a concurrency wrapper.
- Keep data fetch/prep and GPU/TF-compute phases separable — don't block on I/O while holding GPU/TF resources.
- Config/shared state passed explicitly (also what makes a function process-pool-safe — can't parallelize across processes if it reaches into shared mutable globals).
- Downcast dtypes once shape is finalized (`float32`, `category` for repeated strings); stream/chunk large reads (`chunksize=`, parquet row groups) instead of materializing a full multi-year file for a slice; prefer generators over fully-materialized lists for once-consumed values.

## Check "archive_not_used_trash/"

before coding first search inside, archive_not_used_trash/
these are codes we developed before and has good ideas to remeber for optimized processing.
do not move them blindly. every thime get the idea and implement it in a better way and try to optimize.
apply skulls defined project standard on the code.

**Hard guard: never edit or create any file under `archive_not_used_trash/`.** It is read-only reference — kept for its ideas, excluded from lint/mypy/tests by design (see `.pre-commit-config.yaml` and `pyproject.toml` excludes). If you need logic that lives there, re-implement it properly in the active tree (`src/`), applying current project standards; do not patch the archived copy, do not move it into `src/`, and do not add new files inside it. Treat the entire directory as frozen.

When re-implementing ideas from `archive_not_used_trash/`, apply the active tree's naming conventions: the codebase uses `time_range` / `time_range_str` for timestamp spans (not `date_range` / `date_range_str`), and `pd.date_range` is the only exception (pandas library call). Do not bring old `date_range` naming into `src/`.

## Helper imports

Trigger: any module that needs a shared third-party alias or project-wide shortcut. Prefer `app/helper/importer.py` aliases over local `import X as Y` so the mapping is defined once and consumed everywhere.

Current aliases:
- `go = plotly.graph_objects`
- `pa = pandera`
- `pt = pandera.typing`
- `ptd = pd.DataFrame`
- `ta = pandas_ta`

Rule: import the alias directly (`from helper.importer import ptd, ta`), then use `ptd(...)` instead of `pd.DataFrame(...)` and `ta.<indicator>(...)` instead of `pandas_ta.<indicator>(...)`. If the file needs other `pd` names (`pd.concat`, `pd.read_parquet`, etc.), keep `import pandas as pd` alongside the helper import — only the DataFrame constructor moves to `ptd`.

## Lib-first

Trigger: before implementing any new non-trivial algorithm/transform/indicator/concurrency primitive.

Order of attack:

1. Does pandas/numpy already express it (`rolling`, `groupby`, `where`/`select`, `merge_asof`)?
2. Does an existing dependency cover it? Already in use: `pandas-ta`, `scipy`, `pandera`, `optuna`, `ccxt`.
3. Is there a well-maintained third-party lib scoped to exactly this (table below)?
4. Only hand-write the residual logic no library covers.

Candidates (none adopted yet — evaluate once profiling shows a real bottleneck, not preemptively):

| Library                          | Reach for it when                                                                                                 |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `numexpr`                        | wide numeric expressions over large DataFrames, skip pandas' intermediate temporaries                             |
| `bottleneck`                     | C nanops/rolling stats once pandas' own rolling is the confirmed bottleneck (commented out in `requirements.txt`) |
| `numba`                          | the rare loop that truly can't be expressed as pandas/numpy ops                                                   |
| `polars`                         | dataset-gen rewrite, if pandas is confirmed the bottleneck at current scale                                       |
| `pyarrow`                        | already a dep — feather/parquet I/O, zero-copy interop                                                            |
| `dask.dataframe`                 | dataset gen once data stops fitting in RAM                                                                        |
| `ta-lib`                         | C-backed `pandas-ta` alternative if indicator computation is a measured bottleneck                                |
| `joblib`                         | CPU fan-out across symbols/timeframes/folds, after vectorization is exhausted                                     |
| `concurrent.futures` (stdlib)    | default thread/process pool — prefer over `joblib` unless its memory-mapping/caching is actually needed           |
| `asyncio` + `ccxt.async_support` | multi-symbol/timeframe fetch loops (currently sequential in `fetch_ohlcv.py`)                                     |
| `vectorbt`                       | planned backtesting replacement, not yet integrated                                                               |

Hand-rolling is justified for: domain-specific market-structure logic with no generic lib equivalent (peak/valley detection, bull/bear/side classification, base-pattern detection); or a lib that's unmaintained, has no vectorized path, or pulls a disproportionate dependency tree. Note the reason in the commit ("no vectorized lib does X, hand-rolled because Y") so the next pass doesn't re-search from scratch.

Anti-pattern: reimplementing rolling-window stats, JSON/CSV/parquet parsing, retry/backoff, or async HTTP plumbing that `pandas`/`pyarrow`/`ccxt`/stdlib already provide; a bespoke thread/process pool instead of `concurrent.futures`/`joblib`.

## Paths, CLI & config libraries

Trigger: building a filesystem path, a CLI entrypoint, or a settings/validation model.

- **Paths**: `pathlib.Path`, not `os.path`/`os.listdir`/`os.remove`/`os.rename`/`os.makedirs`/string-joined paths. Applies to (a) any function or file you're adding — new code doesn't inherit the surrounding file's old style just because the rest of that file is still `os.path`; and (b) any existing `os.path` call you're already editing for another reason, converted as part of the same edit (mirrors [Feather/ZSTD migration on touch](#featherzstd-migration-on-touch)'s policy exactly: touched lines migrate, untouched ones don't — never a repo-wide sweep). A private (`_`-prefixed) helper consumed only within the file(s) you're touching is free to return `Path` instead of `str`; a widely-imported public function (e.g. `symbol_data_path()`, imported across a dozen+ files) keeps its existing `str` return type — widening that contract is a separate, deliberate migration, not something an on-touch edit should trigger by itself.
- **CLI entrypoints**: `typer`, not `argparse`, for new CLIs. `fetch_ohlcv_cli.py` and `tier1_000_training.py` still use `argparse.ArgumentParser` — migrate on touch, not preemptively. `typer` isn't in `requirements.txt` yet; add it the first time a CLI is created or migrated.
- **Settings/config**: `pydantic_settings.BaseSettings` — already the pattern in `config/Config.py` (env-var overridable via `DLF_<FIELD_NAME>`, validated on load and on every assignment). Reuse `app_config`; don't add a second settings mechanism.
- **Structured data validation outside DataFrames** (function params, non-tabular value objects, API-shaped payloads): `pydantic.BaseModel`. Pandera (`domain/schemas/`) stays the tool for DataFrame-shaped schemas — pydantic doesn't replace it there.

## Test strategy

Trigger: deciding what test type a change needs, or reviewing test coverage. This repo: offline data/ML pipeline (pandas → TensorFlow → `backtrader`), no HTTP API/UI/other-team's-service caller — several categories below don't apply here.

| change is...                                                             | write a...                                                             | marker             |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------- | ------------------ |
| pure function, no I/O (indicator/label/scaling math)                     | unit test, synthetic in-memory fixture                                 | `unit`             |
| touching legacy code with no independent spec                            | characterization test — pin _today's actual_ output, never hand-derive | `characterization` |
| wiring modules together (dataset assembly, schema-gated repository read) | integration test                                                       | `integration`      |
| fixing a bug / protecting an invariant that broke before                 | regression test, named after the invariant, not the ticket             | `regression`       |
| broad "does it still work" check, safe every commit                      | smoke test                                                             | `smoke`            |
| full fetch→dataset→train→predict→strategy chain                          | e2e test, real/pinned data, not run every commit                       | `e2e`              |
| a vectorization/throughput claim                                         | perf test, explicit budget                                             | `perf`             |

Characterization discipline: run the real function against the fixture, capture what it _actually_ outputs today, assert that — never hand-compute an expected value. It's a refactor safety net, not a spec-conformance check (that's a regression test against a written spec, once one exists).

Not applicable here: CDC (no separately-deployed consumer/provider pair), synthetic/shadow monitoring (nothing deployed/serving), UI testing (plotly usage is diagnostic, not product UI), fault injection (no live broker/network calls yet).

Reviewing a PR: ask what type the change actually needs per the table — not "does it have _a_ test." (Mechanics — directory layout, naming, fixture policy, marker config — are in the separate `pytest` skill.)

## Vectorized pandas/numpy

Trigger: writing/reviewing any pandas/numpy code (dataset gen, indicator/label computation, scaling/normalization, OHLCV processing). A loop over rows/samples is a bug magnet and 10-1000x slower than the vectorized equivalent.

Red flags to eliminate: `for i in range(len(df))`, `df.iterrows()`, `df.apply(..., axis=1)`; `while remained > 0: ... .append(...)` sample-generation loops that recompute one slice at a time (see `train_data_of_mt_n_profit` in `training_datasets.py`) — prefer precomputing all boundaries at once (`np.random.randint(size=n)`) and slicing in one vectorized pass; repeated `np.array(df[cols])` conversion inside a hot loop — convert once, slice after; growing a list of DataFrames/arrays then `pd.concat`/`np.array` at the end, when boundaries could've been precomputed; scalar-by-scalar column assignment in a loop over columns.

Preferred patterns: boolean masking (`df.loc[mask, col] = value`); `np.where(cond, a, b)` / `np.select([...], [...], default=c)`; broadcasting across the whole array/DataFrame; `.groupby(...).transform(...)` / `.rolling(...).agg(...)`; batch `.loc`/`pd.IndexSlice` or `numpy.lib.stride_tricks.sliding_window_view` for windowed extraction at many offsets; `.to_numpy()` (not bare `.values`) for hot-path ndarray drops.

A loop is legitimate for: truly sequential/stateful logic where step _n_ depends on step _n-1_'s _computed result_ (vectorize the per-step body, the outer loop may stay); one-time setup/config code, not hot paths.

Review checklist: any row/element/sample loop replaceable by a mask, `np.where`/`np.select`, groupby/rolling, or a fully-vectorized index computation? Any repeated array conversion of the same columns to hoist out of a loop? Any column-by-column loop collapsible to one vectorized expression over the selected columns? Does the vectorized version's shape/dtype match what downstream code expects (upcasting, index alignment) before replacing the loop?

## Feather/ZSTD migration on touch

Trigger: about to edit a file that reads or writes the OHLCV/indicator/label disk cache — the `read_file()`/`data_frame_type` family (see [Cache or generate](#cache-or-generate)).

Feather/ZSTD (`write_data_file()`/`read_file()`-native) is the primary on-disk format; legacy CSV-zip (`to_csv(..., compression='zip')`) is the old format — still readable, no longer written. Migration is **incremental, on-touch only** — never a repo-wide sweep in one change.

Rule: if a file you're already modifying for another reason still writes via `to_csv(os.path.join(file_path, f'{name}.{time_range_str}.zip'), compression='zip')`, replace that call with `write_data_file(df, '<name>', time_range_str, file_path)` (import from `helper.data_preparation`) as part of the same edit. If the file isn't otherwise being touched, leave it as-is — the read-side (`_read_raw_data_file()` in `helper/data_preparation.py`) already auto-converts any lingering CSV-zip to feather/ZSTD and deletes the zip the first time it's read, so untouched files self-heal on next read regardless.

Don't: proactively grep the whole repo for remaining `.zip` writers and convert them all in one pass — that's the "change whole project at once" this rule exists to avoid.

## Timeframes and pandas frequencies

Trigger: using a project timeframe in a pandas frequency API (`pd.Grouper`, `pd.date_range`, `Timestamp.ceil`, `pd.Timedelta`, or equivalent).

Project timeframes use trading-domain semantics; do not pass their strings directly to pandas. Always convert them with `timeframe_to_pandas_freq(timeframe)` from `helper.date_utils` before supplying a pandas frequency.

- The helper preserves every configured non-weekly timeframe.
- `"1W"` is the exception: it maps to `"W-MON"`, giving Monday-start weekly candle bins. Plain pandas `"1W"` does not express the project's trading-week convention.
- For a fixed candle duration rather than a pandas frequency/offset, use `timeframe_to_period(timeframe)`; it returns `7 days` for `"1W"`.

## Timestamp column naming

Trigger: adding/renaming a column or index level that holds timestamps, or choosing a name for a timestamp-valued field.

This repo uses **two canonical names** for timestamps — each in a specific context. Don't invent a third (`datetime`, `time`, `ts`, `time_stamp`, `date_time`, `timestamp_ms`, etc.):

| Name | Context | Type | Where |
|------|---------|------|-------|
| `"date"` | pandas index / MultiIndex level holding timestamps | `datetime64[ns, UTC]` | Domain schemas (`OHLC`, `tick.py`, `OHLCVA`, `CausalExtremum`), `disk_cache_layout.index_by_date()`, query results, MultiIndex level alongside `"timeframe"` |
| `"timestamp"` | on-disk storage column (DuckDB/Iceberg) | `datetime64[ns, UTC]` | `_TIMESTAMP_COLUMN` in `duckdb_cache_helpers.py`, Iceberg filters, broker raw OHLCV (millisecond epoch) |

**Round-trip pattern** (follow, don't ad-lib):
1. Raw broker data arrives with `"timestamp"` (millisecond epoch integers).
2. `tick.py` converts: `df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)`.
3. `"date"` becomes the pandas index; `"timestamp"` column is dropped.
4. Domain code works with `"date"` index only.
5. On write to DuckDB/Iceberg, `to_storage_frame()` renames `"date"` → `"timestamp"` via `_TIMESTAMP_COLUMN`.
6. On read from DuckDB/Iceberg, `from_storage_frame()` / query helpers rename `"timestamp"` → `"date"` and set index.

Rules:
- **Pandas index level holding timestamps = `"date"`** — never `"datetime"`, `"time"`, `"ts"`. MultiIndex alongside `"timeframe"` is always `["timeframe", "date"]`.
- **On-disk storage column = `"timestamp"`** — referenced via `_TIMESTAMP_COLUMN` constant, never hard-coded except in that constant's definition.
- **Raw broker data column = `"timestamp"`** (millisecond epoch) — only in the fetch/ohlcv construction layer.
- **Never use `"datetime"` as a column/index name** — it's a Python/pandas type name, not a domain name. Causes confusion with `pd.datetime` (deprecated) and `datetime.datetime`.
- **Schema index type**: `pt.Index[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]` — always nanosecond UTC, never bare `datetime64` (timezone-naive) or `datetime64[us]` (microsecond).
- **Validation**: when adding a timestamp column, grep the codebase for similar names (`date`, `timestamp`, `datetime`, `time`) to ensure you're not introducing an alias for an existing column.

Anti-patterns that have been fixed:
- `date_utils.py:multi_timeframe_timestamps` used `names=["timeframe", "datetime"]` — corrected to `["timeframe", "date"]`.
- `date_utils.py:merge_to_ranges` referenced `group["datetime"]` — corrected to `group["date"]`.
- `duckdb_retention.py:remove_overlapping_periods` used `get_level_values("datetime")` — corrected to `get_level_values("date")`.

## Merge duplicated logic (DRY)

Trigger: about to add a function/method whose body is the same shape (same try/except/log/cleanup structure) as an existing one, differing only in a small, explicit piece — a value, a flag, an injected callable.

Rule: merge into one function taking that difference as an explicit parameter rather than keeping near-duplicate bodies side by side. Prefer fewer lines whenever it doesn't cost clarity: merging isn't just a style nicety here, it's the default call when two code paths are genuinely the same logic. Keep the parameter's effect visible at the call site (e.g. `flatten=True`/`flatten=False`) instead of hiding it behind a branch that always runs and happens to no-op for one caller — see [No no-op calls](#no-no-op-calls); DRY-merging a pair of functions must not reintroduce a no-op call one of them had deliberately dropped.

Fixed instance: `_migrate_feather_to_parquet()`/`_migrate_csv_zip_to_parquet()` in `infrastructure/datastore_engine/convert_to_parquest.py` (re-exported through `disk_cache.py`) were identical except for one `flatten_index_to_columns()` call — merged into `_migrate_to_parquet(df, parquet_file_path, source_file_path, *, flatten)`, so the write/log/unlink logic isn't duplicated, while the CSV-zip caller still passes `flatten=False` to skip that call outright.

## No no-op calls

Trigger: about to add a call/guard/branch justified as "for consistency", "for defense-in-depth", or "just in case", that provably does nothing on every actual path it runs on.

Rule: don't. Either the scenario is genuinely reachable — call the real guard and say which case it's for — or it isn't, and the call/branch gets deleted outright rather than kept as inert scaffolding. Same principle as CLAUDE.md's "don't add error handling/validation for scenarios that can't happen," applied to no-op calls specifically: a call whose own docstring admits it's "normally a no-op" on that path is a signal to remove it, not to keep it defensively.

Fixed instance: `_migrate_to_parquet()` in `infrastructure/datastore_engine/convert_to_parquest.py` (then still split into `_migrate_feather_to_parquet()`/`_migrate_csv_zip_to_parquet()`, later merged — see [Merge duplicated logic](#merge-duplicated-logic-dry)) called `flatten_index_to_columns(df)` unconditionally on a frame from `pd.read_csv()`, which never sets a custom index — the call could never do anything on that path, so its caller now passes `flatten=False` to skip it outright rather than relying on the callee's own no-op branch.

## Log on raise / exit / termination

Trigger: any code path that raises, exits, or otherwise terminates — `raise`, `sys.exit()`, `return` from a no-recovery path, fatal log + abort.

Rule: log the event with `log_e(...)` before every `raise`, `sys.exit()`, or equivalent termination. No silent exits. If a function has multiple early-exit branches, each must log its reason.

## brief comments

proper naming is always the first choice
a comment just allowed if what it says is not understandable from the name of nearby method and method arguments and requires to add real knowledge and do what is impossible by using proper naming.
