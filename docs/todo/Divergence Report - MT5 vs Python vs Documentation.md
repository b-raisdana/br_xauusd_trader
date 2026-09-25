# Divergence Report: MT5 vs Python vs Documentation

## Scope and conclusion

Reviewed 2026-09-20 against the working tree, including staged and unstaged changes. This is source inspection with previously stored test evidence, not a new runtime test.

**Original source of truth, explicitly confirmed by the Leader: [`mt5/XAUUSD_MVP.mq5`](../../mt5/XAUUSD_MVP.mq5), including its called include modules.** Python and other documentation do not override this reference. Runtime wiring is distinguished from isolated contract helpers and smoke checks.

The selected Python path is **not equivalent to MT5**. Its M15 interval matches, but state propagation is incomplete, signal methods are placeholders, `action` is always `None`, and native risk/order/position management is absent. The [updated implementation plan](Vectorization%20Implementation%20Plan.md) now specifies the actual MQL semantics, reference caveats and prioritized work with acceptance criteria.

The three comparison targets are the EA and its dependencies; the implementation plan; and [`__main__.py`](../../src/application/xauusd_trading_strategy_1_vector/__main__.py) with its reachable implementation. The plan is a target specification, not executable evidence.

## Reachable Python path

`cli → asyncio.run(main) → load_zones_from_file → get_ticks → get_ohlcv(timeframe="15min") → run_vectorized_strategy → ZaoneCache → VectorizedXauUsdStrategy.process_tick_data → candle merge → order columns → position columns → save → summary`.

All acquisition precedes strategy construction. The runner passes **only ticks** into the strategy; fetched candles are joined afterward. `preload_days` is compatibility-only and unused; CLI/main accept `debug` but do not use it. The internal-state accessor is separately exported, but the runner does not return its strategy object.

The active class is `vectorized_strategy.py`. Sibling `trend.py`, `engagement.py`, `signals.py`, scalar helpers and archived alternatives do not establish behavior unless this class calls them. In particular, earlier alternative-implementation test results cannot validate the selected class.

## Three-way comparison

Status describes selected Python relative to MQL. The plan column describes requirements, not completed work.

| Area / source anchor | MQL source of truth | Updated plan | Python reached from CLI / finding |
|---|---|---|---|
| Modes — `OnInit`, `OnTick` | Research default; explicit event-loop switch; guarded tester execution; live flag rejected | Preserve modes, no live expansion | Offline scaffold/acquisition, no matching execution mode. **Different scope** |
| Inputs | Native symbol/ticks/M15/session data and generated daily zones; project Magic | Explicit data/native-outcome contracts | Typer symbol/zones/output/debug; zone dates bound acquisition; fetch-before-construction. **Partial** |
| Symbol propagation — `get_ticks`, `Tick.from_ndarray` | `_Symbol` passed through native path | End-to-end nondefault-symbol validation | Requested symbol used for fetch, but converter called without symbol/broker and defaults to config; candle label uses requested symbol. **P0 mismatch** |
| Index/day | Broker day from native tick time | Stable event IDs and explicit broker-time mapping | Index `(symbol,broker,date,datetime)`; date is UTC second floor. Class derives day directly from datetime, normally UTC. **Not broker-day parity** |
| M15 — `_compute_bar_time` | Native `PERIOD_M15` throughout | Retain and verify bar alignment | Floors `15min`; CLI fetches `15min`. **Period matches**; not a configurable bar-time port |
| Startup — `InitializeCurrentEventLoop` | Same-day closed history bootstrap and native current open; trend crossings not replayed | Supply history/open to causal computation | Fetched candles never enter class; no history bootstrap; first tick substitutes for native open. **Missing** |
| Day/bar flow — `ProcessCurrentEventLoopTick` | Day reset before old close; close before begin; management then BOs then current tick | Preserve exact phases | `day_active` set only on first index label; later bar groups usually skipped. Supplied bar group is closed before beginning, before tick calculations. **Incorrect** |
| Trend — `RecordTrendCandle`, `ProcessTrendTick` | Prior closed bars, count≤3, same-day sticky direction | Shift references; threshold events and within-day propagation | Zero/NONE defaults per row; history written at group last row without propagation; group future max/min used; row-wise `apply`; nested `where` retains row default, not preceding tick trend. **Incorrect/noncausal** |
| Zones — `BuildMergedZones` | Normal0/High1; normalized, sorted, chain merge<1.5; daily IDs | Reuse validated metadata | Cache validates/filter Enabled/maps priority/merges/deep-copies. **Implemented component**, not full parity; cache date-only |
| Missing zones | Initialization fails | Explicit failure/diagnostic | Cache returns empty list; class skips zone work and can return null actions. **Different** |
| Engagement — `BeginSignalBar`, `UpdateZoneEngagement` | Per-zone latches, inclusive open, bar reset | Per-zone segmented cumulative OR | Only aggregate pair; open reset false rather than containment; no cumulative propagation. **Incorrect shape/behavior** |
| Previous quote/gap | Previous processed quote; opening reset; multi-gap destination-only new latches | Partition shifts and gap masks | Shifts mostly-zero `last_bid` before tick pass populates it; ordinary crossing masks also run on multi-gaps. **Incorrect** |
| BO — `CloseCoordinatorBar` | Close engagement/trend/strict±1; BO IDs and PB parent windows | Ordered close candidates before history roll | Expressions discarded; no candidates/sequence/window creation. **Placeholder** |
| Reversal — `ProcessCoordinatorTick` | Updated trend, directional touch, no multi-gap, bar/zone/side uniqueness | Candidate uniqueness separate from attempts | Masks/key expressions discarded; `reversal_signals=None`; no uniqueness/quota. **Placeholder** |
| PB — `EvaluatePullbackPrice` | Penetration±0.20, pending at edge, offsets1–5, parent retention | Separate emission/pending/fill/cancel/expiry | Active defaults false; no window evaluation or signals. **Placeholder** |
| Candidate ordering — `ProcessTesterCandidates` | BOs first, then reversals/PBs; gate→audit→send→commit | Ordered events/reducer | No arbitration, gates or submission. **Missing** |
| Quotas — `CommitPreparedEntryAttempt`, `RecordPullbackFill` | Reversal attempts Normal1/High2; PB fills Normal1/High∞; attempted candidate-bar slot | Distinguish candidate/attempt/fill | Key/attempt string placeholders; no per-zone consumption. **Missing** |
| SL/TP/free space — `XauContracts`, `XauRequests` | Nearest qualifying boundaries; stop cap6, target≥6, gap>3 for all families | Exact formulas/order and boundary tests | No reachable protection preparation. **Missing** |
| Capital/risk — `XauTesterRisk` | 0.01 lot, 200/300 profiles, native cash/margin, GROSS15, daily loss below300 | Native fixture boundary and reasons | No risk, capital, margin or concurrency engine. **Missing** |
| Request/fill prices — `SubmitTesterPreparedEntry` | Candidate Bid/close; market Ask/Bid request; pending edge; native fill | Preserve distinct prices | No generated orders/fills. **Missing** |
| Execution — `OnTradeTransaction` | Symbol/Magic filter, audit/projection/bindings, callback recovery/idempotence | Ordered outcome records | No native outcome source/projector. **Missing** |
| Strict PB/TP — `ManageTesterPullbackTp` | Current-candle and closed directions; pre-zone1; one extension, restore/close | Exact anchor/latch/acceptance semantics | No position TP management. **Missing** |
| RF/SL — `ManageTesterProfitProtection` | Observed native costs, 6-unit steps, never loosen | Match measured cost/quote fixtures | No cost/protection engine. **Missing** |
| Conflict close — `CloseTesterOppositeReversals` | Close same-zone opposite reversal for valid BO before BO entry | Separate from touch-time blocking | Neither close nor touch-block implemented. **Missing** |
| Session/restart — `ExecuteTesterOperationalSafety` | Broker session end−5, project cancel/flatten/lock, restart simulation | Explicit scope and outcomes | No calendar/lock/flatten. **Missing** |
| Actions — `_generate_actions` | Ordered candidates/requests/outcomes; no native action-column enum | Tick rows plus ordered events; compatibility summary | Core returns only all-null `action`. Order/position helpers mostly initialize null columns. **No trading parity** |
| Diagnostics | Audit/counters/native results/specification/deinit summary | Optional trace/state and first mismatch | `_per_tick_temp_state` exists but runner drops its extra fields; summary cannot show them; debug unused. **Partial** |
| Vectorization | Stateful native tick loop | Day-level batching, no Python bar/tick loops or row `apply` in hot path | Bar `groupby` loop and row-wise reference `apply` remain. **Requirement unmet** |

## Additional integration findings

- **P0 export collision:** `merge_results_with_candles` constructs a MultiIndex from arrays while retaining same-named broker/symbol/datetime/date columns. `save_results_to_file` then calls `reset_index()`, which can raise `ValueError: cannot insert …, already exists`. This is source-level analysis, not a CLI execution recorded here.
- **P0 join cardinality:** no `validate="many_to_one"` on candle merge; duplicate candle keys can multiply tick rows. Final full-bar OHLC joined to earlier ticks is retrospective context and would leak future information if later reused as a causal feature.
- **P0 duplicate identity:** `.loc[first_index]`/`.loc[group.index]` use labels, so duplicate tuples can update multiple rows or misalign assignment. Stable sorting does not repair these writes or preserve arbitrary caller cross-group order.
- **P0 quote alignment:** runner reattaches Bid/Ask positionally from sorted input, assuming exact agreement with output cardinality/order. Test stable event identity across supported index layouts rather than assuming it.
- **P0 empty/error flow:** core empty handling does not prove runner merge/enrichment/export; `main` explicitly rejects empty zones. Missing native data and missing zone days need deterministic failure behavior.
- **P1 data scope:** date-only zone cache shares one daily set across instruments/brokers; CLI labels candles with configured broker. Define supported scope and account/risk mapping.
- **P1 debug/report semantics:** exported accessor is not a functioning CLI debug path; initialized order/position columns do not imply simulated lifecycle or accounting.

## MQL limitations and differences from other documentation

MQL remains the reference. These source findings must be preserved and labeled in parity work, not silently replaced by what another document says should happen. The plan names them M1–M8.

| ID | Source evidence and implication | Plan/Python treatment |
|---|---|---|
| M1 | `BlocksOppositeReversal` is exercised by smoke checks but not production coordinator/preparation | No claim of wired strict-PB blocking at actual touch; distinguish breakout conflict close |
| M2 | `BeginPullbackBar` reports expiry cancellation; event loop only counts/logs it; broker stops are GTC | Internal inactive window is not native cancellation; include possible late-fill behavior |
| M3 | Daily-loss lock updated with candidates; pending cancellation wired for session/restart, not daily loss | Preserve actual entry-lock scope; do not claim other docs' cancellation behavior exists |
| M4 | Attempt gate/commit use candidate bar; close BO and current reversal/PB can use different IDs on same tick | Trace signal bar and physical attempt bar separately; do not silently impose a different slot rule |
| M5 | Restart flag is simulation input, not persisted activation-day detection | Tester scenario is not automatic reattach protection |
| M6 | Free-space gate includes BO; other rule text explicitly names reversal/PB | Port all-family MQL behavior |
| M7 | Strict history starts after candidate bar; TP failure uses current quote, not historical crossing | Delayed fills and crossing/retreat need reference fixtures |
| M8 | Day branch bypasses old close; gaps read one previous bar; failure flag only suppresses repeated logs | No invented batch-end close, missing-bar replay or persistent failure latch |

Other corrected details: priority0/1; daily loss resets on initialization; runtime counters do not all reset daily; PB sequence can advance on a later-gated candidate; active PB parent is retained; market request differs from candidate price; pre-zone latch precedes strict/modify success; RF uses observed native costs rather than unknown future fees.

## Plan assessment and optimization

The plan now replaces general algorithm prose with source-specific execution phases, state ownership, exact thresholds/formulas, candidate/attempt/fill distinctions and native management scope. It removes the unsupported claim that the selected Python is largely consistent with MT5.

Its TODO order is data/time fidelity → causal state → candidates → feedback-dependent attempts/outcomes → risk/management/reporting → measured optimization. Each stage has completion criteria. M1–M8 are explicit reference caveats rather than accidental behavior changes.

Vectorize shifted closed-bar references, threshold events, per-zone cumulative engagement and static boundary lookups. Keep memory bounded by day and use sparse candidate/event records where appropriate. Submission/fill/quota/risk feedback needs an explicit ordered reducer or verified compiled scan; independent masks alone cannot establish equivalence. Profile only after correctness; measure peak memory as well as elapsed time. No strategy parameter tuning is proposed.

## Evidence and completion status

- MQL anchors: `InitializeCurrentEventLoop`, `ProcessCurrentEventLoopTick`, `ProcessTesterCandidates`, `ManageTesterPullbackTp`, `ManageTesterProfitProtection`, `ExecuteTesterOperationalSafety`, `OnInit/OnTick/OnTradeTransaction`; [`XauContracts.mqh`](../../mt5/include/XauContracts.mqh), [`XauCoordinator.mqh`](../../mt5/include/XauCoordinator.mqh), [`XauState.mqh`](../../mt5/include/XauState.mqh), [`XauRequests.mqh`](../../mt5/include/XauRequests.mqh), [`XauTesterBroker.mqh`](../../mt5/include/XauTesterBroker.mqh), [`XauTesterRisk.mqh`](../../mt5/include/XauTesterRisk.mqh).
- Python anchors: [`strategy_runner.py`](../../src/application/xauusd_trading_strategy_1_vector/strategy_runner.py), [`vectorized_strategy.py`](../../src/application/xauusd_trading_strategy_1_vector/vectorized_strategy.py), [`zone_cache.py`](../../src/application/xauusd_trading_strategy_1_vector/zone_cache.py), [`result_processing.py`](../../src/application/xauusd_trading_strategy_1_vector/result_processing.py), [`reporting.py`](../../src/application/xauusd_trading_strategy_1_vector/reporting.py), [`tick.py` adapter](../../src/infrastructure/mt5/tick.py), [`Tick` schema](../../src/domain/schemas/tick.py).
- Latest 2026-09-20 sections in [`CURRENT_STATE.md`](../CURRENT_STATE.md)/[`TEST_STATUS.md`](../TEST_STATUS.md) report 4 cache tests passing and 17 selected-class state/where failures. Repository gate also has missing fixture/ratchet problems. Earlier 18/34-pass results and the 0.607-second benchmark belong to an alternative class, not the selected implementation.
- Frozen MVP contract/native-test evidence has narrower scope than this vector CLI and does not prove every runtime wiring path. This review ran no tests or MT5 and makes no new runtime parity claim.
- **DONE:** Update both requested documents with the source comparison and optimized implementation plan. **TODO:** Execute the plan's implementation stages. No implementation code was changed by this review.
