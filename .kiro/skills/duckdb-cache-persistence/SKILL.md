---
name: duckdb-cache-persistence
description: Use when adding or modifying any DataFrame persist/cache-or-generate code — the one required mechanism is the @duckdb_cache decorator, not read_file/read_file_windowed/find_cache_gaps/read_duckdb (being retired) or hand-rolled read/write-parquet logic.
---

# DataFrame persistence via @duckdb_cache

Trigger: persisting a generated/fetched DataFrame to disk so it isn't recomputed twice, or reading such an artifact back.

The decorator is implemented in [duckdb_cache.py](../../../src/infrastructure/datastore_engine/duckdb_cache.py); use the [datastore ownership and contract](../../../src/infrastructure/datastore_engine/README.md) and current code instead of removed migration plans. Manifest result persistence is a separate concern.

`@duckdb_cache(...)` is the **only** cache-or-generate mechanism for DataFrame persistence in this repo — it replaces `read_file`, `read_file_windowed`, `find_cache_gaps`, and `read_duckdb` outright, not alongside them (project-decisions § cache-or-generate: "one cache per artifact type"). Do not:

- Add a new `read_file_windowed(...)`-style call site — decorate the generator with `@duckdb_cache(...)` instead and call it directly.
- Hand-roll a new Parquet read/write path for a persisted artifact — `duckdb_cache` owns gap detection, generation dispatch, casting/validation, and the on-disk write.
- Reach into `archive_not_used_trash/` for any of the retired functions' old bodies — they're frozen reference only (project-decisions § "Check archive_not_used_trash").

Inspect the current signature, schema checks, frequency/boundary handling, `nan_means` and `post_fetch` before changing a caller. The implementation delegates storage to Iceberg helpers; do not assume the historical Parquet-only design still applies.

## Cross-module manifest handoff

Large DataFrame artifacts cross module boundaries by manifest reference to disk-resident data, not by copying the full frame. The manifest identifies the artifact and its schema, index and partition/path metadata. A manifest is a handoff contract, not a second cache/read-write mechanism: persisted DataFrames still use `@duckdb_cache(...)` and its owning storage API.

Keep temporary DataFrames incremental: contain only newly derived columns, preserve their index, and align them with existing frames by index when needed. Do not copy the existing frame's columns into temporary intermediates. Strategy calculations also follow [pandas vectorization rules](../pandas-multi-column-assignment/SKILL.md).

## Migrating an existing caller

Verify the decorated generator against the existing caller with focused regression coverage, then remove the old call site. Search imports and dynamic entry points before retiring any helper; archived code remains reference only. Do not create a parallel cache implementation.
