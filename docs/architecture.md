# Architecture

Responsibilities, dependency direction and state lifetimes. For current status
see [CURRENT_STATE.md](CURRENT_STATE.md); for commands see
[development.md](development.md).

## Dependency direction

```text
presentation  ->  application  ->  domain
                     |              ^
                     v              |
               infrastructure -----+
```

Intended direction is `presentation -> application -> domain`, with
`infrastructure` implementing ports the application needs and `domain` depending
on nothing internal. `config` and `helper` are cross-cutting leaves.

**Known violation:** `application` imports `infrastructure.result_processing`,
and that module imports `application...domain.schema`. This is bidirectional
package coupling. It is not a runtime circular import, because the cycle closes
at module level rather than at import time. Extracting the shared contracts into
a neutral module is tracked in `docs/CURRENT_STATE.md`.

Do not migrate wholesale to `src/xauusd/` or rename the strategy package without
a demonstrated benefit.

## Layers

| Package | Owns | Must not |
|---|---|---|
| `domain/` | Value objects, enums, constants, Pandera frame contracts, OHLCV and zone schemas | perform I/O, read configuration, import `application` |
| `application/xauusd_trading_strategy_1_vector/` | Ordered market-state transitions, replay configuration, recording/trace comparison, strategy-specific configuration | reach into broker APIs directly |
| `infrastructure/` | MT5 adapters, DuckDB/datastore engine, Parquet/result IO, Pandera dump support | own trading rules |
| `presentation/` | Typer CLIs, offline reports, synthetic data generators | contain business logic |
| `config/` | `BaseConfig`, context-bound config objects, `app_config` | be mutated implicitly from feature code |
| `helper/` | Shared imports, date/time utilities, enum and data-preparation utilities | hide business rules |

## Responsibility map

| Functionality | Implementation | Tests (tier) |
|---|---|---|
| Acquisition / orchestration | `__main__.py`, `runner.py`, `infrastructure/mt5/` | `test_mt5_input_validation` (unit) |
| Ordered transitions | `market.py`, `the_strategy.py` | `test_vectorized_pipeline`, `test_vectorized_state` (unit) |
| Execution / risk replay | `replay.py`, `domain/replay.py`, `domain/robust.py` | `test_vectorized_execution` (unit) |
| Recorded callbacks | `native_replay.py`, `recorded_runner.py`, `domain/recording.py`, `domain/native.py`, `trace.py` | `test_recorded_native_replay` (parity) |
| Native parity reference | `test_robust_mt5_parity.py` | (parity) |
| Zones | `zone_loader.py`, `zone_cache.py`, `domain/xau_usd/zone.py` | `test_mt5_zone_loader`, `test_vectorized_cache` (unit) |
| Frame contracts / schemas | strategy `domain/schema.py`, `domain/schemas/` | `test_datetime_schemas`, `test_vectorized_validation` (unit) |
| Artifacts / manifests | `infrastructure/result_processing/` | `test_result_manifest` (integration) |
| Optional reports | `backtest.py`, `reporting.py`, `presentation/vectorbt_backtest_report.py` | `test_backtest_signals` (unit), `test_backtest_import_isolation` (integration) |
| Datastore | `infrastructure/datastore_engine/` | coverage/ownership map still incomplete |
| Verification | `scripts/dev.py`, `scripts/check_docs_links.py`, `scripts/benchmark_tick_stages.py` | self-verifying |

`tests/vectorized_fixtures.py` and `tests/conftest.py` are shared test helpers,
not test modules. Import fixtures from them rather than from another test module,
so tier selection stays stable.

Legacy vector helpers retained for compatibility are a **compatibility
surface**, not the active path. Label new work against the active controller.

## Active controller path

```text
__main__.py  ->  runner.py  ->  VectorizedXauUsdStrategy.process_tick_data
                                        |
                                        +-> process_native_stream  (ordered transitions)
                                                |
                                                +-> MarketState.step  (causal transitions)
                                                +-> ExecutionReplay    (optional)
```

`MarketState` is created per broker/symbol and retained **across daily manifest
partitions**, so cross-day state survives a day boundary. `ExecutionReplay` is
optional; default mode is signals-only.

`process_tick_data` reads daily artifacts from a `ResultFilesManifest` and
persists validated per-tick and per-candle state. State artifacts are written
through a fire-and-forget executor and must not be concatenated in memory.

## State lifetimes

| State | Lifetime | Survives |
|---|---|---|
| `MarketState` | per broker/symbol, across days | day changes, new bars |
| Trend, previous Bid | per broker/symbol, across days | day and bar changes |
| Cycle / PB lifecycle | per active parent order | until a recognized fill |
| Execution replay | per broker/symbol | day changes |
| `Zones` / `ZoneCache` | whole run | all days |

Missing bars are never replayed. Sticky trend and previous Bid persist; current
candle extrema never enter their own reference.

## Artifact contracts

- Frames crossing a module boundary are Pandera-validated with
  `@pandera_validate`; index level names, dtypes and timestamp units are part of
  the contract.
- Rejection cases (empty, nullable, wrong dtype, wrong index order) are tested,
  not just the happy path.
- `.use()` context binding is how per-object configuration is activated. Do not
  mutate config objects implicitly.
- Manifests describe persisted artifacts and their partitions; state artifacts
  are large and are written, not accumulated.

## Evidence boundaries

Offline regression, recorded comparison, MQ5 compile and native runtime parity
are four distinct evidence classes. A passing Python suite is offline regression
only. The MT5 EA and its envelope are the reference definition; no compile has
been run, so no build or parity claim exists.

## Verification

`docs/development.md` owns commands and tiers. In short: everything runs through
`scripts/dev.py`, test classification lives in `tests/conftest.py`, and a tier
that selects zero tests fails rather than passing.