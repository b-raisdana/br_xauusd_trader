# Architecture and task map

## Data and control flow

Python CLI → runner → daily `ResultFilesManifest` partitions → `VectorizedXauUsdStrategy` → `process_columns` signals/windows/state → optional `VectorizedExecutionReplay` → compiled `BatchReplay/ReplayKernel` → persisted execution collections → optional Vectorbt report.

State persists across chronological broker/symbol partitions. Three actual closed M15 bootstrap candles and unique covering native bars are required. Multiple events/orders/positions belong in collections; scalar snapshots cannot represent a complete ledger.

MT5 runs independently: EA callbacks delegate through the included release envelope to approved strategy handlers. Python simulated settlement, synthetic identities and callback assumptions require native trace comparison; source similarity is insufficient.

## Find the change

Paths are relative to `src/application/xauusd_trading_strategy_1_vector/` unless qualified.

| Task | Entry/owner | Validation scope under `tests/` |
| --- | --- | --- |
| CLI, acquisition | `__main__.py`, `runner.py`, `zone_loader.py` | `test_backtest_cli_option.py`, `test_mt5_input_validation.py` |
| Signals/trend/pullback windows | `the_strategy.py`, `columnar_process/`, `domain/columnar.py` | `test_native_columnar.py`, `test_vectorized_*.py` |
| Execution/risk/protection | `vectorized_replay.py` → `execution_batch/adapter.py` → `kernel.py` and sibling phases | `test_batch_execution_replay.py`, `test_vectorized_execution.py`, `test_oracle_scalar_replay.py` |
| Replay contracts/economics | `domain/replay.py`, `domain/execution_schema.py`, `config/` | `test_batch_schema_validation.py`, `test_vectorized_validation.py` |
| Shared schemas/zones | `src/domain/schemas/`, `src/domain/xau_usd/` | `test_datetime_schemas.py`, `test_mt5_zone_loader.py` |
| Persistence/manifest | `src/infrastructure/result_processing/io.py`, `src/infrastructure/datastore_engine/` | `test_result_manifest.py`, `test_vectorized_cache.py` |
| Report/provenance | `backtest.py`, `replay_portfolio.py`, `provenance.py`, `src/presentation/` | `test_replay_report_acceptance.py`, `test_backtest_import_isolation.py` |
| Native EA/envelope | `mt5/MQL5/Experts/` | Native compile/tester plus [acceptance work](todo/MT5-Python.Divergence.md) |

## Ownership and dependencies

- `src/config/config.py` owns application paths/settings (`DLF_` environment overrides); strategy `config/` owns bound calculation settings. `ReplayFileConfig` owns explicit file-input economics; MT5 inputs remain independent native settings.
- Shared Pandera models live in `src/domain/schemas/`; strategy-specific models live in its `domain/`. Use actual models rather than copying declarations.
- Application orchestration calls domain calculations and infrastructure I/O; `helper/` supplies shared date/import utilities. This map does not imply enforced dependency layering.
- New DataFrame cache-or-generate work uses `@duckdb_cache`; manifest output persistence is a separate concern. Inspect implementation and the task-specific skill before changing either.
- `replay.py`, `market.py` and test scalar coordinators retain reference/compatibility roles; production uses columnar signals and batch replay. Do not merge implementations without differential coverage.
- `pyproject.toml` owns packaging, dependencies, pytest, Ruff, mypy and hook settings; `.pre-commit-config.yaml` selects hooks. Hook implementation is the `br_pre_commit` submodule.

See [runbook](../RUNBOOK.md) for commands and [current state](CURRENT_STATE.md) for evidence and limitations.
