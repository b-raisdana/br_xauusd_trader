# MT5 Include Files Documentation

This directory contains the modular include files for the XAUUSD MVP. Each file has a single responsibility and zero circular dependencies.

## File Index

| File | Purpose | Lines | Key Exports |
|------|---------|-------|-------------|
| [XauContracts.mqh](#xaucontractsmqh) | Core domain logic (pure functions) | 487 | Enums, zones, validation, risk, safety, execution transitions |
| [XauExecution.mqh](#xauexecutionmqh) | Execution projection & bindings persistence | 330 | Projection struct, binding struct, TSV persist/load, lifecycle projection |
| [XauAudit.mqh](#xauauditmqh) | JSONL audit serialization | 80 | Audit event struct, serialization, append-only file write |
| [XauNative.mqh](#xaunativemqh) | Read-only broker API boundary | 179 | Symbol spec, deal classification, cash risk, margin, trade sessions |
| [XauState.mqh](#xaustatemqh) | Trend/zone/pullback state machines | 371 | Trend reference, daily zones, pullback window, TP state |
| [XauCoordinator.mqh](#xaucoordinatormqh) | Bar/tick coordination & signal emission | 223 | Market coordinator, signal candidates, bar lifecycle |
| [XauRequests.mqh](#xaurequestsmqh) | Candidate → prepared entry pipeline | 144 | Prepared entry, attempt availability, audit build, commit |
| [XauTesterBroker.mqh](#xautesterbrokermqh) | Tester-only order operations | 208 | Submit, cancel, close, modify (OrderSend wrappers) |
| [XauTesterRisk.mqh](#xautesterriskmqh) | Tester risk snapshots & PnL | 170 | Realized risk, exposure risk, risk-free price |
| [XauVisual.mqh](#xauvisualmqh) | Chart rendering (output-only) | 74 | Zone rectangles, audit markers, tooltips |

---

## XauContracts.mqh {#xaucontractsmqh}

**Location**: `mt5/include/XauContracts.mqh`

Pure domain logic with no I/O, no MT5 API calls, no state mutation. All functions are deterministic and testable via vectors.

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `BASE_R_USD` | 6.0 | Base risk unit in USD |
| `BREAKOUT_BUFFER_USD` | 1.0 | Minimum close-beyond-zone for breakout |
| `GROSS_DAILY_RISK_FRACTION` | 0.15 | Max gross risk as fraction of capital |
| `PULLBACK_PENETRATION_USD` | 0.20 | Penetration depth for pullback entry |
| `PRE_ZONE_TRIGGER_DISTANCE_USD` | 1.0 | Pre-zone trigger distance |
| `DAILY_REALIZED_LOSS_FRACTION` | 0.20 | Daily loss lock threshold |
| `PARITY_PRICE_TOLERANCE` | 1e-9 | Float comparison tolerance |
| `MINIMUM_FREE_SPACE_USD` | 3.0 | Min space between zones for entry |

### Enums

- `XauDirection` {BUY=0, SELL=1}
- `XauTrend` {NONE=0, UP=1, DOWN=2}
- `XauExecutionStatus` {SUBMITTED=0, FILLED=1, REJECTED=2, CLOSED=3, CANCELLED=4}
- `XauExecutionEvent` {FILL=0, REJECT=1, CLOSE=2, MODIFY=3, MODIFY_REJECT=4, CANCEL=5, CANCEL_REJECT=6}
- `XauOrderType` {MARKET=0, PENDING_STOP=1}
- `XauSignalFamily` {BREAKOUT=0, REVERSAL=1, PULLBACK=2}
- `XauEntryRejection` {ALLOWED=0, DAILY_LOSS=1, GROSS_RISK=2, CONCURRENCY=3, MARGIN=4, INVALID_PROTECTION=5, FREE_SPACE=6, INITIAL_RISK=7}
- `XauTpFailureAction` {NONE=0, RESTORE=1, MARKET_CLOSE=2}

### Structs

- `XauZone` {id, low, high, priority(0/1)}
- `XauOperationalSafety` {locked, block_entries, cancel_pending, cancel_pullback_cycles, close_positions}

### Zone Construction

| Function | Purpose |
|----------|---------|
| `BuildMergedZones(raw_zones, broker_day, merged[])` | Sort raw zones, merge overlapping (≥1.5 gap), assign priority=max, generate IDs `broker_day:R#` |
| `CountDirectionalCrosses(zones, prev_bid, curr_bid)` | Count zones crossed in one tick (for multi-zone gap detection) |

### Signal Validation

| Function | Purpose |
|----------|---------|
| `BreakoutValid(zone, direction, trend, close_price, engaged)` | Buy: trend UP + close > high+buffer. Sell: trend DOWN + close < low-buffer. Requires engaged. |
| `ReversalDirectionalTouch(zone, direction, trend, prev_bid, curr_bid, multi_zone_gap)` | Sell@UP: prev<low && curr≥low. Buy@DOWN: prev>high && curr≤high. Blocks on multi_zone_gap. |
| `CausalTrendThenReversal(zone, direction, current_trend, ref_count, ref_high, ref_low, prev_bid, curr_bid, updated_trend)` | Update trend from references, then test reversal touch. |

### Trend Reference

| Function | Purpose |
|----------|---------|
| `UpdateTrend(current, ref_count, ref_high, ref_low, bid)` | If bid>ref_high→UP, bid<ref_low→DOWN, else unchanged. Returns new trend. |
| `TrendReferences(state, reference_high, reference_low)` | Rolling 3-candle high/low window. |

### Pullback

| Function | Purpose |
|----------|---------|
| `PullbackPenetrated(zone, direction, bid, entry_price)` | Buy: bid ≤ high-0.20 (entry=high). Sell: bid ≥ low+0.20 (entry=low). |
| `PullbackWindowActive(bar_offset)` | True for bar_offset 1..5 (5-bar window after breakout). |
| `PullbackUsageAllowed(zone_priority, daily_fills)` | Priority 1: always. Priority 0: only if daily_fills < 1. |
| `StrictPullbackTrend(direction, closed_directions[], current_open, current_bid, current_ask)` | All closed candles must match direction (1/-1). Current price must extend beyond open. |

### Pre-Zone Trigger

| Function | Purpose |
|----------|---------|
| `PreZoneTriggerPrice(direction, target_zone)` | Buy: target.low - 1.0. Sell: target.high + 1.0. |
| `PreZoneCrossed(direction, target_zone, prev_price, curr_price)` | Cross detection at trigger price. |
| `BlocksOppositeReversal(actual_zone_touch, strict_trend_valid)` | Both must be true to block opposite reversal. |

### Risk: Stop / Target

| Function | Purpose |
|----------|---------|
| `InitialStop(direction, entry, zones[], stop_loss, stop_zone_id)` | Buy: nearest zone.high < entry, SL = max(zone.high, entry-6). Sell: nearest zone.low > entry, SL = min(zone.low, entry+6). |
| `DirectionalFreeSpace(zone_id, direction, zones[], free_space)` | Space to next zone in direction. Buy: next.low - this.high. Sell: this.low - prev.high. |
| `HasMinimumFreeSpace(zone_id, direction, zones[])` | Free space > 3.0 USD. |
| `InitialTarget(direction, entry, zones[], take_profit, target_zone_id)` | Buy: nearest zone.low > entry with ≥6 USD gap. Sell: nearest zone.high < entry with ≥6 USD gap. |

### Portfolio & Safety

| Function | Purpose |
|----------|---------|
| `PortfolioRiskAllows(capital, realized_gross_loss, open_risk, pending_risk, proposed_risk)` | Sum ≤ capital × 0.15. |
| `MaximumPositions(capital)` | 200→3, 300→5, else -1. |
| `ConcurrencyAllowsEntry(capital, open_positions)` | open < maximum. |
| `NativeMarginAllowsEntry(required_margin, free_margin)` | required ≤ free. |
| `EvaluateProtectedEntry(daily_locked, portfolio_allowed, concurrency_allowed, margin_allowed, direction, entry, stop, tp, volume)` | Sequential gate: daily→portfolio→concurrency→margin→protected_order(volume=0.01). |
| `EvaluateOperationalSafety(session_active, same_day_restart)` | If locked: block entries, cancel pending, cancel pullback cycles, close positions. |
| `DailyLossLocked(capital, net_realized_pnl, previously_locked)` | Latches true when net ≤ -capital×0.20. Capital must be <300. |
| `SessionEndActive(broker_now, broker_session_end)` | Active in last 5 minutes. |

### Profit Protection

| Function | Purpose |
|----------|---------|
| `ProfitProtectionStop(direction, entry, risk_free, bid, ask, current_stop, proposed_stop)` | Favorable = (bid-entry) or (entry-ask). Step = floor(favorable/6). Proposed = risk_free ± (step-1)×6. Must improve current stop. |
| `ProtectionModificationValid(direction, entry, current_stop, proposed_stop, proposed_tp)` | Buy: proposed_stop ≥ current_stop && proposed_stop < proposed_tp && proposed_tp > entry. Sell: proposed_stop ≤ current_stop && proposed_tp < proposed_stop && proposed_tp < entry. |

### Pullback TP Failure

| Function | Purpose |
|----------|---------|
| `PullbackTpFailureAction(direction, extended, strict_valid, initial_tp, bid, ask)` | If not extended or strict_valid→NONE. If crossed initial_tp→MARKET_CLOSE else RESTORE. |

### Restart & Execution

| Function | Purpose |
|----------|---------|
| `RestartSameDayLocked(broker_day, persisted_last_activation_day)` | True if same non-empty day. |
| `ExecutionTransition(status, event, order_type, next_status)` | Valid state transitions per execution event. Returns false for invalid. |

---

## XauExecution.mqh {#xauexecutionmqh}

**Location**: `mt5/include/XauExecution.mqh`

Execution lifecycle projection and request↔order↔position binding persistence.

### Structs

```cpp
struct XauExecutionProjection {
    string request_id;
    XauExecutionStatus status;
    XauOrderType order_type;
    XauDirection direction;
    double order_entry, fill_price, stop_loss, take_profit, close_price;
    datetime transition_time;
};

struct XauExecutionBinding {
    string request_id;
    ulong order_ticket;
    ulong position_id;
};
```

### Binding Management

| Function | Purpose |
|----------|---------|
| `BindExecutionOrder(bindings[], request_id, order_ticket)` | Add/replace binding. Validates unique request_id and order_ticket. |
| `BindExecutionPosition(bindings[], order_ticket, position_id)` | Attach position_id to existing order_ticket. |
| `ResolveExecutionRequest(bindings[], event_kind, order_ticket, position_id, request_id)` | FILL→by order_ticket. CLOSE→by position_id. |
| `ResolveExecutionOrderTicket(bindings[], order_ticket, request_id)` | Lookup request_id by order_ticket only. |

### Persistence (TSV)

| Function | Purpose |
|----------|---------|
| `LoadExecutionBindings(file_name, bindings[])` | Parse TSV with header `XAU_EXECUTION_BINDINGS\t1`. Validates each line. |
| `SaveExecutionBindingsAtomically(file_name, bindings[])` | Write to `.tmp`, verify via reload, atomic `FileMove`. Rejects `..` paths. |

### Projection Lifecycle

| Function | Purpose |
|----------|---------|
| `InitializeExecutionProjection(record, request_id, order_type, direction, entry, sl, tp, submitted_at)` | Validates protection (SL<entry<TP for buy). Sets SUBMITTED status. |
| `ProjectExecutionOutcome(record, event_kind, outcome_time, price=0, proposed_stop=0, proposed_tp=0)` | Validates transition via `ExecutionTransition`. Updates fields per event. |
| `FindExecutionProjection(projections[], request_id)` | Returns index or -1. Returns -1 on duplicate request_id. |

### Native Correlation

| Function | Purpose |
|----------|---------|
| `ProjectCorrelatedNativeOutcome(projections[], bindings[], event_kind, order_ticket, position_id, broker_time, price)` | Resolve request → copy projection → project outcome → bind position (on FILL) → commit. |
| `PersistThenPublishCorrelatedNativeOutcome(projections[], bindings[], event_kind, order_ticket, position_id, broker_time, price, bindings_file)` | Copy→project→save bindings atomically→copy back. All-or-nothing. |

---

## XauAudit.mqh {#xauauditmqh}

**Location**: `mt5/include/XauAudit.mqh`

Append-only JSONL audit for allowed entries.

### Struct

```cpp
struct XauOrderAuditEvent {
    string event_id, request_id, zone_id, rule_ids;
    XauDirection direction;
    XauOrderType order_type;
    datetime broker_time;
    double entry, stop_loss, take_profit;
};
```

### Functions

| Function | Purpose |
|----------|---------|
| `AuditTextValid(value)` | Non-empty, no quotes, backslashes, CR, LF. |
| `SerializeOrderAudit(event, line)` | Validates required fields. Produces compact JSON with schema_version=1. |
| `AppendAuditLine(file_name, line)` | Opens READ+WRITE+SHARE_READ, seeks end, writes line+\r\n, flushes. Rejects `..` paths. |
| `AppendOrderThenProject(audit_file, decision, event, projections[])` | If decision≠ALLOWED→false. Else: init projection, serialize, append, add to projections[]. |

---

## XauNative.mqh {#xaunativemqh}

**Location**: `mt5/include/XauNative.mqh`

**Read-only boundary** — no order send, no position mutation, no account identity.

### Structs

```cpp
struct XauNativeSymbol {
    int digits;
    double point, volume_min, volume_max, volume_step;
};

struct XauNativeDealOutcome {
    ulong deal_ticket, order_ticket, position_id;
    XauExecutionEvent event_kind;
    double price;
    datetime broker_time;
};
```

### Deal Classification

| Function | Purpose |
|----------|---------|
| `ClassifyNativeDealEntry(entry, event_kind)` | IN→FILL. OUT/OUT_BY→CLOSE. INOUT→false (ambiguous). |
| `LoadNativeDealTicketOutcome(deal_ticket, order_ticket, expected_symbol, expected_magic, outcome)` | Select deal, validate symbol/magic, classify entry, extract price/time/position_id. |
| `LoadNativeDealOutcome(transaction, expected_symbol, expected_magic, outcome)` | Only TRADE_TRANSACTION_DEAL_ADD. Delegates to ticket loader. |

### Symbol & Risk

| Function | Purpose |
|----------|---------|
| `LoadNativeSymbol(symbol, result)` | Digits, point, volume min/max/step. Validates ranges. |
| `NativeCashRisk(order_type, symbol, volume, entry, stop, cash_risk)` | `OrderCalcProfit` → abs(profit). Validates volume/entry/stop. |
| `NativeRequiredMargin(order_type, symbol, volume, entry, margin)` | `OrderCalcMargin`. Validates volume/entry. |

### Trade Session

| Function | Purpose |
|----------|---------|
| `NativeSecondsOfDay(value)` | Hour×3600 + min×60 + sec. Returns -1 on failure. |
| `NativeContainingTradeSession(symbol, broker_now, session_from, session_to)` | Scans current day and prior day sessions. Handles overnight (to≤from → +86400). Returns first containing session. |

---

## XauState.mqh {#xaustatemqh}

**Location**: `mt5/include/XauState.mqh`

State machines for trend reference, daily zones, pullback windows, and TP management.

### Structs

```cpp
struct XauTrendReferenceState { XauTrend trend; int count; double highs[3]; double lows[3]; };
struct XauDailyZoneSignalState { XauZone zone; bool buy_engaged, sell_engaged; int reversal_usage; int pullback_fills; };
struct XauPullbackWindowState { string parent_breakout_id; XauZone zone; XauDirection direction; int bar_offset; bool active, penetration_latched, pending_active; int sequence; };
struct XauPreZoneTriggerState { string position_id, target_zone_id; bool triggered; };
struct XauPullbackTpState { string position_id; XauDirection direction; string initial_target_zone_id; double initial_tp; string current_target_zone_id; double current_tp; bool extended; };
```

### Trend Reference

| Function | Purpose |
|----------|---------|
| `BeginTrendDay(state)` | Reset trend=NONE, count=0, zero highs/lows. |
| `RecordTrendCandle(state, high, low)` | Rolling 3-candle buffer. Returns false if high<low. |
| `TrendReferences(state, reference_high, reference_low)` | Max of highs, min of lows across buffer. |
| `ProcessTrendTick(state, bid)` | Updates trend via `UpdateTrend`. Returns current trend. |
| `CloseBarBreakoutBeforeRoll(state, zone, direction, close_price, engaged, candle_high, candle_low, breakout)` | Tests breakout on closed bar, then records candle. |

### Daily Zone Signals

| Function | Purpose |
|----------|---------|
| `InitializeDailyZoneStates(zones[], states[])` | Copy zones, reset engaged/usage/fills. Validates zone.id and low≤high. |
| `FindDailyZoneState(states[], zone_id)` | Linear search by zone.id. |
| `BeginSignalBar(states[], open_bid)` | Sets buy_engaged/sell_engaged = (open_bid inside zone). |
| `UpdateZoneEngagement(states[], prev_bid, curr_bid, multi_zone_tick_gap)` | Multi-zone gap = crosses>1. If gap: engaged=inside. Else: latch on boundary cross. |
| `ConsumeReversalUsage(state)` | Priority 1: limit 2. Priority 0: limit 1. Increments and returns true if under limit. |
| `RecordEntryAttempt(attempted_bars[], bar_id)` | Unique bar_id tracking. |

### Pullback Window

| Function | Purpose |
|----------|---------|
| `CreatePullbackWindow(window, parent_breakout_id, zone, direction)` | Initialize all fields. Validates parent/zone.id and low≤high. |
| `BeginPullbackBar(window, pending_must_cancel)` | Increment bar_offset. If >5: deactivate, set pending_must_cancel=was_pending. |
| `EvaluatePullbackPrice(window, daily_fills, bid, candidate_id, entry_price)` | If active, window 1-5, not pending, usage allowed: latch penetration (bid vs zone±0.20), generate candidate_id=parent:PB#sequence, entry=zone.high/low. |
| `RecordPullbackAttempt(window, attempted_bars[], bar_id, broker_accepted)` | Records bar attempt. If accepted→pending_active=true. |
| `RecordPullbackFill(window, zone_state)` | Validates active+pending+zone match. Increments zone_state.pullback_fills. Clears pending+penetration. |
| `RecordPullbackPendingRemoved(window)` | Clears pending_active if was pending. |

### Pre-Zone Trigger State

| Function | Purpose |
|----------|---------|
| `PreZoneCrossOnce(state, position_id, direction, target_zone, prev_price, curr_price)` | Resets state on position/zone change. Returns true only on first cross (via `PreZoneCrossed`). |
| `InitializePullbackTp(state, position_id, direction, initial_target)` | Sets initial/current TP to target.low (buy) or target.high (sell). Extended=false. |
| `ProposePullbackTpExtension(state, approached_zone, next_zone, has_next, strict_valid, requested_tp, target_zone_id)` | Only if not extended, strict_valid, has_next, approached=initial. Returns next zone low/high. |
| `RecordPullbackTpExtension(state, requested_tp, target_zone_id, broker_accepted)` | If accepted: updates current_tp/target_zone_id, extended=true. |
| `EvaluatePullbackTpFailure(state, strict_valid, bid, ask, requested_tp)` | Delegates to `PullbackTpFailureAction`. On RESTORE: requested_tp=initial_tp. |
| `RecordPullbackTpRestore(state, broker_accepted)` | If accepted: resets current_tp=initial_tp, current_target=initial_target, extended=false. |

---

## XauCoordinator.mqh {#xaucoordinatormqh}

**Location**: `mt5/include/XauCoordinator.mqh`

Bar/tick coordination, trend processing, zone engagement, signal emission.

### Structs

```cpp
struct XauSignalCandidate {
    string candidate_id, parent_breakout_id, bar_id, zone_id;
    XauSignalFamily family;
    XauDirection direction;
    XauOrderType order_type;
    datetime signal_time;
    double entry_price;
};

struct XauMarketCoordinator {
    string broker_day, bar_id;
    bool day_active, bar_active;
    double bar_open, last_bid, last_ask;
    int breakout_sequence;
    XauTrendReferenceState trend;
    XauDailyZoneSignalState zones[];
    XauPullbackWindowState pullbacks[];
    string reversal_keys[];
    string attempted_bars[];
};
```

### Functions

| Function | Purpose |
|----------|---------|
| `AppendSignalCandidate(candidates[], candidate_id, parent_breakout_id, bar_id, zone_id, family, direction, order_type, signal_time, entry_price)` | Validates required fields. Appends to array. |
| `RecordUniqueText(values[], value)` | Unique string array append. |
| `FindCoordinatorPullback(state, zone_id, direction)` | Linear search pullbacks[]. |
| `BeginCoordinatorDay(state, broker_day, zones[])` | Init daily zones, reset all fields, `BeginTrendDay`. |
| `BeginCoordinatorBar(state, bar_id, open_bid, open_ask, pending_cancellations)` | For each active pullback: `BeginPullbackBar` → count pending cancellations. Then `BeginSignalBar`. Sets bar state. |
| `ProcessCoordinatorTick(state, tick_time, bid, ask, candidates[])` | Clears candidates. Updates trend. Updates zone engagement. Emits REVERSAL on directional touch (unique per bar:zone:side). Emits PULLBACK from active windows (via `EvaluatePullbackPrice`). Updates last_bid/ask. |
| `CloseCoordinatorBar(state, close_time, high, low, close_bid, breakouts[])` | Validates bar geometry. For each zone+side: if `BreakoutValid` → emit BREAKOUT, create pullback window if not exists. Records trend candle. Deactivates bar. |

---

## XauRequests.mqh {#xaurequestsmqh}

**Location**: `mt5/include/XauRequests.mqh`

Candidate → prepared entry pipeline with safety gates and audit.

### Struct

```cpp
struct XauPreparedEntry {
    XauSignalCandidate candidate;
    XauEntryRejection decision;
    double volume_lots, stop_loss, take_profit;
    string stop_zone_id, target_zone_id;
};
```

### Functions

| Function | Purpose |
|----------|---------|
| `EntryBarAvailable(attempted_bars[], bar_id)` | True if bar_id not in attempted_bars. |
| `CandidateAttemptAvailable(state, candidate)` | Bar available + zone exists + family-specific: BREAKOUT=always. REVERSAL=usage<limit (priority 1:2, 0:1). PULLBACK=window active, not pending, usage allowed. |
| `PrepareCandidateEntry(candidate, zones[], daily_locked, capital, realized_gross_loss, open_risk, pending_risk, open_positions, native_cash_risk, required_margin, free_margin, prepared)` | 1. Validates family. 2. `HasMinimumFreeSpace`. 3. `InitialStop`/`InitialTarget`. 4. `PortfolioRiskAllows`. 5. `EvaluateProtectedEntry` (all gates). Sets decision, SL, TP, zone IDs. Volume fixed 0.01. |
| `BuildPreparedOrderAudit(prepared, event_id, request_id, event)` | Only if ALLOWED. Fills audit struct with rule_ids per family: BREAKOUT="BREAKOUT_VALIDATION,ZONE_ENGAGEMENT", REVERSAL="REVERSAL_DIRECTIONAL_TOUCH", PULLBACK="PULLBACK_CONSERVATIVE". |
| `CommitPreparedEntryAttempt(state, prepared, broker_accepted)` | Only if ALLOWED. BREAKOUT: record bar attempt. REVERSAL: check usage limit, record bar, increment usage. PULLBACK: `RecordPullbackAttempt` with broker_accepted. |

---

## XauTesterBroker.mqh {#xautesterbrokermqh}

**Location**: `mt5/include/XauTesterBroker.mqh`

Tester-only OrderSend wrappers. All functions return false if not in tester or not enabled.

### Struct

```cpp
struct XauTesterSubmission {
    bool attempted, accepted;
    ulong order_ticket, deal_ticket;
    uint retcode;
};
```

### Functions

| Function | Purpose |
|----------|---------|
| `TesterExecutionAllowed(enabled)` | `enabled && MQL_TESTER`. |
| `NativeFillingPolicy(symbol)` | FOK/IOC/RETURN from SYMBOL_FILLING_MODE. |
| `TesterRetcodeAccepted(retcode)` | DONE, PLACED, DONE_PARTIAL. |
| `SubmitTesterPreparedEntry(enabled, magic, symbol, prepared, submission)` | Builds MqlTradeRequest (MARKET: DEAL at bid/ask, deviation=20. PENDING: STOP at entry_price). OrderSend. Fills submission. |
| `CancelTesterPendingOrders(enabled, magic, symbol, cancelled_tickets[])` | Iterates orders, sends REMOVE. Collects cancelled tickets. |
| `CloseTesterPositions(enabled, magic, symbol, closed_positions)` | Iterates positions, sends opposite DEAL at bid/ask, deviation=20. Counts closed. |
| `CloseTesterPosition(enabled, magic, symbol, position_ticket, submission)` | Single position close. Fills submission with attempt/accepted/tickets. |
| `ModifyTesterProtection(enabled, magic, symbol, position_ticket, stop_loss, take_profit, accepted)` | SLTP modify. Validates positive SL/TP. Fills accepted. |

---

## XauTesterRisk.mqh {#xautesterriskmqh}

**Location**: `mt5/include/XauTesterRisk.mqh`

Risk snapshots from tester history and live positions/orders.

### Struct

```cpp
struct XauTesterRiskSnapshot {
    double net_realized_pnl, realized_gross_loss;
    double open_position_risk, pending_order_risk;
    double free_margin;
    int open_positions, pending_orders;
};
```

### Functions

| Function | Purpose |
|----------|---------|
| `LoadTesterRealizedRisk(magic, symbol, day_start, broker_now, net_realized, gross_loss)` | HistorySelect range. Aggregates deals by position_id. Sums profit+swap+commission+fee. Closed positions (OUT/OUT_BY) → net_realized; negative → gross_loss. |
| `LoadTesterExposureRisk(magic, symbol, snapshot)` | Positions: risk via `NativeCashRisk` (validates protected stop). Orders: BUY_STOP/SELL_STOP risk via `NativeCashRisk`. Sums risk, counts. |
| `LoadTesterRiskSnapshot(enabled, magic, symbol, day_start, broker_now, snapshot)` | Combines realized + exposure. Adds free_margin from account. |
| `TesterPositionRiskFree(enabled, magic, symbol, position_id, direction, entry, volume, broker_now, risk_free)` | Sums native costs (commission+fee+swap, floored at 0). Computes cash per 1 USD move via `OrderCalcProfit`. risk_free = entry ± offset. |

---

## XauVisual.mqh {#xauvisualmqh}

**Location**: `mt5/include/XauVisual.mqh`

**Render-only** — never feeds back into decisions.

### Struct

```cpp
struct XauVisualMarker {
    string event_id, zone_id, label;
    datetime broker_time;
    double entry, stop_loss, take_profit;
    int zone_priority;
};
```

### Functions

| Function | Purpose |
|----------|---------|
| `XauZoneColor(priority)` | Priority 1→Gold, else DodgerBlue. |
| `XauMarkerTooltip(marker, digits)` | Formatted string: Time, Zone, Entry, SL, TP, Event. |
| `DrawXauZone(chart_id, zone, from_time, to_time)` | Creates/updates OBJ_RECTANGLE with fill, background, hidden, non-selectable. Color by priority. |
| `DrawXauAuditMarker(chart_id, marker, digits)` | Creates/updates OBJ_TEXT at entry price with label + tooltip. Color by zone priority. |

---

## Cross-Reference to Main README

See [mt5/README.md](../README.md) for:
- [Main pipeline overview](../README.md#core-pipeline-functions)
- [Global state reference](../README.md#global-state-mt5xauusd_mvpmq527-69)
- [Input parameters](../README.md#input-parameters-mt5xauusd_mvpmq518-26)
- [Event handlers](../README.md#event-handlers)
- [Data flow diagram](../README.md#data-flow-summary)