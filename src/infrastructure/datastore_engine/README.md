# DataFrame datastore

Use `@duckdb_cache` for new cache-or-generate DataFrame work. Manifest result persistence belongs to `infrastructure/result_processing/` and is independent.

## Ownership

| Module | Responsibility |
| --- | --- |
| [duckdb_cache.py](duckdb_cache.py) | Decorator orchestration, gap generation, assembly and schema validation |
| [duckdb_cache_helpers.py](duckdb_cache_helpers.py) | Cache/schema helpers and development integrity checking |
| [iceberg_base.py](iceberg_base.py) | Iceberg table access and upsert storage |
| [duckdb_cache_registry.py](duckdb_cache_registry.py) | Registry identities |
| [dataframe_indexing.py](dataframe_indexing.py), [paths.py](paths.py) | Shared indexing/path helpers |
| [duckdb_reader.py](duckdb_reader.py), [parquet_housekeeping.py](parquet_housekeeping.py), [migrate_ohlcv.py](migrate_ohlcv.py) | Retained Parquet reader, housekeeping and migration utilities; not a competing new cache API |

## Contract

The generator accepts the configured boundary argument (normally `time_range_str`) and a `timeframe` argument, and returns a typed Pandera DataFrame model. Every dataset carries a timeframe index; the decorator requests all configured frequencies with `timeframe=None`. Results are assembled on `[timeframe, date]`, trimmed to the request and validated. Incomplete candles are dropped. `nan_means` controls whether cached NaN values count as missing data.

Read the actual decorator/helper code for boundary alignment and cache identity before changing persistence. Application roots/settings belong to `src/config/config.py`; do not create a second configuration path. In development mode, integrity checking can fetch data in a background thread and abort on mismatch; avoid enabling it during an unrelated inspection.

[Project task map](../../../docs/ARCHITECTURE.md) and [runbook](../../../RUNBOOK.md) provide navigation and validation commands. Archived designs do not activate migration work or override current code/contracts.
