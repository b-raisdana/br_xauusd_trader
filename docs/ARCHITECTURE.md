# Architecture and task map

## DDD boundaries

- **Domain** (`src/domain/xau_usd/strategy_v1/`) owns strategy configuration and deterministic, pandas-only market, signal-confirmation, risk-budget, sizing, session, and order-price calculations. It has no MT5, filesystem, account, or presentation dependency.
- **Application** (`src/application/strategy_v1/`) owns the versioned stage contracts, orchestration interfaces, and ports for artifact access. Each stage accepts one preceding artifact and returns one immutable result.
- **Infrastructure** (`src/infrastructure/`) implements MT5 market-data access, zone and account snapshots, native risk calculations, artifact persistence, broker execution, and execution-event ingestion. Adapters translate external schemas into application contracts; they do not decide signals or risk.
- **Presentation** (`src/presentation/`) exposes explicit replay or operational commands and calls application services. It contains no strategy calculations.

## SOA stage contracts

```text
StrategyContext → SignalStage → SignalResult → OrderStage → OrderResult → PositionStage → PositionResult
       ↑                                                                                         │
       └──────────────────── SnapshotIngress appends the next immutable input snapshot ─────────┘
```

Signal, order, and position services have separate versioned contracts and ownership. Signal owns market/setup decisions; order owns sizing, protection, budget gates, and pending LIMIT preparation; position owns fills, closes, realized outcomes, and retry state. A stage reads only references carried by its input contract. `SnapshotIngress` is the explicit boundary that attaches later market/account/execution events to the prior `PositionResult` before the next signal cycle.

Large frames cross service boundaries as immutable `ArtifactReference` values containing path, SHA-256, schema, index, columns, and row count. Domain functions operate on frames supplied by the application layer and emit only new result columns/artifacts. Runtime services may share one process; service boundaries and contracts do not imply separate deployments.

## Current implementation boundary

The v1 domain contains configuration validation, UTC closed-candle filtering, M15 trend, RSI/DEMA MACD confirmation, unique zone membership, net-loss budget calculations, cost stress estimation, volume sizing, DST-aware SL distance, and LIMIT/SL/TP price preparation. Application artifact contracts, stage protocols, the risk-calculation port, and an MT5 risk snapshot model are present. MT5 risk-calculation and data/zone/artifact adapters exist; concrete stage services, execution-event ingestion, and a presentation replay runner remain in `docs/todo/strategy-v1-implementation.md`.

## Integration points

- Existing MT5 market-data adapters: `src/infrastructure/mt5/tick.py` and `src/infrastructure/mt5/ohlcv.py`.
- Shared market schemas: `src/domain/schemas/tick.py` and `src/domain/schemas/common/ohlcv.py`.
- V1 domain calculations/config: `src/domain/xau_usd/strategy_v1/`.
- V1 application contracts/ports: `src/application/strategy_v1/`.
- MT5 account/symbol/profit/margin risk adapter: `src/infrastructure/strategy_v1/mt5_risk_calculator.py`.
- Strategy specification: [TradingStrategy.v1.0.md](TradingStrategy.v1.0.md) and its signal, order, and position documents.
- Repeatable data/runtime commands: [RUNBOOK.md](../RUNBOOK.md).
