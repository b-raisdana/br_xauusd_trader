# Vectorization Implementation Plan

## Scope and source of truth

Reviewed 2026-09-20 against the working tree, including uncommitted Python changes. This review updates documentation only; unchecked implementation work below remains outstanding.

**Original source of truth, explicitly confirmed by the Leader: [`mt5/XAUUSD_MVP.mq5`](../../mt5/XAUUSD_MVP.mq5), including the code it calls in `mt5/include/`.** Reproduce its actual behavior, ordering, state and execution boundaries. Other documentation and Python implementations do not override it. Distinguish runtime behavior from helpers that exist only in tests; record apparent gaps without silently repairing or redefining the reference.

Target: [`__main__.py`](../../src/application/xauusd_trading_strategy_1_vector/__main__.py) and its reachable strategy, runner, cache, data adapters and result-processing modules. The selected Python class is a scaffold: its signal methods are incomplete and `_generate_actions` returns `None` on every row. This plan is a target specification, not a parity claim. See the [three-way comparison](Divergence%20Report%20-%20MT5%20vs%20Python%20vs%20Documentation.md).

## MQL behavior to reproduce

### Modes, acquisition and initialization

- `OnInit` rejects `InpEnableTrading=true`. `OnTick` processes the coordinator only if `InpRunCurrentEventLoop=true`; actual order operations additionally require `InpEnableTesterExecution`. Tester execution requires Strategy Tester, positive Magic, native-outcome observation and capital 200 or 300. Default switches are false; default capital is 200. Restart simulation requires tester execution. Initialization also runs embedded smoke checks; the optional time probe emits at most five successful tick reads.
- Each EA instance uses `_Symbol`; native orders/outcomes are filtered by project Symbol/Magic. Python may support multiple broker/symbol partitions, but must not infer independent account margin or risk budgets from those partitions.
- M15 bars come from native `iTime/iOpen/iHigh/iLow/iClose` and `CopyRates`, not a configurable one-minute provider. Broker day derives from `tick.time`.
- `InitializeCurrentEventLoop` loads generated zones, normalizes/merges them and initializes the coordinator. Missing/empty zones fail initialization. It records closed M15 history from broker midnight through `bar_time-1`, retaining the last three highs/lows. It does not replay historical trend crossings: trend stays NONE until a processed tick establishes it.
- Current bar open is native `iOpen`, not necessarily the first supplied tick. Opening Ask is synthesized as `open_bid + max(0, tick.ask-tick.bid)`. Internal day/zone IDs use `YYYY-MM-DD`; native date lookup uses `YYYY.MM.DD`.

### Ordered tick processing

`ProcessCurrentEventLoopTick` has the following order:

1. Read current M15 bar time; initialize if needed; emit tester symbol specification when applicable.
2. If broker day changed, reinitialize. This branch precedes normal bar-close handling, so it does not close the old day's final bar through that branch.
3. Otherwise, on bar change, close the active coordinator bar using native shift-1 OHLC and the new bar timestamp. Require close Bid to match the last processed Bid within `1e-9`. Generate breakouts from existing close-time trend/engagement **before** rolling the closed candle into trend history. Begin the new bar, advance pullback offsets and reset engagement from native open.
4. Run operational session/restart safety → pullback TP management → profit protection → close opposite same-zone reversal positions for valid close breakouts.
5. Process close-breakout candidates through gates and submission.
6. Process current tick: update trend → engagement/gap classification → reversals in zone order, BUY then SELL → pullbacks in window order → update last Bid/Ask.
7. Count current reversal/pullback candidates and process them in that order.

Breakout candidate `bar_id` identifies the **closed** bar; its signal time is the new bar timestamp and candidate entry is closed Bid. Submission occurs on the new tick. Beginning a bar resets previous Bid/Ask to its opening values; other ticks use the previous processed quote. Do not close the final bar simply because a Python batch ends. On a missing-bar gap, the MQL branch reads one shift-1 bar; it does not replay every missing bar and can fail the close/last-Bid check.

`OnTradeTransaction` is a separate event source. Project-owned native outcomes update audit, bindings and projections; synchronous submissions may also apply immediate deal outcomes. Preserve idempotence and callback/binding recovery rather than counting the same fill twice.

### State and reset boundaries

| State | Required shape and behavior |
|---|---|
| Coordinator | Per instance/day: day/bar active, bar ID/open, previous Bid/Ask; initialized at day/bar boundaries |
| Trend | Direction NONE/UP/DOWN, count 0–3, three highs/lows; reset daily, optionally bootstrap closed same-day history; roll only after close breakout evaluation |
| Zone | One record per merged zone: two engagement latches, reversal usage, pullback fills; usage resets daily, engagement resets per bar |
| Identity | Daily BO sequence, reversal-key set and attempted-bar IDs; day reset; reversal keys include bar/zone/side |
| Pullback | One stored slot per zone/direction: parent BO, offset, active, penetration latch, pending flag, sequence; inactive slots can be reused |
| Position TP | Initial/current target IDs/prices, extension flag and position/target crossing latch; accepted outcomes govern changes |
| Runtime | Requests, execution bindings/projections, audit and diagnostic counters; not all reset daily |
| Safety | Initialization clears daily-loss, operational and session-flat flags; restart flag comes from simulation input. Daily-loss lock persists only until reinitialization |

### Zones, trend and engagement

- Priority is **Normal=0, High=1**, not 1/2. Python zone input uses `normal`/`high` before conversion. Enabled filtering belongs to input preparation; `XauZone` has no Enabled field.
- `BuildMergedZones` swaps reversed bounds, sorts low then high, and merges chains when next low minus merged high is **<1.5**. Equality 1.5 remains separate. Overlap and line zones are valid; priority becomes maximum; IDs are `YYYY-MM-DD:R1`, `R2`, etc. There is no strategy hard cap.
- Trend references up to three preceding closed bars of the current day. With zero references it remains NONE. `bid > max(highs)` sets UP; `bid < min(lows)` sets DOWN; equality/inside retains the preceding same-day direction. Normal day-start reference counts progress 0,1,2,3. Current-bar final OHLC must not enter its own tick decisions.
- Inclusive containment of bar open engages both directions. Upward crossing `previous_bid < low <= bid` latches BUY; downward crossing `previous_bid > high >= bid` latches SELL.
- Count directional crossed zones. When count >1, only destination-containing zones gain new engagement, in both directions; **existing latches remain set**. Skip ordinary crossing updates for that tick. No synthetic intermediate touches. Engagement is per zone, not a global pair of flags.

### Candidates, attempts and fills

| Family | Candidate generation | Consumption and lifecycle |
|---|---|---|
| Breakout | At close: BUY engaged + UP + `close > high+1`; SELL engaged + DOWN + `close < low-1`. Daily IDs `BO1`, `BO2`, …; MARKET | Creates a PB slot independently of order acceptance/reversal presence. An active same-zone/direction slot retains its existing parent; a later BO does not replace it. Attempt consumes candidate bar ID |
| Reversal | No multi-zone gap. SELL: UP and `previous_bid < low <= bid`; BUY: DOWN and `previous_bid > high >= bid`. Key `bar_id:R:zone_id:side`, BUY=0/SELL=1; MARKET; candidate entry Bid | Unique key recorded when candidate emitted even if later gated. Per-zone/day quota across directions: Normal1/High2. Actual submission attempt consumes quota even if broker rejects; mere signal does not |
| Pullback | Active offsets 1–5; BUY penetration `bid <= high-0.20`, SELL `bid >= low+0.20`; latch emits PENDING_STOP at high/low with ID `parent:PBn` | Submit on penetration, not after waiting for re-entry. Sequence advances per emitted candidate, including later gate rejection. Accepted submission sets pending; fill increments daily zone fills and clears pending/latch. Broker rejection leaves latch available; cancellation clears pending but not latch. Normal max1 fill/day, High unlimited |

New PB offset is 0; `BeginPullbackBar` increments it once per processed bar transition. Offset 6 deactivates the window and reports whether pending cancellation is needed. It does not remove the slot or itself cancel a broker order. While pending is active, no further PB candidate is emitted. Fill does not automatically close the parent cycle; further penetration can generate another PB while the window/quota permit it.

Runtime fill recovery is distinct from the normal window transition: `ApplyProjectOwnedNativeOutcome` increments the zone's PB fill count even if the window is missing or `RecordPullbackFill` fails, provided the zone still resolves. In that fallback it does not perform the normal pending/latch reset. Missing zone fails. Duplicate already-projected fill/close outcomes return early. Preserve this distinction in late-fill and callback fixtures.

### Entry, risk and execution prices

Actual `ProcessTesterCandidates` order: candidate-bar/quota availability → native risk snapshot/daily-loss update → initial stop/target precheck (missing zone skips candidate) → native cash risk/margin → preparation → durable order audit/projection/runtime record → submit → commit attempt/quota → bind accepted ticket → immediate native outcome if available.

`PrepareCandidateEntry` checks free space, protection-zone lookup, then daily loss, GROSS15, concurrency, margin and directional protection/fixed volume. A gate rejection does not consume an attempt; a broker-rejected submission does.

| Calculation | Exact reference behavior |
|---|---|
| Free space | From signal zone to adjacent merged zone: BUY `next.low-zone.high`; SELL `zone.low-previous.high`; missing neighbor rejects; must be `>3`. Preparation applies this to **all three families** |
| Stop | BUY nearest zone high strictly below candidate entry, then `max(high, entry-6)`; SELL nearest zone low strictly above entry, then `min(low, entry+6)`. Missing qualifying zone rejects |
| Target | BUY nearest zone low at least 6 above entry; SELL nearest zone high at least 6 below entry. Skip nearer ineligible zones; never clamp to an invented price. Missing target rejects |
| Size/concurrency | Fixed 0.01 lot; capital200→3 open positions, capital300→5; unsupported profiles reject. Concurrency counts open positions, while pending risk is included separately |
| GROSS15 | Nonnegative gross realized loss + open risk + pending risk + proposed native cash risk `<= 0.15*capital + 1e-9`; price distance is not automatically account-currency loss |
| Daily loss | Capital below300: net realized PnL `<= -0.20*capital` latches entry lock until reinitialization. Capital300 does not activate this threshold |
| Margin/protection | Native required margin ≤ free margin; directional SL/entry/TP ordering; fixed-volume tolerance `1e-9` |
| Prices | Candidate Bid/closed Bid drives protection/risk preparation. MARKET request uses current Ask for BUY, Bid for SELL; pending request uses zone edge. Native fill price is a separate outcome |
| Broker request | SL/TP from creation; native filling policy, GTC, market deviation20 points; retain acceptance and invalid-price/stops/other rejection outcomes |

### Position and safety management

- Strict PB trend reads closed candle directions **after the PB candidate bar**, excluding that bar, plus current M15 open: BUY Bid>open; SELL Ask<open. Any doji/opposite closed candle fails; same-bar decisions use only the current candle. The runtime anchor is candidate bar, not an independently recorded delayed-fill bar.
- Pre-zone crossing: BUY Bid crosses target low−1 upward; SELL Ask crosses target high+1 downward; a gap across the level counts. `PreZoneCrossOnce` latches by position/target before strict validation or broker acceptance, so a failed proposal/modify does not automatically retry at the same target.
- Strict-valid crossing can extend initial TP one adjacent zone. No next zone leaves it unchanged. State changes on broker acceptance. After extension, strict failure restores initial TP if current quote is before it; otherwise market-closes. The helper tests current Bid/Ask, not a historical ever-crossed latch. No recursive extension.
- Profit protection: `step=floor(favorable_move/6)`, favorable BUY Bid−entry or SELL entry−Ask. For step≥1 propose BUY `RF+(step-1)*6`, SELL `RF-(step-1)*6`, only if tighter. RF converts observed native commission/fee/swap via `OrderCalcProfit`; unknown future exit costs are not guaranteed covered.
- Session/restart safety cancels project pending orders, closes project positions, cancels PB cycles and locks entries. Trigger is broker session end−5 minutes or simulated restart. Native snapshot verifies zero exposure. Scope is Symbol/Magic; automatic durable restart detection is not implemented by the simulation flag.

## Reference caveats: preserve, do not silently change

These are source-inspection findings. They constrain what a faithful port may claim; different intended behavior in other documentation does not override the Leader-selected MQL source. Any correction to MQL is separate work.

| ID | Actual reference behavior / limitation | Required parity evidence |
|---|---|---|
| M1 | `BlocksOppositeReversal` is used by smoke checks, not production reversal generation/preparation | Distinguish available helper from absent touch-time blocking; do not claim it is wired |
| M2 | Window expiry reports pending cancellations, but event loop only counts/logs them; stops are GTC | Distinguish internal inactive window from broker cancellation and possible late fills |
| M3 | Daily-loss update occurs during candidate processing; no daily-loss-triggered pending cancellation is wired there | Preserve entry-lock behavior separately from session/restart cancellation |
| M4 | Attempt gate keys candidate bar; close BO and current reversal/PB can use different slots on one physical tick | Trace candidate bar and physical attempt bar independently; do not silently consolidate them |
| M5 | Restart lock comes from `InpSimulateSameDayRestart` | Do not claim automatic restart/reattach detection |
| M6 | Free-space gate covers BO as well as reversal/PB | Reproduce all-family scope even where other docs mention only reversal/PB |
| M7 | PB strict history anchors to candidate bar; TP failure compares current quote | Include delayed fill and prior-crossing/retreat cases |
| M8 | Day rollover skips old close; gaps read one shift-1 bar; failure flag suppresses repeated logs but does not stop later calls | Preserve branch/failure traces; no invented missing-bar replay, batch-end close or persistent failure lock |

## Optimized implementation design

The optimization target is equivalent computation, not changed trading behavior or parameter tuning.

- Acquire data before strategy construction; reuse validated in-memory zone metadata. Pass authoritative closed M15 history/current opens into computation rather than joining candles only for reporting.
- Retain the existing vector-state constraint: Python time-partition loops may cover days or larger units; bar/tick loops and row-wise `apply` do not belong in the vector hot path. Zone metadata iteration is allowed.
- Compute closed-bar references with grouped aggregates, shifts and array gathers. Trend is a threshold-event series followed by within-day forward-fill; engagement is per-zone/per-bar cumulative OR after open seeding and multi-gap masking. Apply reset and availability masks first.
- Precompute daily sorted zone arrays, priorities, adjacent gaps and boundary lookups. Use searches/gathers for nearest qualifying stop/target; benchmark small metadata loops versus broadcasting.
- Keep keyed zone/window/position state, with sparse ordered candidates or bounded daily arrays. Avoid an unbounded ticks×zones×windows tensor. Measure peak memory and time; make wide debug snapshots optional.
- Submission, acceptance, fill, quota and account-state feedback cannot be replaced by independent row masks. Specify an ordered deterministic reducer/reference, then choose a verified compiled scan or other implementation respecting the vector hot-path constraint. Do not claim full vectorization by omitting feedback. Reuse existing domain logic only after confirming its MQL semantics.

### Data and output contracts

- Identify index levels by name. Native `Tick.from_ndarray` returns `(symbol, broker, date, datetime)`; both dates use UTC nanosecond dtype, `datetime` derives from milliseconds, and `date` is **one-second flooring**, not broker day. `(broker, symbol, datetime, date)` is a compatibility layout.
- Preserve all tick rows, including identical timestamps/full index tuples, using positional event IDs. Require chronological order within broker/symbol and finite positive Bid with Ask≥Bid. Preserve duplicate event order; restore caller order after internal sorting. Avoid label-based writes as positional updates.
- Map UTC to verified broker day/bar/session explicitly, retaining offset provenance. Native opens and closed-history availability must match MQL; UTC midnight cannot be assumed broker midnight. Full current-candle OHLC may be retrospective display context, never an available tick feature.
- Validate unique candle keys `(broker,symbol,bar_time)` with a many-to-one join and explicit missing-zone handling. Keep index names from colliding with exported columns. Test nondefault-symbol propagation from acquisition through reporting.
- Output one state row per input tick plus ordered events containing tick ID, phase/sequence, candidate ID, parent BO, candidate/attempt bars, zone, family, direction, order type, candidate/request/fill prices, SL/TP, decision/reason and lifecycle outcome.
- Retain `action` as a documented compatibility summary referencing associated events. MQL has no native action-column enum; specify whether a summary means candidate, attempted order or fill. Multiple events on one tick must not be discarded. Optional debug state must be accessible without strategy I/O.

## Executable TODO and acceptance

The sequence reduces rework: establish data/time fidelity, prove state, then candidates and outcome feedback, then measure speed. Full vector parity is this implementation objective, not a retroactive change to older frozen-MVP test scope.

| Status / priority | Scope and change | Completion criteria |
|---|---|---|
| **DONE — review** | Trace MQL and selected Python path; update both requested docs | Exact source authority, semantics, caveats and remaining work recorded; no implementation claim |
| **TODO P0 — data boundary** | CLI/adapters/runner/join/export: symbol propagation, broker-time mapping, candle uniqueness, index collisions, missing data, debug | Mocked end-to-end actual-schema inputs, nondefault symbol, duplicate/empty ticks, missing zones, CSV/Parquet outputs; no lost/duplicated events |
| **TODO P0 — causal state** | Selected class: closed-history bootstrap, daily/bar propagation, trend and per-zone engagement; remove bar/row loops | Existing state/where tests pass where consistent with MQL; investigate conflicts rather than weaken tests; prefix invariance, duplicates and group reset evidence |
| **TODO P0 — candidates** | BO/reversal/PB conditions, ordering, IDs, uniqueness, retained parents/windows | Exact ordered MQL candidate fixtures; thresholds and offsets0/1/5/6; repeated penetration/fill; no artificial final-bar close |
| **TODO P0 — attempts/outcomes** | Gates, audit/submission, quotas, accepted pending, fill/cancel/reject and callbacks | Gate rejection consumes no attempt; rejected submission consumes bar/reversal quota; only PB fill consumes PB quota; duplicates/callback races deterministic |
| **TODO P1 — management** | Native risk/margin fixture boundary, RF/SL, PB TP, conflict close, operational safety | Exact MQL gate reasons, quote sides, accepted/rejected modifications and scoped flatten outcomes; explicit coverage of M1–M8 without silently fixing reference behavior |
| **TODO P1 — reporting** | Ordered events, summary actions, optional state and export schemas | Candidate/attempt/accept/fill counts separated; stable multiplicity/order after save/load; no fabricated position/PnL columns |
| **TODO P2 — optimization/parity** | Profile correct pipeline, reduce allocations and compare MQL traces | Record source/input hashes, versions, timings, peak memory and first mismatch; exact discrete outputs and bounded price error; no benchmark from a different implementation |

### Verification requirements

Use deterministic local fixtures for state/calculations and mocked native outcomes/acquisition for orchestration. Compare exact enums, flags, counters, IDs, action semantics and event order; use `1e-9` for shared contract price comparisons and explicit native tick-size tolerances where needed. Do not soften strict thresholds to conceal mismatches.

Cover empty/singleton inputs, duplicate timestamps, multiple instruments/days, partial-day startup, gaps, final unclosed bar, line/reversed/disabled/merged zones, merge gap1.5, free space3, BO buffer1, target distance6, penetration0.20, equality at trend boundaries, multi-zone gaps preserving old latches, quotas, competing candidates, broker rejection, delayed fills, expiry versus actual cancellation, TP extension/restore/close/rejection, RF steps, daily/GROSS15/concurrency/margin boundaries, callback duplicates and session/restart.

Stored evidence in the latest `CURRENT_STATE.md`/`TEST_STATUS.md` sections reports 4 cache tests passing and 17 selected-class state/where failures after promotion. Earlier 18/34-pass results and the 0.607-second benchmark belong to an alternative implementation, not the selected class. This review does not rerun tests/MT5 or establish new runtime parity evidence.
