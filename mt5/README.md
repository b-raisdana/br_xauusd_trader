# XAUUSD MVP - MT5 Implementation

Research-only baseline for XAUUSD M15 trading. All logic is inert unless `InpEnableTesterExecution=true` inside Strategy Tester with valid Magic number.

## Architecture Overview

```
XAUUSD_MVP.mq5 (main entry)
├── Inputs (18 parameters)
├── Global State (50+ variables)
├── Runtime Structures (XauRuntimeRequest)
├── Core Pipeline Functions (25+)
├── Smoke Tests (11 validation suites)
└── Event Handlers (OnInit, OnTick, OnTradeTransaction, OnDeinit)
```

### Include Dependency Tree

```
XAUUSD_MVP.mq5
├── generated/CoreVectors.mqh          # Hard-coded test vectors
├── include/XauContracts.mqh           # Core domain logic (pure functions)
├── generated/DailyZones.mqh           # Pre-generated zone data per day
├── include/XauExecution.mqh           # Execution projection & bindings
├── include/XauAudit.mqh               # JSONL audit serialization
├── include/XauNative.mqh              # Read-only broker API boundary
├── include/XauState.mqh               # Trend/zone/pullback state machines
├── include/XauCoordinator.mqh         # Bar/tick coordination & signal emission
├── include/XauRequests.mqh            # Candidate → prepared entry pipeline
├── include/XauTesterBroker.mqh        # Tester-only order send/cancel/modify
├── include/XauTesterRisk.mqh          # Tester risk snapshots & PnL
└── include/XauVisual.mqh              # Chart rendering (output-only)
```

---

## Input Parameters (mt5/XAUUSD_MVP.mq5:18-26)

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `InpEnableTrading` | bool | false | Live trading gate (blocks init if true) |
| `InpEmitTimeBasisProbe` | bool | false | Emit 5 time-basis probes on tick |
| `InpObserveNativeOutcomes` | bool | false | Subscribe to OnTradeTransaction |
| `InpStrategyMagic` | long | 0 | Magic number for order/position filtering |
| `InpRunCurrentEventLoop` | bool | false | Enable main event loop in OnTick |
| `InpEnableTesterExecution` | bool | false | Enable Strategy Tester order execution |
| `InpStrategyCapital` | double | 200.0 | Capital base for risk budgeting |
| `InpSimulateSameDayRestart` | bool | false | Simulate same-day restart lock |

---

## Global State (mt5/XAUUSD_MVP.mq5:27-69)

### Execution Tracking
- `g_execution_projections[]` - Projected lifecycle per request
- `g_execution_bindings[]` - Request ↔ Order ↔ Position mapping
- `EXECUTION_BINDINGS_FILE` - Persistent TSV path
- `ORDER_AUDIT_FILE` - JSONL audit log path

### Market Coordinator
- `g_market_state` - `XauMarketCoordinator` (day/bar/trend/zones/pullbacks)
- `g_current_bar_time` - Current M15 bar timestamp

### Event Loop
- `g_event_loop_ready` - Initialization complete flag
- `g_event_loop_failure_reported` - Failure latch

### Counters
- `g_breakout_candidate_count`, `g_reversal_candidate_count`, `g_pullback_candidate_count`
- `g_tester_attempt_count`, `g_tester_accept_count`, `g_tester_reject_count`
- `g_request_sequence`, `g_event_sequence`

### Safety Locks
- `g_daily_loss_locked`, `g_operational_lock`, `g_restart_lock`
- `g_max_open_positions`, `g_session_zero_exposure`

### Rejection Tracking
- `g_gate_rejections[8]` - Per-rejection-type counts
- `g_invalid_price_rejections`, `g_other_broker_rejections`

### Protection Stats
- `g_protection_modifies`, `g_protection_modify_rejects`
- `g_sl_loosen_violations`, `g_tp_extensions`, `g_tp_restores`, `g_tp_market_closes`, `g_tp_modify_rejects`, `g_tp_close_rejects`
- `g_breakout_conflict_closes`

### Attribution
- `g_attribution_attempts[6]`, `g_attribution_accepts[6]`, `g_attribution_rejects[6]`
- Index mapping: BO_normal=0, BO_high=1, REV_normal=2, REV_high=3, PB_normal=4, PB_high=5

---

## Core Pipeline Functions

### 1. `NearlyEqual` (mt5/XAUUSD_MVP.mq5:82-85)
**Purpose**: Floating-point parity comparison using `PARITY_PRICE_TOLERANCE` (1e-9)
**Input**: `left: double`, `right: double`
**Output**: `bool` - true if |left-right| ≤ 1e-9
**Used by**: All smoke tests for vector parity validation

### 2. `EmitTesterSymbolSpecification` (mt5/XAUUSD_MVP.mq5:87-119)
**Purpose**: Log symbol specification once during tester execution
**Input**: `tick: MqlTick`
**Output**: `bool` - true if emitted or already emitted
**Side Effect**: Prints `TESTER_SYMBOL_SPEC` with digits, point, contract_size, tick_size, tick_value, stops_level, freeze_level, volume_min, volume_step, session_from, session_to

### 3. `InitializeCurrentEventLoop` (mt5/XAUUSD_MVP.mq5:610-659)
**Purpose**: Bootstrap coordinator state for a new day
**Input**: `tick: MqlTick`, `bar_time: datetime`
**Output**: `bool` - true if initialization succeeded
**Flow**:
1. Load raw zones for `broker_day` via `LoadGeneratedRawZones`
2. Build merged zones via `BuildMergedZones`
3. `BeginCoordinatorDay` with merged zones
4. Backfill trend candles from M15 history (day_start → bar_time-1)
5. `BeginCoordinatorBar` with current bar open
6. Reset daily locks and counters
**Calls**: `LoadGeneratedRawZones`, `BuildMergedZones`, `BeginCoordinatorDay`, `RecordTrendCandle`, `BeginCoordinatorBar`, `CopyRates`, `iTime`, `iOpen`

### 4. `ProcessCurrentEventLoopTick` (mt5/XAUUSD_MVP.mq5:1248-1335)
**Purpose**: Main per-tick processing pipeline
**Input**: `tick: MqlTick`
**Output**: `bool` - true if all stages succeeded
**Stages** (each can fail-fast with `CURRENT_EVENT_LOOP_STAGE_FAIL`):
1. **Symbol Spec** - `EmitTesterSymbolSpecification`
2. **Day Rollover** - Re-initialize if broker day changed
3. **Bar Rollover** - `CloseCoordinatorBar` → `BeginCoordinatorBar` on new M15 bar
4. **Operational Safety** - `ExecuteTesterOperationalSafety`
5. **Pullback TP Management** - `ManageTesterPullbackTp`
6. **Profit Protection** - `ManageTesterProfitProtection`
7. **Breakout Conflict Close** - `CloseTesterOppositeReversals`
8. **Breakout Candidates** - `ProcessTesterCandidates` (from bar close)
9. **Tick Candidates** - `ProcessCoordinatorTick` → `ProcessTesterCandidates`

### 5. `ProcessTesterCandidates` (mt5/XAUUSD_MVP.mq5:1121-1246)
**Purpose**: Evaluate candidates → risk checks → prepare entry → audit → submit → bind
**Input**: `tick: MqlTick`, `candidates: XauSignalCandidate[]`
**Output**: `bool` - true if all candidates processed
**Per-Candidate Flow**:
1. `CandidateAttemptAvailable` - bar/zone usage limits
2. `LoadTesterRiskSnapshot` - realized PnL, exposure, free margin
3. Update `g_max_open_positions`, `g_daily_loss_locked`
4. `InitialStop` / `InitialTarget` - zone-based SL/TP
5. `NativeCashRisk` / `NativeRequiredMargin` - broker risk measurement
6. `PrepareCandidateEntry` - full safety gate evaluation
7. If `XAU_ENTRY_ALLOWED`:
   - Generate `request_id` (REQ-N), `event_id` (DAY:E####)
   - `BuildPreparedOrderAudit` + `AppendOrderThenProject` (durable JSONL + projection)
   - `AppendRuntimeRequest` - track for TP/protection management
   - `SubmitTesterPreparedEntry` - OrderSend
   - `CommitPreparedEntryAttempt` - update zone usage
   - Attribution counters increment
   - On reject: project `XAU_EXECUTION_REJECT`, categorize retcode
   - On accept: `BindExecutionOrder` + persist bindings
   - Immediate fill: `LoadNativeDealTicketOutcome` → `ApplyProjectOwnedNativeOutcome`

### 6. `ExecuteTesterOperationalSafety` (mt5/XAUUSD_MVP.mq5:809-860)
**Purpose**: Session-end / restart flattening
**Input**: `tick: MqlTick`
**Output**: `bool`
**Conditions**: `InpEnableTesterExecution && !g_operational_lock && (SessionEndActive || g_restart_lock)`
**Actions**:
- `CancelTesterPendingOrders` → `ApplyTesterPendingCancellation` per ticket
- `CloseTesterPositions` → verify zero exposure via `LoadTesterRiskSnapshot`
- Lock `g_operational_lock=true`, `g_session_zero_exposure=true`

### 7. `ManageTesterPullbackTp` (mt5/XAUUSD_PAction-projectFolder/mt5/XAUUSD_MVP.mq5:888-1024)
**Purpose**: Pullback TP extension / restore / market close lifecycle
**Input**: `tick: MqlTick`
**Output**: `bool`
**Per-Position Flow** (pullback family only):
1. Resolve `request_id` via bindings (recover if needed via `RecoverTesterPositionBinding`)
2. Lazy TP state initialization via `InitializePullbackTp` if not `tp_initialized`
3. Load strict trend directions via `LoadPullbackStrictDirections` (M15 candles since pullback bar)
4. `StrictPullbackTrend` validation
5. **Pre-zone cross**: `PreZoneCrossOnce` → `ProposePullbackTpExtension` → `ModifyTesterProtection` → project outcome → `RecordPullbackTpExtension`
6. **Failure evaluation**: `EvaluatePullbackTpFailure` → `XAU_TP_RESTORE` (modify back) or `XAU_TP_MARKET_CLOSE` (close position)
7. On close: `CloseTesterPosition` → load deal → `ApplyProjectOwnedNativeOutcome`

### 8. `ManageTesterProfitProtection` (mt5/XAUUSD_MVP.mq5:1066-1119)
**Purpose**: Trailing stop at R-multiples (profit protection)
**Input**: `tick: MqlTick`
**Output**: `bool`
**Per-Position Flow**:
1. Resolve `request_id` via bindings (recover if needed)
2. `TesterPositionRiskFree` - compute risk-free price including native costs
3. `ProfitProtectionStop` - calculate proposed stop at (step-1)*R from risk-free
4. `ProtectionModificationValid` - validate no SL loosening
5. `ModifyTesterProtection` → project outcome
6. Track `g_protection_modifies` / `g_protection_modify_rejects` / `g_sl_loosen_violations`

### 9. `CloseTesterOppositeReversals` (mt5/XAUUSD_MVP.mq5:1026-1064)
**Purpose**: Close reversal positions conflicting with new breakout direction
**Input**: `tick: MqlTick`, `breakouts: XauSignalCandidate[]`
**Output**: `bool`
**Logic**: For each breakout, find reversal positions in same zone with opposite direction → close via `CloseTesterPosition` → track `g_breakout_conflict_closes`

### 10. `ApplyProjectOwnedNativeOutcome` (mt5/XAUUSD_MVP.mq5:691-756)
**Purpose**: Process native deal → persist bindings → project execution state
**Input**: `outcome: XauNativeDealOutcome`
**Output**: `bool`
**Flow**:
1. `ResolveExecutionRequest` - find request_id from bindings
2. Idempotency check - skip if projection already at target status
3. `PersistThenPublishCorrelatedNativeOutcome` - atomic bind persist + projection update
4. On FILL for pullback: initialize TP state, record pullback fill in coordinator

### 11. `RecoverTesterPositionBinding` (mt5/XAUUSD_MVP.mq5:758-779)
**Purpose**: Recover order→position binding from history deals
**Input**: `position_id: ulong`, `broker_now: datetime`
**Output**: `bool` - true if binding recovered
**Logic**: `HistorySelect(0, broker_now)` → find DEAL_ENTRY_IN for position_id with matching magic → `BindExecutionPosition` + persist

### 12. `ApplyTesterPendingCancellation` (mt5/XAUUSD_MVP.mq5:781-807)
**Purpose**: Project cancellation for a pending order
**Input**: `order_ticket: ulong`, `broker_time: datetime`
**Output**: `bool`
**Logic**: Resolve request → project `XAU_EXECUTION_CANCEL` → if pullback, `RecordPullbackPendingRemoved`

### 13. `LoadPullbackStrictDirections` (mt5/XAUUSD_MVP.mq5:862-880)
**Purpose**: Load closed M15 candle directions since pullback bar
**Input**: `runtime: XauRuntimeRequest`, `directions: int&[]` (output)
**Output**: `bool`
**Logic**: CopyRates from pullback_bar+15min to current_bar-1 → direction = sign(close-open)

### 14. `AdjacentTargetZoneIndex` (mt5/XAUUSD_MVP.mq5:882-886)
**Purpose**: Find next zone in direction of trade
**Input**: `current_index: int`, `direction: XauDirection`
**Output**: `int` - next zone index or -1

---

## Smoke Test Functions (OnInit Validation)

All smoke tests run in `OnInit` and return `bool`. Failure → `INIT_FAILED`.

| Function | Validates |
|----------|-----------|
| `RunCoreVectorSmoke` | All 19 core contract vectors (breakout, reversal, trend, pullback, risk, merge, gap, window, TP, restart, execution, causal, protection) |
| `RunExecutionProjectorSmoke` | Execution projection lifecycle, bindings persist/load, native correlation |
| `RunGuardedNativeCallbackSmoke` | Persist-then-publish native outcome correlation |
| `RunStateOrderingSmoke` | Trend reference, bar-close breakout, daily zones, pullback window, TP extension/restore |
| `RunCoordinatorSmoke` | Day/bar/tick coordination, trend, engagement, signals, pullback creation |
| `RunSafetyRequestSmoke` | Portfolio, concurrency, margin, daily loss, operational safety |
| `RunPreparedRequestSmoke` | Space/risk/safety/audit/attempt pipeline |
| `RunAuditRequestSmoke` | Durable audit before state projection |
| `RunNativeAdapterSmoke` | Symbol/session/risk/margin/deal mapping (read-only) |
| `RunVisualPayloadSmoke` | Marker tooltip rendering |

---

## Event Handlers

### `OnInit` (mt5/XAUUSD_MVP.mq5:1337-1387)
**Purpose**: Validate configuration, run all smoke tests, initialize
**Returns**: `INIT_SUCCEEDED` or `INIT_FAILED`
**Gates**:
- Blocks if `InpEnableTrading=true` (live not implemented)
- Requires `InpStrategyMagic>0` for native observation/tester execution
- Requires `MQL_TESTER` for tester execution
- Runs 11 smoke tests sequentially

### `OnTick` (mt5/XAUUSD_MVP.mq5:1403-1428)
**Purpose**: Main entry point per tick
**Flow**:
1. Time basis probe (if enabled)
2. If `InpRunCurrentEventLoop`: `SymbolInfoTick` → `ProcessCurrentEventLoopTick`
3. Failure latch prevents log spam

### `OnTradeTransaction` (mt5/XAUUSD_MVP.mq5:1389-1401)
**Purpose**: Observe native deals for correlation (opt-in)
**Input**: `transaction`, `request`, `result`
**Flow**: If `InpObserveNativeOutcomes` → `LoadNativeDealOutcome` → `ApplyProjectOwnedNativeOutcome`

### `OnDeinit` (mt5/XAUUSD_MVP.mq5:1430-1476)
**Purpose**: Print final statistics
**Output**: Comprehensive counters for event loop, tester risk, TP, breakout, attribution

---

## Data Flow Summary

```
Tick (OnTick)
    ↓
ProcessCurrentEventLoopTick
    ├── Day/Bars → Coordinator (XauCoordinator.mqh)
    │   ├── Trend reference (XauState.mqh)
    │   ├── Zone engagement (XauState.mqh)
    │   ├── Reversal signals (Contracts: ReversalDirectionalTouch)
    │   ├── Pullback evaluation (XauState.mqh: EvaluatePullbackPrice)
    │   └── Breakout on bar close (Contracts: BreakoutValid)
    │
    ├── Operational Safety (Contracts: EvaluateOperationalSafety)
    ├── Pullback TP Management (XauState.mqh + Contracts)
    ├── Profit Protection (Contracts: ProfitProtectionStop)
    ├── Breakout Conflict Close
    │
    └── Candidate Processing (XauRequests.mqh)
        ├── Attempt availability (bar/zone limits)
        ├── Risk snapshot (XauTesterRisk.mqh)
        ├── SL/TP from zones (Contracts: InitialStop/InitialTarget)
        ├── Native risk/margin (XauNative.mqh)
        ├── Safety gate (Contracts: EvaluateProtectedEntry)
        ├── Audit persistence (XauAudit.mqh)
        ├── Execution projection (XauExecution.mqh)
        ├── Tester submission (XauTesterBroker.mqh)
        └── Binding persist (XauExecution.mqh)
```

---

## File Cross-References

- **Core Contracts**: [mt5/include/XauContracts.mqh](../include/XauContracts.mqh) → [mt5/include/README.md#xaucontractsmqh](../include/README.md#xaucontractsmqh)
- **Execution Projection**: [mt5/include/XauExecution.mqh](../include/XauExecution.mqh) → [mt5/include/README.md#xauexecutionmqh](../include/README.md#xauexecutionmqh)
- **Audit/JSONL**: [mt5/include/XauAudit.mqh](../include/XauAudit.mqh) → [mt5/include/README.md#xauauditmqh](../include/README.md#xauauditmqh)
- **Native Adapter**: [mt5/include/XauNative.mqh](../include/XauNative.mqh) → [mt5/include/README.md#xaunativemqh](../include/README.md#xaunativemqh)
- **State Machines**: [mt5/include/XauState.mqh](../include/XauState.mqh) → [mt5/include/README.md#xaustatemqh](../include/README.md#xaustatemqh)
- **Coordinator**: [mt5/include/XauCoordinator.mqh](../include/XauCoordinator.mqh) → [mt5/include/README.md#xaucoordinatormqh](../include/README.md#xaucoordinatormqh)
- **Request Pipeline**: [mt5/include/XauRequests.mqh](../include/XauRequests.mqh) → [mt5/include/README.md#xaurequestsmqh](../include/README.md#xaurequestsmqh)
- **Tester Broker**: [mt5/include/XauTesterBroker.mqh](../include/XauTesterBroker.mqh) → [mt5/include/README.md#xautesterbrokermqh](../include/README.md#xautesterbrokermqh)
- **Tester Risk**: [mt5/include/XauTesterRisk.mqh](../include/XauTesterRisk.mqh) → [mt5/include/README.md#xautesterriskmqh](../include/README.md#xautesterriskmqh)
- **Visual**: [mt5/include/XauVisual.mqh](../include/XauVisual.mqh) → [mt5/include/README.md#xauvisualmqh](../include/README.md#xauvisualmqh)
- **Generated Vectors**: [mt5/generated/CoreVectors.mqh](../generated/CoreVectors.mqh)
- **Generated Zones**: [mt5/generated/DailyZones.mqh](../generated/DailyZones.mqh)
