# `datastore_engine`

- [`@duckdb_cache` — usage](#duckdb_cache--usage)
- [How gap detection works](#how-gap-detection-works)
- [Storage](#storage)
- [Dev integrity check](#dev-integrity-check)
- [Iceberg garbage collection](#iceberg-garbage-collection)
- [Data pipeline upgrade plan](#data-pipeline-upgrade-plan)
- [SQLAlchemy + DuckDB ORM upgrade (reference)](#sqlalchemy--duckdb-orm-upgrade-reference)

Cache-or-generate persistence for DataFrames. Two stacks live here:

- **`@duckdb_cache`** (`duckdb_cache.py`, `duckdb_cache_helpers.py`, `iceberg_base.py`) — the current one. Iceberg-backed, `(timeframe, timestamp)`-indexed, precise gap detection. Use this for new code.
- **`disk_cache*`** (`disk_cache.py`, `disk_cache_layout.py`, `disk_cache_gaps.py`, `disk_cache_windowed.py`, `parquet_housekeeping.py`) — legacy Parquet windowed cache. Still used by `ExtendedDf.read_file`, `plotter`, `fetch_ohlcv_cli` gap listing. `app_config.default_cache_window_freq` / `cache_window_freq_overrides` feed only this path now.

## `@duckdb_cache` — usage

```python
@pandera_validate
@duckdb_cache(
    datastore_registry=DatastoreRegistry.UnifiedNoNAN,
    dataset_type="ohlcv",
    freqs=("1min",),                 # every dataset carries a timeframe level; never ()
    nan_means="not-available",       # "not-cached" (NaN = missing) | "not-available" (NaN = a real value)
)
def get_x(*, time_range_str: str, timeframe: str | None = None) -> pt.DataFrame[SomeMultiTimeframeModel]:
    ...
```

Contract:

- Generator **must** accept `time_range_str` (or whatever `boundary_arg` names) and a `timeframe` param, and **must** annotate its return as `pt.DataFrame[Model]` where `Model` has a `timeframe` index level. The decorator always calls it with `timeframe=None` = "produce every freq in `freqs`".
- Output is `[timeframe, date]` MultiIndexed, trimmed to the requested range.
- Rows whose candle has not closed yet (`open + timeframe >= now`) are dropped before caching and from the result.

## How gap detection works

1. Fetch the request's cached rows from Iceberg.
2. Expected labels = `timeframe_grid(start, end, tf)` per freq, anchored exactly as `aggregate_multi_timeframe_ohlcv`'s `pd.Grouper` bins. Every candle is labelled by its open time — opening Mondays 00:00 for `1W`, epoch-aligned grid otherwise. `MultiIndex.difference` against the cached rows → the genuinely missing `(timeframe, timestamp)` pairs (`nan_means` decides whether a NaN row counts as present).
3. `merge_to_ranges` → contiguous per-timeframe runs. `_missing_labels_to_data_ranges` widens each run forward to the last candle's close (`open label + one period`); `1W` is open-labelled like every other freq (its Monday label opens the week). `_union_time_ranges` merges those across freqs.
4. One `generator(time_range_str=window)` call per merged window; result upserted to Iceberg on `(timestamp, timeframe)`. A window may reach past the request's own end so a straddled coarse candle is computed in full — the final return is still trimmed to the original range, and adjacent windows regenerating the same candle is harmless (idempotent upsert + in-RAM de-dupe).
2. Expected labels = `timeframe_grid(start, end, tf)` per freq, anchored exactly as `aggregate_multi_timeframe_ohlcv`'s `pd.Grouper` bins — Mondays 00:00 for `1W`, epoch-aligned grid otherwise. `MultiIndex.difference` against the cached rows → the genuinely missing `(timeframe, timestamp)` pairs (`nan_means` decides whether a NaN row counts as present).
3. `merge_to_ranges` → contiguous per-timeframe runs. `_missing_labels_to_data_ranges` widens each run to the base span its candles need: to the last candle's close for left-labelled freqs; one week earlier for `1W` (its label closes the week). `_union_time_ranges` merges those across freqs.
4. One `generator(time_range_str=window)` call per merged window; result upserted to Iceberg on `(date, timeframe)`. A window may reach past the request's own end so a straddled coarse candle is computed in full — the final return is still trimmed to the original range, and adjacent windows regenerating the same candle is harmless (idempotent upsert + in-RAM de-dupe).

## Storage

One unpartitioned Iceberg table per `(datastore_registry, market, symbol, exchange, schema)`, under `data/dataset_db/<registry>/`. `timeframe` is an index column, never a partition key. `_write_gap` uses `Transaction.upsert(join_cols=["date", "timeframe"])`.

## Dev integrity check

When `app_config.environment == "development"`, every call spawns a background thread that re-fetches the boundary and `assert_frame_equal`s it against what was returned; a mismatch logs and `os._exit(1)`. Injectable abort (`duckdb_cache_helpers._abort`) for tests.

## Iceberg garbage collection

`app/infrastructure/datastore_engine/iceberg_base.py` (the `@duckdb_cache` storage layer, since the migration from plain DuckDB tables to real Apache Iceberg via `pyiceberg`) has no garbage collection. Every gap-fill write (`_write_gap`) creates a new Iceberg snapshot; nothing ever expires old snapshots, drops orphaned data files (aborted writes, superseded overwrite-mode upserts), or drops empty tables (a table created via a fully-filtered gap write — e.g. a window with no closed candles — has a snapshot with zero rows and stays around forever).

### Why deferred

Not needed for correctness today — the sole production caller (`get_base_timeframe_ohlcv` in `app/infrastructure/ohlcv/ohlcv.py`) has no volume/retention pressure yet. Scoped out of the initial pyiceberg migration to keep that change reviewable; tracked here instead of silently dropped.

### What it needs, when picked up

- **Snapshot expiry**: `Table.expire_snapshots()` (pyiceberg 0.11+) on a retention window (e.g. keep last N snapshots or last N days) — every `upsert()` call creates a new snapshot via `overwrite()`.
- **Orphan file cleanup**: no first-class pyiceberg API as of 0.11.1; would need `catalog.list_tables` → `Table.inspect.files()`/manifest walk to find data files not referenced by any live snapshot, or wait for pyiceberg to add a `remove_orphan_files`-equivalent (Spark/Java Iceberg have one).
- **Empty-table cleanup**: `Table.current_snapshot() is None` (never-written) or a snapshot with zero rows → `catalog.drop_table(identifier)`. This part is cheap and was actually implemented in a draft of the migration (walk `catalog.list_namespaces()` → `list_tables(ns)` → check `current_snapshot()`), then pulled to keep this doc as the single place the GC design lives — reuse that draft directly when this is picked up, don't redesign from scratch.
- Needs a caller/schedule: nothing invokes GC today (the old, pre-Iceberg `iceberg_duckdb_garbage_collection` had zero callers too) — decide whether it's a manual CLI command, a periodic background task, or invoked from a training-pipeline entrypoint before this ships.

## Data pipeline upgrade plan

Open work only. Shipped work (Feather → Parquet migration, `dataset_db` repartitioning + DuckDB batched-window reads, `BasePattern`/`rolling_mean_std` converted to `windowed=True`) isn't re-documented here. Also still deferred, not covered below: catalog/data-quality extensions, ClickHouse (parked, see `docs/infrastructure.md` § ClickHouse), PyArrow dataset API, versioned datasets, Spark/Cassandra/Polars/Zarr.

### Remove the `windowed=False` path from `cache_on_disk()`

No active `@cache_on_disk` site uses `windowed=False` (the default) any more — every one left in `app/` now passes `windowed=True` (`get_base_timeframe_ohlcv`/`get_multi_timeframe_ohlcv`, `get_multi_timeframe_ohlcva`, `get_multi_timeframe_base_patterns`, `get_multi_timeframe_rolling_mean_std_ohlcv`). The remaining step: remove the `windowed: bool` parameter from `cache_on_disk()` and the `if windowed:`/`else` dispatch in `wrapper()` (`infrastructure/datastore_engine/disk_cache.py:432-462`), leaving `read_file_windowed()` as the only entry point — `read_file()` itself stays as its per-window primitive (also still used directly by `ExtendedDf.read_file()` and other non-decorator callers). Not done yet; not blocked on anything.

### Postponed, not tracked: `PeakValley`/`BullBearSide`/`BullBearSidePivot`/`PeakValleyPivots`

These 4 modules (5 generator functions) could never safely convert to `windowed=True` as written — each needs unbounded context from outside its own calendar window, in both directions (backward *and* forward: `PeakValley.calculate_strength()`, `BullBearSide`'s trend/candle-trend `merge_asof` calls), not just a fixed lookback buffer. An adaptive expand-until-resolved approach (mirroring `get_multi_timeframe_ohlcva`'s ATR lookback, but sized at run time instead of fixed in config) would fix the backward half cheaply via DuckDB; the forward half would additionally need deferred cache writes (a window's file isn't finalized until its forward dependency resolves), which `disk_cache.py` has no mechanism for today.

Moot for now: none of these 5 generators are reachable from any active model-training or backtesting path (`train.py` → `build_dataset()` → `datafeeder_input3_outcome1.py` touches only `read_multi_timeframe_ohlcv`/`CausalExtremum`; `BasePatternStrategy.py` — the one active backtesting strategy — uses only `BasePattern`, not these). Moved to `app/archive_not_used_trash/domain/price_action/` (mirroring the original `app/domain/price_action/` hierarchy) rather than fixed. `PivotsHelper.py`, `ClassicPivot.py`, `AtrMovementPivots.py`, and the four `presentation/market_structure/*_plotter.py` visualization scripts still reference the archived modules and had their imports repointed accordingly — `ClassicPivot.py` and `AtrMovementPivots.py` were already broken by pre-existing, unrelated bugs (a stale `infrastructure.ohlcv.*` import path, a wrong function name) before this move; left as found, out of scope. Postponed indefinitely — not tracked as open work here.

## SQLAlchemy + DuckDB ORM upgrade (reference)

Here's a complete, worked version combining both — Pandera as source of truth, generating SQLAlchemy Core `Table`s, then imperatively mapping full ORM classes (with relationships) on top of them.

### The challenge with relationships

Pandera has no native concept of foreign keys or relationships — it validates DataFrame shape, not relational structure. So the generator handles columns/types/constraints from Pandera, and you specify FKs/relationships separately, alongside the schema. That's the one piece that can't be fully derived — everything else (columns, types, nullability, PK) comes from Pandera.

### 1. Define Pandera schemas (source of truth for columns)

```python
import pandera as pa
from pandera.typing import Series
from datetime import datetime
from typing import Optional

class CustomerSchema(pa.DataFrameModel):
    id: Series[int] = pa.Field(ge=1)
    name: Series[str]
    region: Optional[Series[str]] = pa.Field(nullable=True)

    class Config:
        coerce = True

class OrderSchema(pa.DataFrameModel):
    id: Series[int] = pa.Field(ge=1)
    customer_id: Series[int]
    amount: Series[float] = pa.Field(ge=0)
    created_at: Series[datetime]

    class Config:
        coerce = True
```

### 2. Generator: Pandera schema → SQLAlchemy Core `Table`

```python
import numpy as np
from sqlalchemy import Table, Column, MetaData, ForeignKey
from sqlalchemy.types import Integer, Float, String, DateTime, Boolean, TypeEngine

PANDAS_TO_SQLA: dict[type, type[TypeEngine]] = {
    np.dtype("int64"): Integer,
    np.dtype("float64"): Float,
    np.dtype("bool"): Boolean,
    np.dtype("datetime64[ns]"): DateTime,
    np.dtype("object"): String,
}

def pandera_to_table(
    schema_cls: type[pa.DataFrameModel],
    table_name: str,
    metadata: MetaData,
    primary_key: str,
    foreign_keys: dict[str, str] | None = None,   # {"customer_id": "customers.id"}
) -> Table:
    schema = schema_cls.to_schema()
    foreign_keys = foreign_keys or {}
    columns = []

    for name, col in schema.columns.items():
        sqla_type = PANDAS_TO_SQLA.get(np.dtype(col.dtype.type), String)
        col_args = [name, sqla_type]
        if name in foreign_keys:
            col_args.append(ForeignKey(foreign_keys[name]))
        columns.append(
            Column(*col_args, primary_key=(name == primary_key), nullable=col.nullable)
        )

    return Table(table_name, metadata, *columns)
```

### 3. Generate tables + imperatively map ORM classes with relationships

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import registry, relationship

metadata = MetaData()
mapper_registry = registry(metadata=metadata)

customers_table = pandera_to_table(CustomerSchema, "customers", metadata, primary_key="id")
orders_table = pandera_to_table(
    OrderSchema, "orders", metadata,
    primary_key="id",
    foreign_keys={"customer_id": "customers.id"},
)

class Customer:
    def __repr__(self):
        return f"Customer(id={self.id!r}, name={self.name!r}, region={self.region!r})"

class Order:
    def __repr__(self):
        return f"Order(id={self.id!r}, customer_id={self.customer_id!r}, amount={self.amount!r})"

mapper_registry.map_imperatively(
    Customer, customers_table,
    properties={"orders": relationship(Order, back_populates="customer")},
)
mapper_registry.map_imperatively(
    Order, orders_table,
    properties={"customer": relationship(Customer, back_populates="orders")},
)
```

At this point `Customer`/`Order` are fully normal ORM classes — same as declarative classes — but their columns came entirely from `CustomerSchema`/`OrderSchema`. One definition of "what an order looks like," reused for both DataFrame validation and DB mapping.

### 4. `db.py` — engine, unchanged from before

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

engine = create_engine("duckdb:///analytics.duckdb", poolclass=NullPool)
Session = sessionmaker(bind=engine)

metadata.create_all(engine)  # creates customers + orders using the generated Tables
```

### 5. CRUD — identical usage to a hand-written declarative model

```python
from db import Session

with Session() as session:
    session.add(Customer(id=1, name="Acme", region="EMEA"))
    session.add(Order(id=1, customer_id=1, amount=1200.0, created_at=datetime.utcnow()))
    session.commit()
```

### 6. Join + aggregation — exact same syntax as before

```python
from sqlalchemy import select, func
from db import Session

with Session() as session:
    stmt = (
        select(
            Customer.region,
            func.sum(Order.amount).label("total_revenue"),
            func.count(Order.id).label("order_count"),
        )
        .join(Order, Order.customer_id == Customer.id)
        .group_by(Customer.region)
        .order_by(func.sum(Order.amount).desc())
    )
    for row in session.execute(stmt):
        print(row.region, row.total_revenue, row.order_count)
```

### 7. Validate a DataFrame with Pandera, then `merge()` each row through the ORM

```python
import pandas as pd
from db import Session

df = pd.DataFrame({
    "id": [1, 2],
    "name": ["Acme Corp", "Globex"],
    "region": ["EMEA", "AMER"],
})
validated = CustomerSchema.validate(df)

with Session() as session:
    for row in validated.itertuples(index=False):
        session.merge(Customer(id=row.id, name=row.name, region=row.region))
    session.commit()
```

### 8. Validate + bulk upsert (SQL-level, for larger batches)

```python
from sqlalchemy import text
from db import Session

def upsert_orders(df: pd.DataFrame):
    validated = OrderSchema.validate(df)  # raises pa.errors.SchemaError on bad data
    with Session() as session:
        session.execute(
            text("""
                INSERT INTO orders (id, customer_id, amount, created_at)
                VALUES (:id, :customer_id, :amount, :created_at)
                ON CONFLICT (id) DO UPDATE SET
                    amount = excluded.amount,
                    created_at = excluded.created_at
            """),
            validated.to_dict(orient="records"),
        )
        session.commit()

upsert_orders(pd.DataFrame({
    "id": [1, 3],
    "customer_id": [1, 2],
    "amount": [1500.0, 300.0],
    "created_at": [datetime.utcnow()] * 2,
}))
```

Since `validated` was checked against `OrderSchema` — the same schema that generated the `orders` table's columns — there's no drift possible between what Pandera allows through and what the table accepts.

### 9. Alembic compatibility

Alembic autogenerate works against `target_metadata` — since `metadata` here is a real `MetaData` object populated by `pandera_to_table`, it plugs in exactly like a declarative `Base.metadata` would:

```python
# alembic/env.py
from your_module import metadata  # the same MetaData built from Pandera schemas
target_metadata = metadata
```

```bash
alembic revision --autogenerate -m "create customers and orders from pandera schemas"
alembic upgrade head
```

One caveat: if you change a Pandera schema (add a field, change a type) and regenerate the `Table`, you need to re-run the generator _before_ calling `alembic revision --autogenerate`, since Alembic diffs against whatever `metadata` currently holds — not against the Pandera class definitions directly. In practice this means: Pandera schema change → re-import/rebuild `metadata` → autogenerate → review the migration → apply. The generator is a build step, not something Alembic understands natively.

### What this buys you, concretely

|                                      | Before (double coding)                             | Now                                                                                                                                                                                                                              |
| ------------------------------------ | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Column names/types                   | Defined in both `DataFrameModel` and `Column(...)` | Defined once in `DataFrameModel`                                                                                                                                                                                                 |
| Field constraints (`ge=0`, nullable) | Pandera-only, not reflected in ORM                 | Nullability flows through; value constraints (`ge=0`) still Pandera-only — SQLAlchemy has no generic "check constraint from Pandera Field" bridge, so add `CheckConstraint` manually if you need it enforced at the DB level too |
| Relationships/FKs                    | Hand-written either way                            | Still hand-written (Pandera has no relationship concept) — the one irreducible piece                                                                                                                                             |
| Migration history                    | Alembic vs. hand-maintained models could drift     | Alembic diffs the _generated_ `MetaData`, same as any declarative setup                                                                                                                                                          |

The remaining manual work is genuinely irreducible (relationships, FK wiring, DB-level `CheckConstraint`s) — everything else that used to require touching two class definitions now only requires touching the Pandera model.

## `@duckdb_cache` — full design spec

### Workload

Training system, not online/live-fetch: random historical date → fetch surrounding history → compute derived factors. Requests skew toward old, closed data, scattered across a long history. Caching compounds across training runs as coverage trends toward "almost everything already cached."

- **Precise gaps**: a request is diffed against the cache at `(timeframe, timestamp)` granularity (not bucketed into fixed calendar windows), so generation covers exactly the missing candles, plus a widening so no partially-covered coarse candle is computed from a truncated slice.
- **Coverage-check frequency**: every random-date sample triggers a coverage lookup.

### Storage architecture

Single dataset per `datastore_relative_path`, indexed by `[timeframe, timestamp]`. No per-freq file or directory split. All freqs for a given artifact live in one logical dataset. Every dataset carries a `timeframe` level — a nominally single-cadence artifact (e.g. base OHLCV) is tagged with its native cadence and passes `freqs=(that_cadence,)`; there is no no-timeframe path.

Physical layout is a true unpartitioned single dataset — not Hive-partitioned by `timeframe`. The dataset may still span multiple physical files (e.g. one file per gap-fill write, or compaction-driven splits), but file boundaries carry no semantic meaning — `timeframe` is never used as a partition key. Coverage queries always filter/group by the `[timeframe, timestamp]` index columns against the dataset as a whole, never by routing to a specific file based on `timeframe`.

- Writes go through an Iceberg `upsert` keyed on `(timestamp, timeframe)` — idempotent, so regenerating a candle already on disk is harmless.
- **Coverage/gap detection**: fetch the request's rows, build the expected `(timeframe, timestamp)` label set (`timeframe_grid` per freq, anchored exactly as the aggregator's `pd.Grouper` bins — Mondays for `1W`, epoch-aligned otherwise), and take `MultiIndex.difference`. `merge_to_ranges` collapses each timeframe's missing labels into contiguous runs; `_missing_labels_to_data_ranges` widens every run to the full base span its candles need (last candle's close for left-labelled freqs; one week back for `1W`, whose label closes the week); `_union_time_ranges` merges those across freqs into the minimal set of gap `time_range_str`s.
- **Generation**: one `generator(timeframe=None, time_range_str=gap)` call per merged gap window; the result is upserted. Widening can make two adjacent windows regenerate the same coarse candle — accepted (idempotent upsert; the in-RAM assembly also de-dupes on `(timeframe, timestamp)`).
- **`nan_means`** still disambiguates NaN within the schema's nullable columns before the diff: `"not-cached"` → NaN row is missing; `"not-available"` → NaN is a confirmed value.

### Schema contract

The schema contract is inferred from the generator's return-type annotation — not passed as an explicit decorator kwarg.

Validation/casting uses pandera's own API directly (`DataFrameModel.validate(df)` / `pt.DataFrame[Model]`) — not the legacy casting helpers (`apply_as_type`, `Pandera_DFM_Type`). Anything in the old casting path that isn't just a direct `.validate()` call moves to `archive_not_used_trash/`.

Validation depth is environment-gated:
- `app_config.environment == "development"`: full `.validate()` (lazy, all checks) on every generated/re-fetched frame — same gate as the development-mode integrity check.
- Outside development: coercion/dtype cast only (`coerce=True`, no full constraint/lazy validation); the covered-window re-fetch (step 8) skips validation entirely, since that data already passed full validation once at write time (step 7).
- Applies throughout the flow: step 7 (per-gap validate/cast) and step 8 (covered-window portion) both follow this gate.

A `nan_means="not-available"` generator whose own schema grows a new column after data is already cached will misread old rows' NaN in that column as confirmed-valid rather than not-yet-computed. `"not-available"` is only used for OHLCV, whose columns are fixed — this is handled manually if it ever arises, not designed around.

### Decorator flow

```python
@duckdb_cache(
    datastore_relative_path: Path,
    dataset_type: str,                      # keys into cachable_indexes(indexes, dataset_type)
    boundary_arg: str = "time_range_str",   # raise if not in generator signature
    freqs: tuple[str, ...] = tuple(app_config.timeframes),  # a single-cadence artifact passes (native_cadence,); never empty
    post_fetch: Callable[[SchemaContract], SchemaContract] | None = None,
    nan_means: Literal["not-cached", "not-available"] = "not-cached",
)
def generator(*, timeframe: str | None, time_range_str: str, ...) -> SchemaContract: ...
```

1. **Decoration time**: `boundary_arg in inspect.signature(generator).parameters`; `freqs` non-empty and `set(freqs) <= set(app_config.timeframes)`; generator's return-type annotation must be present and resolve to the schema contract type, else raise.
2. **Call time**: resolve dataset location dynamically from `datastore_relative_path` plus runtime context (market/symbol/exchange), never baked in at decoration time.
3. Normalize the incoming boundary to `(start, end)`.
4. Fetch the request's cached rows; compute the precise gap windows (see Storage architecture → Coverage/gap detection). Indexes `cachable_indexes(indexes, dataset_type)` excludes are dropped from the expected label set (see Non-cacheable indexes) but not skipped from generation.
5. If there are no gap windows the cache already covers the request — skip to step 8. A read/parse failure on existing data is treated as absent (regenerate), not a hard error.
6. Gaps are processed in ascending chronological order; each gap is written and durable independently, so an interrupted run resumes cleanly.
7. Per merged gap window:
   - `results = generator(*args, timeframe=None, **{boundary_arg: gap})` — `timeframe=None` means "produce every freq in `freqs` for this window in one call"; `gap` may reach past the request's own end so a straddled coarse candle is computed in full
   - validate/cast `results` against the schema contract, drop not-yet-closed candles
   - upsert to Iceberg keyed on `(timestamp, timeframe)`
7b. Non-cacheable indexes (see Cacheable indexes), every call, regardless of gaps: call `generator(..., timeframe=None, boundary_arg=non_cacheable_span)` unconditionally for the excluded span, validate the same way, never write it to disk, defensively delete any stray data covering those indexes.
8. Assemble the result in RAM. Step 4 already read the cached rows; step 7 produced validated frames for gaps; step 7b (if applicable) produced a validated frame for the non-cacheable span. Concatenate, de-dupe on `(timeframe, timestamp)` (keep the freshly generated row), normalise the timestamp to `ns` UTC (Iceberg exports `us`), sort, and trim to the **originally requested** boundary — generation reaching past a gap's nominal end never widens the return.
9. Apply `post_fetch(final_result)` if given, dispatch the development-mode integrity check without waiting on it, return `final_result` immediately.
10. Development-mode only, backgrounded, non-blocking: re-fetch the same boundary via a fresh query through the same DuckDB connection, validate, compare against the frame already returned in step 9. Never runs in production.

### Development-mode integrity check

- **Gate**: `app_config.environment == "development"` only.
- **Dispatch**: background thread, no `join()`.
- **Throttling**: none at the app level. The verification query goes through the same DuckDB connection as everything else; concurrent queries queue naturally at the connection.
- **Comparison**: `pd.testing.assert_frame_equal`, or a cheap shape/dtype/row-count check first, full comparison only on mismatch. Also compares per-column NaN counts/positions between the two frames — a shape/dtype/row-count match can still hide a NaN-distribution drift (e.g. `nan_means` misclassification, a column silently going all-NaN).
- **Logging**: `datastore_relative_path`, boundary, `freqs`, window(s) at start; success line on match; specific differing rows/columns/dtypes on mismatch.
- **On mismatch**: hard-stop the process (`os._exit(1)` after logging) — a background thread's own exception won't propagate or halt the main thread.
- **Testing this mechanism**: inject the abort call (module-level, swappable) so a forced mismatch can be asserted without killing the test runner.

### Cacheable indexes

Whether an index is eligible for caching at all is determined by `cachable_indexes(indexes, dataset_type) -> Index`, a pluggable per-dataset-type function — not a single hardcoded live-candle rule. Different dataset types have different maturity requirements before a candle's index counts as cacheable:

- **Plain OHLCV / most feature types**: an index is cacheable once its own candle is closed. The still-open current candle is excluded.
- **Lookahead-dependent features** (e.g. forward-window zigzag pivots, MFE/MAE/RER labels needing a confirmed forward horizon): an index is cacheable only once N additional candles beyond it have also closed — the exclusion zone trails further behind "now" than a single candle.

`cachable_indexes` is looked up by `dataset_type` and applied wherever the grid or a requested boundary needs to be filtered for eligibility — grid construction (step 4) and the non-cacheable-window handling (step 7b) both call it rather than assuming a single fixed live-candle cutoff.

### Non-cacheable indexes (live and near-live)

Indexes `cachable_indexes` excludes are generated and returned on every call that touches them — never counted as coverage, never persisted, always regenerated in full. Bounded cost (the excluded tail, not the dataset). Incremental refresh for this tail, if a generator needs it, is internal to that generator; it still returns a plain frame to `duckdb_cache`.

### Concurrency

Writes are issued through a DuckDB connection — the connection itself performs the write (`COPY ... TO ...` / native table write), not raw pandas Parquet writes. DuckDB's native single-writer locking on the connection arbitrates concurrent gap-fill attempts. No app-level `flock` or double-checked locking.

### New skills

- **DataFrame persistence via `duckdb_cache`** — the one way to persist/cache-or-generate a DataFrame in this repo, once implemented.
- **SQLAlchemy + DuckDB ORM** — scoped to relational metadata only (e.g. an optional future coverage ledger), not bulk time-series rows.

### Testing

- unit: `timeframe_grid` anchoring, `_union_time_ranges`, `_missing_labels_to_data_ranges`, `find_gaped_ranges` (empty cache, full cache, partial-coarse-candle widening), both `nan_means` modes.
- integration: full round-trip — precise gap detection, idempotent re-run, `post_fetch`, not-yet-closed candle never persisted.
- regression: added once a concrete bug surfaces.

### Open items

None outstanding.

### File bloat / stale data

Excluded from this design — handled by a separate mechanism outside `duckdb_cache`.

- Compaction merges the small files produced by successive gap-fill writes into fewer, larger files. Since the dataset is unpartitioned, this is a plain file-count/size operation with no `timeframe`-aware repartitioning logic — compaction preserves the `[timeframe, timestamp]` index correctly across the merge.
- Compaction and cleanup mechanisms apply to whatever files accumulate under this layout.
- Manual regeneration of an already-cached window (generator bugfix, corrected source data) requires deleting the old data first — there is no automatic staleness/versioning detection.

### Non-goals

- Reading/migrating legacy cached data.
- Multi-writer distributed locking beyond DuckDB's own connection-level arbitration.
- ClickHouse or any client-server backing.
- File compaction and stale/versioned-data cleanup (see File bloat / stale data).
- Coverage ledger — a separate metadata table tracking which `(dataset, timeframe, window)` combinations are already generated, to avoid scanning the real dataset for coverage checks.
- Cache invalidation on generator-logic change.
