# MQL5 ↔ Python Mapping — Findings

## 1. Objective

Map the full MQL5 lifecycle in `src/mt5/XAUUSD_MVP.mq5` and its `include/` + `generated/` headers to the current Python domain package `src/xauusd/`, identify parity gaps, and determine what remains to be done under `docs/todo/todo-MetaTrader-independence.md`.

## 2. Scope of MQL5 Baseline (current)

### 2.1 EA entry point: `src/mt5/XAUUSD_MVP.mq5` (1,477 lines)

Hard-disabled outside Strategy Tester (`/MT5` lock in `XauTesterBroker.mqh`). Input params:

| Input | Default | Purpose |
|---|---|---|
| `InpEnableTrading` | `false` | Trading gate |
| `InpEmitTimeBasisProbe` | `false` | Server-time/Bid probe for UTC offset correlation |
| `InpObserveNativeOutcomes` | `false` | Opt-in `OnTradeTransaction` Native outcome processing |
| `InpStrategyMagic` | `0` | Magic number filter |
| `InpRunCurrentEventLoop` | `false` | Inert event loop consumer |
| `InpEnableTesterExecution` | `false` | Tester-only execution gate |
| `InpStrategyCapital` | `200.0` | Capital basis for risk limits |
| `InpSimulateSameDayRestart` | `false` | Restart fail-closed simulation |

### 2.2 Include modules (10 files, 2,532 lines total)

| File | Lines | Key Contracts |
|---|---|---|
| `XauContracts.mqh` | 487 | Constants, enums, pure math: `BuildMergedZones`, `CountDirectionalCrosses`, `BreakoutValid`, `ReversalDirectionalTouch`, `InitialStop`, `InitialTarget`, `PortfolioRiskAllows`, `MaximumPositions`, `ConcurrencyAllowsEntry`, `EvaluateProtectedEntry`, `EvaluateOperationalSafety`, `ProfitProtectionStop`, `DailyLossLocked`, `SessionEndActive`, `PullbackTpFailureAction`, `RestartSameDayLocked`, `ExecutionTransition`, `ProtectionModificationValid` |
| `XauState.mqh` | 371 | `XauMarketCoordinator`, `XauTrendReferenceState`, `XauDailyZoneSignalState`, `XauPullbackWindowState`, `BeginCoordinatorDay/Bar`, `ProcessCoordinatorTick`, `CloseCoordinatorBar`, `BeginTrendDay`, `RecordTrendCandle`, `ProcessTrendTick`, `CloseBarBreakoutBeforeRoll`, `InitializeDailyZoneStates`, `BeginSignalBar`, `UpdateZoneEngagement`, `NextBreakoutId`, `ConsumeReversalUsage`, `RecordEntryAttempt`, `CreatePullbackWindow`, `BeginPullbackBar`, `EvaluatePullbackPrice`, `RecordPullbackAttempt`, `RecordPullbackFill`, `RecordPullbackPendingRemoved`, `PreZoneCrossOnce`, `InitializePullbackTp`, `ProposePullbackTpExtension`, `RecordPullbackTpExtension`, `EvaluatePullbackTpFailure`, `RecordPullbackTpRestore` |
| `XauCoordinator.mqh` | 223 | Day/bar/tick orchestration, signal emission, `XauSignalCandidate` definition |
| `XauExecution.mqh` | 330 | `XauExecutionProjection`, `XauExecutionBinding`, binding persistence (`SaveExecutionBindingsAtomically`, `LoadExecutionBindings`, `SameExecutionBindings`), `InitializeExecutionProjection`, `ProjectExecutionOutcome`, `BindExecutionOrder`, `BindExecutionPosition`, `ResolveExecutionRequest`, `ProjectCorrelatedNativeOutcome`, `PersistThenPublishCorrelatedNativeOutcome` |
| `XauNative.mqh` | 179 | Native adapter: `LoadNativeSymbol`, `LoadNativeDealOutcome`, `ClassifyNativeDealEntry`, `NativeCashRisk`, `NativeRequiredMargin`, `NativeContainingTradeSession` |
| `XauRequests.mqh` | 144 | `PrepareCandidateEntry`, `BuildPreparedOrderAudit`, `CommitPreparedEntryAttempt` |
| `XauTesterBroker.mqh` | 208 | Tester-only broker: `TesterExecutionAllowed`, `SubmitTesterPreparedEntry`, `CancelTesterPendingOrders`, `CloseTesterPositions`, `ModifyTesterProtection`, `LoadTesterRiskSnapshot`, `TesterPositionRiskFree` |
| `XauTesterRisk.mqh` | 170 | Tester deal-position grouping, native cash risk aggregation |
| `XauAudit.mqh` | 80 | `AppendOrderThenProject`, durable JSONL audit before projection |
| `XauVisual.mqh` | 74 | Visual markers (render-only, no trading) |

### 2.3 Generated files (2 files, 657 lines)

| File | Lines | Source |
|---|---|---|
| `generated/CoreVectors.mqh` | 87 | Generated from `tests/vectors/core_contracts.json` by `scripts/generate_mql_vectors.py` — 19 parity constants |
| `generated/DailyZones.mqh` | 570 | Generated from `data/ranges.csv` by `scripts/generate_mql_zones.py` — 23 Broker Days, 444 source rows |

## 3. Python Contracts (current)

`src/xauusd/` implements deterministic equivalents:

| Python Module | Key Contracts | MQL5 Parity |
|---|---|---|
| `xauusd.zones` | `Zone`, `RawZone`, `ZonePriority`, `build_daily_zones`, `load_zone_csv`, `price`, `ZoneEngagementTracker` | `XauZone`, `BuildMergedZones`, `LoadGeneratedRawZones`, `UpdateZoneEngagement`, `ZoneLineAllowed`, `ZoneMerge` |
| `xauusd.trend` | `Candle`, `CandleDirection`, `TrendState`, `DailyTrendTracker` | `XauTrendReferenceState`, `BeginTrendDay`, `RecordTrendCandle`, `ProcessTrendTick`, `UpdateTrend` |
| `xauusd.signals` | `BreakoutTracker`, `ReversalTracker`, `TradeDirection`, `OrderType`, `SignalFamily`, `OrderAttemptLedger` | `XauSignalCandidate`, `BreakoutValid`, `ReversalDirectionalTouch`, daily usage/duplicate guards |
| `xauusd.pullback` | `PullbackTracker`, `PullbackOrderCandidate`, `PullbackTpState`, `PullbackExpiry` | `XauPullbackWindowState`, `CreatePullbackWindow`, `BeginPullbackBar`, `EvaluatePullbackPrice`, `RecordPullbackFill` |
| `xauusd.momentum` | `PreZoneTriggerTracker`, `TpAction`, `blocks_opposite_reversal`, `pre_zone_trigger_price`, `strict_pullback_trend` | `PreZoneCrossOnce`, `ProposePullbackTpExtension`, `EvaluatePullbackTpFailure`, `BlocksOppositeReversal` |
| `xauusd.risk` | `InitialRisk`, `build_initial_risk`, `initial_stop`, `initial_target`, `profit_protection_stop`, `risk_free_price`, `concurrency_allows_entry`, `native_margin_allows_entry`, `BASE_R_USD`, `MINIMUM_FREE_SPACE_USD`, `FIXED_VOLUME_LOTS` | `InitialStop`, `InitialTarget`, `ProfitProtectionStop`, `ConcurrencyAllowsEntry`, `NativeMarginAllowsEntry`, `MaximumPositions` |
| `xauusd.safety` | `DailyRealizedLossGuard`, `PortfolioRiskSnapshot`, `DailyGuardState`, `OperationalSafetyActions`, `evaluate_portfolio_risk`, `evaluate_entry_safety`, `session_end_actions`, `RestartFailClosedGuard` | `DailyLossLocked`, `PortfolioRiskAllows`, `EvaluateProtectedEntry`, `EvaluateOperationalSafety`, `SessionEndActive`, `RestartSameDayLocked` |
| `xauusd.execution` | `ExecutionLedger`, `ExecutionRecord`, `ExecutionRequest`, `ExecutionStatus`, `execution_transition`, `protection_modification_valid` | `ExecutionTransition`, `ProtectionModificationValid`, `XauExecutionProjection` state machine |
| `xauusd.audit` | `AuditJournal`, `AuditEvent`, `AuditEventKind`, `JsonlAuditStore`, `ChartMarker` | `AppendOrderThenProject`, durable audit before projection |
| `xauusd.market_state` | `MarketState`, `MarketBarCloseUpdate`, `MarketTickUpdate` | `XauMarketCoordinator` state |
| `xauusd.replay` | `ReplayRunner`, `ReplayDay`, `ReplayBar`, `ReplayTick`, `build_replay_days` | Inert event loop consumer |
| `xauusd.orchestration` | `MarketAuditProjector` | `RunCoreVectorSmoke` / `RunCoordinatorSmoke` smoke tests |

## 4. Scripts Bridging Python ↔ MQL5

| Script | Purpose | MT5 Dependency |
|---|---|---|
| `scripts/export_mt5_ticks.py` | Export read-only MT5 UTC ticks → `data/cache/` CSV | `import MetaTrader5`, requires terminal binary |
| `scripts/match_mt5_time_basis.py` | Fail-closed UTC offset correlation (5-tick ordered probe) | `import MetaTrader5`, requires terminal binary |
| `scripts/generate_mql_vectors.py` | Render `CoreVectors.mqh` from `tests/vectors/core_contracts.json` | None (generator) |
| `scripts/generate_mql_zones.py` | Render `DailyZones.mqh` from `data/ranges.csv` | None (generator) |
| `scripts/compare_signal_parity.py` | Python replay signal count vs MQL event-loop summary | Uses `load_mt5_tick_bars` + `build_replay_days` + `ReplayRunner` |
| `scripts/presentations.py` | Report generation using `load_mt5_tick_bars` | Uses `load_mt5_tick_bars` |

## 5. Config Files

| Config | Live Trading | Tester Execution | Time Basis Probe | Observe Native | Capital |
|---|---|---|---|---|---|
| `contract_smoke.ini` | Off | Off | On | Off | 200 |
| `tester_200.ini` | Off | On | Off | On | 200 |
| `tester_300.ini` | Off | On | Off | On | 300 |
| `tester_multiday_200.ini` | Off | On | Off | Off | 200 |
| `tester_restart.ini` | Off | Off | Off | Off | 200 |
| `tester_qa_20260729.ini` | Off | On | Off | Off | 200 |

## 6. Tests Referencing MQL5 / MT5

| Test File | Scope |
|---|---|
| `tests/test_mt5_tick_export.py` | `utc_datetime` + `cache_output` argument validation |
| `tests/test_mt5_time_basis.py` | `server_to_utc` offset math, `contains_bid_sequence` |
| `tests/test_mt5_source.py` | Source-string assertions on all `.mq5`/`.mqh` includes (448 lines, 25 test functions) |
| `tests/test_mql_zone_generation.py` | `render()` output matches `generated/DailyZones.mqh` byte-for-byte |
| `tests/test_equivalence_vectors.py` | 19 canonical vectors exercise Python contracts; header drift gate |
| `tests/test_signal_parity_script.py` | `compare_signal_parity.py` imports + family coverage |
| `tests/test_tick_data.py` | `load_mt5_tick_bars` normalization, backward-time rejection, offset validation |
| `tests/test_final_report.py` | `FINAL_TEST_EVIDENCE.json` structure and content validation |

## 7. Parity Status

### 7.1 Verified Parity (Python ↔ MQL5)

- **Zone merge + classification**: `XauContracts.mqh:BuildMergedZones` ↔ `xauusd.zones.build_daily_zones` — tested via `test_equivalence_vectors.py` (zone-chain-merge vector) and `tests/test_zones.py` (444 rows → 23 days, 421 merged zones).
- **Strict pullback trend**: `XauContracts.mqh:StrictPullbackTrend` ↔ `xauusd.momentum.strict_pullback_trend` — tested via strict-buy-momentum vector.
- **Pre-zone trigger**: `XauContracts.mqh:PreZoneCrossed` ↔ `xauusd.momentum.pre_zone_trigger_price` — tested via pre-zone-buy-gap-cross vector.
- **Profit protection stop**: `XauContracts.mqh:ProfitProtectionStop` ↔ `xauusd.risk.profit_protection_stop` — tested via profit-protection-buy-step-four vector.
- **Execution transition**: `XauContracts.mqh:ExecutionTransition` ↔ `xauusd.execution.execution_transition` — tested via execution-cancel-reject-preserves-pending vector.
- **Protection modification validation**: `XauContracts.mqh:ProtectionModificationValid` ↔ `xauusd.execution.protection_modification_valid` — tested via modify-buy-no-sl-loosen vector.
- **Portfolio risk**: `XauContracts.mqh:PortfolioRiskAllows` ↔ `xauusd.safety.evaluate_portfolio_risk` — tested via gross15-inclusive-boundary vector.
- **Daily loss guard**: `XauContracts.mqh:DailyLossLocked` ↔ `xauusd.safety.DailyRealizedLossGuard` — tested via daily-loss-inclusive-boundary vector.
- **Session end**: `XauContracts.mqh:SessionEndActive` ↔ `xauusd.safety.session_end_actions` — tested via session-five-minute-boundary vector.
- **Restart fail-closed**: `XauContracts.mqh:RestartSameDayLocked` ↔ `xauusd.safety.RestartFailClosedGuard` — tested via restart-same-day-lock vector.
- **Pullback window / usage**: `XauContracts.mqh:PullbackWindowActive` + `PullbackUsageAllowed` ↔ `xauusd.pullback.pullback_window_active` + `pullback_usage_allowed` — tested via pullback-high-window-t5 vector.
- **Pullback TP failure action**: `XauContracts.mqh:PullbackTpFailureAction` ↔ `xauusd.momentum.PullbackTpState.evaluate_strict_failure` — tested via tp-strict-failure-before-initial vector.
- **Maximum positions / concurrency**: `XauContracts.mqh:MaximumPositions` + `ConcurrencyAllowsEntry` ↔ `xauusd.risk.maximum_positions` — tested via capital-limits boundary tests.
- **Native margin**: `XauContracts.mqh:NativeMarginAllowsEntry` ↔ `xauusd.risk.native_margin_allows_entry` — tested via margin boundary tests.
- **Directional free space**: `XauContracts.mqh:DirectionalFreeSpace` ↔ `xauusd.risk.directional_free_space` — tested via free-space boundary tests.
- **Causal trend then reversal**: `XauContracts.mqh:CausalTrendThenReversal` ↔ `xauusd.trend.DailyTrendTracker.update` + `xauusd.signals.ReversalTracker.detect` — tested via causal-trend-before-reversal vector.

### 7.2 MQL5-Only (No Python Equivalent)

These contracts exist in MQL5 includes but have **no direct Python counterpart** in `src/xauusd/`. They are either tester-specific execution glue or lifecycle orchestration not yet extracted:

| MQL5 Function | File | Description |
|---|---|---|
| `InitializeExecutionProjection` | `XauExecution.mqh` | Projection state initialization |
| `ProjectExecutionOutcome` | `XauExecution.mqh` | State machine outcome projection |
| `BindExecutionOrder` | `XauExecution.mqh` | Ticket-to-request binding |
| `BindExecutionPosition` | `XauExecution.mqh` | Position-ID-to-request binding |
| `ResolveExecutionRequest` | `XauExecution.mqh` | Request lookup by event/ticket |
| `FindExecutionProjection` | `XauExecution.mqh` | Projection lookup |
| `ProjectCorrelatedNativeOutcome` | `XauExecution.mqh` | Native deal outcome → projection correlation |
| `PersistThenPublishCorrelatedNativeOutcome` | `XauExecution.mqh` | Atomic persist-before-publish |
| `SaveExecutionBindingsAtomically` | `XauExecution.mqh` | Atomic TSV file write |
| `LoadExecutionBindings` | `XauExecution.mqh` | TSV file load |
| `SameExecutionBindings` | `XauExecution.mqh` | Binding equality check |
| `InitializeExecutionProjection` (native) | `XauExecution.mqh` | Native projection init |
| `TesterExecutionAllowed` | `XauTesterBroker.mqh` | Tester-only execution gate |
| `SubmitTesterPreparedEntry` | `XauTesterBroker.mqh` | Tester order send |
| `CancelTesterPendingOrders` | `XauTesterBroker.mqh` | Tester pending cancellation |
| `CloseTesterPositions` | `XauTesterBroker.mqh` | Tester position close |
| `ModifyTesterProtection` | `XauTesterBroker.mqh` | Tester SL/TP modify |
| `LoadTesterRiskSnapshot` | `XauTesterBroker.mqh` | Tester risk snapshot load |
| `TesterPositionRiskFree` | `XauTesterBroker.mqh` | Tester risk-free price |
| `LoadNativeSymbol` | `XauNative.mqh` | Symbol specification loader |
| `LoadNativeDealOutcome` | `XauNative.mqh` | Native deal classification |
| `ClassifyNativeDealEntry` | `XauNative.mqh` | Deal entry type classification |
| `NativeCashRisk` | `XauNative.mqh` | Native cash risk from OrderCalcProfit |
| `NativeRequiredMargin` | `XauNative.mqh` | Native margin from OrderCalcMargin |
| `NativeContainingTradeSession` | `XauNative.mqh` | Session bounds from SymbolInfoSessionTrade |
| `PrepareCandidateEntry` | `XauRequests.mqh` | Full entry preparation with risk/safety/audit |
| `BuildPreparedOrderAudit` | `XauRequests.mqh` | Audit event builder |
| `CommitPreparedEntryAttempt` | `XauRequests.mqh` | Coordinator entry attempt commit |
| `BeginCoordinatorDay` | `XauCoordinator.mqh` | Day-level coordinator init |
| `BeginCoordinatorBar` | `XauCoordinator.mqh` | Bar-level coordinator init |
| `ProcessCoordinatorTick` | `XauCoordinator.mqh` | Tick-level coordinator process |
| `CloseCoordinatorBar` | `XauCoordinator.mqh` | Bar-level coordinator close |
| `BeginTrendDay` | `XauState.mqh` | Trend day init |
| `RecordTrendCandle` | `XauState.mqh` | Trend candle recording |
| `ProcessTrendTick` | `XauState.mqh` | Trend tick processing |
| `CloseBarBreakoutBeforeRoll` | `XauState.mqh` | Bar-close breakout before trend roll |
| `InitializeDailyZoneStates` | `XauState.mqh` | Daily zone signal state init |
| `BeginSignalBar` | `XauState.mqh` | Signal bar init |
| `UpdateZoneEngagement` | `XauState.mqh` | Zone engagement update |
| `NextBreakoutId` | `XauState.mqh` | Breakout ID generator |
| `ConsumeReversalUsage` | `XauState.mqh` | Reversal usage consumption |
| `RecordEntryAttempt` | `XauState.mqh` | Entry attempt ledger |
| `CreatePullbackWindow` | `XauState.mqh` | Pullback window creation |
| `BeginPullbackBar` | `XauState.mqh` | Pullback bar init |
| `EvaluatePullbackPrice` | `XauState.mqh` | Pullback price evaluation |
| `RecordPullbackAttempt` | `XauState.mqh` | Pullback attempt recording |
| `RecordPullbackFill` | `XauState.mqh` | Pullback fill recording |
| `RecordPullbackPendingRemoved` | `XauState.mqh` | Pullback pending removal |
| `PreZoneCrossOnce` | `XauState.mqh` | One-time pre-zone trigger |
| `InitializePullbackTp` | `XauState.mqh` | TP state initialization |
| `ProposePullbackTpExtension` | `XauState.mqh` | TP extension proposal |
| `RecordPullbackTpExtension` | `XauState.mqh` | TP extension recording |
| `EvaluatePullbackTpFailure` | `XauState.mqh` | TP failure action evaluation |
| `RecordPullbackTpRestore` | `XauState.mqh` | TP restore recording |

Note: Many of the `XauState.mqh` and `XauCoordinator.mqh` functions have Python equivalents in `market_state.py`, `signals.py`, `pullback.py`, `momentum.py` — but the mapping is not 1:1. Python uses class-based trackers (`BreakoutTracker`, `ReversalTracker`, `PullbackTracker`, `DailyTrendTracker`) whereas MQL5 uses struct-based state with free functions.

## 8. Key Differences: MQL5 vs Python

### 8.1 Decimal Precision

- **MQL5**: `double` (64-bit IEEE 754), tolerance `1e-9` (`PARITY_PRICE_TOLERANCE`)
- **Python**: `Decimal` (arbitrary precision), `price()` helper for string conversion
- **Parity test**: `test_equivalence_vectors.py` loads vectors as `Decimal` strings

### 8.2 State Management

- **MQL5**: Global struct state (`g_market_state`, `g_execution_bindings`, `g_runtime_requests`)
- **Python**: Instance-based state via tracker classes (`MarketState`, `BreakoutTracker`, etc.)

### 8.3 Execution Model

- **MQL5**: Tester-only `OrderSend` in `XauTesterBroker.mqh`; full Native adapter in `XauNative.mqh`
- **Python**: No execution — `ReplayRunner` simulates outcomes via injected tick events

### 8.4 File Persistence

- **MQL5**: Atomic TSV binding files (`SaveExecutionBindingsAtomically`), JSONL audit (`AppendOrderThenProject`)
- **Python**: JSONL audit via `JsonlAuditStore`, no binding file persistence

## 9. Open Gaps for MetaTrader Independence

1. **`load_mt5_tick_bars`** in `src/xauusd/tick_data.py:96` — imports MT5-normalized CSV; replacement must use broker-agnostic tick source
2. **`scripts/export_mt5_ticks.py`** + **`scripts/match_mt5_time_basis.py`** — live MT5 terminal dependency
3. **`tests/test_mt5_*.py`** files — 4 test files referencing MT5 sources
4. **`tests/test_signal_parity_script.py`** — references `load_mt5_tick_bars` import
5. **`scripts/presentations.py`** — uses `load_mt5_tick_bars`
6. **`src/mt5/`** entire directory (3,223 lines across 12 files) — to be removed per TODO
7. **`config/mt5/`** directory (347 lines across 6 INI files) — to be removed per TODO
8. **MQL5-only execution contracts** listed in §7.2 — no Python equivalent yet
