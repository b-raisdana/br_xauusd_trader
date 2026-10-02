# MT5 / Python divergence and acceptance

Updated 2026-10-02. Objective: identical signals, positions and corresponding temporary/internal state for identical ordered inputs. Reference: [XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5](../../mt5/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5), replacing the former MVP, Include and Generated source set. Python now ports visible strategy transitions; **exact native runtime parity is not yet established**. This file is the consolidated implementation comparison and remaining-gap tracker.

## Reference boundary

`XauRobustLiveEnvelope.mqh` is missing from the repository and `mt5/archive.zip`. Final event handlers, release/account guards, emergency handling and reconciliation cannot be compiled or audited. `<Trade/Trade.mqh>` is a separate standard platform dependency. No successful native build, matching native trace, profitability or live readiness is claimed.

## Current Python flow

1. [CLI](../../src/application/xauusd_trading_strategy_1_vector/__main__.py) loads zones, requests complete zone days and 30 days of prior M15 history, derives broker-calendar day labels and invokes the runner. Three actual closed M15 bars are required; production never synthesizes bootstrap candles. Tests explicitly supply synthetic history.
2. [Runner](../../src/application/xauusd_trading_strategy_1_vector/runner.py) persists daily ticks and available preceding candles through `ResultFilesManifest`. Unique covering native M15 bars and chronological ticks are validated per broker/symbol.
3. [MarketState](../../src/application/xauusd_trading_strategy_1_vector/market.py) persists across daily partitions. Session safety precedes new-bar processing. New bar ages cycles, processes native shift1 close with old trend/zones, changes day, assigns bar/reference and seeds engagement from native open. Trend and previous Bid persist across days. Missing bars are not replayed.
4. Restart guard precedes trend, directional gap/engagement/reversal touches, PB handling and protection. Reversal side/bar claims precede entry gates. BO IDs use `BO#01`; closing invalidated reversals must succeed before direct entry/PB creation.
5. [ExecutionReplay](../../src/application/xauusd_trading_strategy_1_vector/replay.py) owns optional order/fill/position, quota, risk and protection transitions. Simulated settlement is performed before current-tick signal processing, after new-bar processing; that ordering is an explicit replay assumption, not proven native callback ordering.
6. Manifest stages join previous M15 context and project/export state and event collections. Scalar projections retain only the last order/position snapshot and first action; use collections for multiple positions. `mt5_state` contains shared state using MQ5 names. Tickets remain synthetic.

Signals-only remains the default. Supply CLI `--execution-config <json>` or programmatic `execution=ReplayConfig(...)` for positions. `ReplayFileConfig` requires explicit economics and accepts EA inputs, initial balance and restart days. `--backtest` defaults off and requires execution configuration; vectorbt remains a separate report with independent accounting assumptions, not the parity oracle. `debug` remains accepted but unused by the runner.

## Implemented source transitions

| Area | Current implementation |
|---|---|
| Inputs | Frozen `RobustInputs` mirrors visible trading defaults: direct BO off; reversal/PB on; Normal/High PB 2/10; High reversal 2; High stop multiplier1.5; PB/High-R space12; cap3; volume0.01; GROSS budget30%; optional order slot off |
| Zones | Bounds normalize; MT5 low-only swap sort; R IDs assigned before gap<1.5 chain merge; High dominates; merged IDs concatenate with & |
| Trend | Exactly three native closed candles; strict threshold changes; sticky across days; enum NONE0/UP1/DOWN-1 |
| Engagement | Native open seed; previous Bid continuity; directional crossing latches; multi-zone gap only engages destination zone |
| BO/PB | Strict buffer1; old close trend; invalidated-R close acceptance gates continuation; retain active parent; offset1 through configured window; inclusive0.20 penetration; fill ends cycle; later BO can renew |
| Pending | Exact edge, stop-distance retry, disappearance retry, fill counts; EndCycle deactivates despite rejected deletion and retains ticket |
| Quotas | Actual fills, separate reversal usage and count; Normal/High PB limits2/10, High0 unlimited; Normal R1/High R2; optional bar slot claimed before broker attempt |
| Initial protection | Adjacent zone relative to signal zone; base cap6; High R expands base risk1.5; target qualifies against actual R0; requested anchor distinct from fill |
| Management | Sticky1R/1.5R/2R stages; known-cost fill BE; requested anchor half-R; latest two confirmed pivots from shifts2..100; desired SL/retry flags; no Python-only TP extension/restore or strict-PB reversal blocker |
| Accounting/risk | Initial-balance/QA basis; OFF/NET/GROSS modes; pending reservations; rejection prechecks; postfill cap/risk closure; close-time daily net/gross; daily guard/QA latch |
| Day/session/restart | Day resets zones/quotas/loss/order slot and cancels cycles without flattening positions; cutoff cancels once and retries targeted closes; restart uses explicit days and exposure-aware fresh-start setting |
| Snapshot | Zone/cycle/request/position fields, request activation, requested and actual prices, immutable risk, stage/retry, fill ordinals and stacked-PB flag; strict recursive first-difference comparator |

Legacy vector helpers remain importable for isolated callers/tests, but production `process_tick_data` uses `MarketState`. Their old daily-reset/cooldown contracts are not a second parity implementation. `generate_actions` is explicitly a supplied-candidate compatibility replay: it rejects mismatched tick/state indexes and conflicting replay configuration, and clears `mt5_state` to `{}` because it has no native candle history or canonical signal state.

## Remaining differences and acceptance requirements

| Boundary | Outstanding work/evidence |
|---|---|
| Complete EA | Supply matching envelope, compile on MT5, record build and input hashes |
| Broker outcomes | Replay uses supplied profit/margin/cost formulas and acceptance with quote-side full fills. Native slippage, partial deals, retcodes, asynchronous callback order, stop-trigger scheduling, net commission/swap/fee and symbol specifications require recorded native outcomes or a matching terminal adapter |
| Native identity | Replay IDs are synthetic; position identifier/ticket distinction and Magic-only cross-symbol callback behavior require explicit identity/event normalization |
| Session state | Explicit session_windows now supply containing start/end, gaps, overnight windows, native-format keys/from/to and per-position carry audit. Native schedule acquisition remains external; legacy per-date ends assume midnight start |
| Restart/reconciliation | Explicit restart_days is not native Magic history/exposure discovery; envelope projection/reconciliation unavailable |
| Input edge cases | CSV input now filters disabled/invalid rows using canonical dotted dates, allowed priorities and positive bounds before schema validation. Wrong CSV field counts still fail fast; native StringToDouble edge cases and Decimal price rounding need boundary vectors before claiming exact equivalence |
| Signals-only | Touch/window candidates do not prove executable signals without economics and broker outcomes. Use configured replay for execution acceptance comparisons |
| Telemetry/release | Raw notes are retained in the zone input frame; journal sequence/file/chart state, terminal object internals and missing-envelope release controls have no complete Python counterpart |
| End-to-end proof | Run both paths on identical ticks, native candles including bootstrap, broker calendar/sessions, zone rows and EA settings. Compare every signal, request, fill, position and corresponding state after each ordered callback/tick, with first differing timestamp/field. Do not substitute old scalar-oracle tests or this source audit for that evidence |

[State glossary CSV](../State-Variables.Glossary.csv) covers all143 current declarations; PARTIAL means implemented/related state with remaining native evidence, not proven parity. [Glossary notes](../State-Variables.Glossary.md) retain the retired inventory disposition. MQ5 SHA-256: `b8bbf960e443c2fa8f2acab297b63d36f5a88473add5caf78eb403536f9ac923`.

## Executable remaining gaps

| ID | State | Required change and acceptance |
|---|---|---|
| EXEC-01 | OPEN | Replace quote-side full-fill assumptions with an optional recorded native execution boundary: ordered submit/cancel/modify/close outcomes, actual fills, native identifiers, commissions/swaps/fees and profit/margin results. Keep synthetic economics explicitly labeled. Acceptance: replay native outcomes without inventing successful fills or costs; rejected and delayed outcomes preserve matching state. |
| EXEC-02 | OPEN | Reproduce native transaction scheduling relative to session handling, old-bar close, day reset, signal sends and protection. Current synthetic settlement runs after new-bar processing. Acceptance: fixtures cover same-tick pending trigger versus expiry/cancellation, immediate versus delayed callbacks, partial/repeated deals and position closure; compare state after each ordered event. |
| STATE-01 | OPEN | Complete request/position identity and metadata correspondence. Synthetic IDs differ from native position identifier/ticket; comments can collide; callback filters Magic without an explicit symbol filter. Acceptance: explicit mapping and callback fixtures, including missing request metadata and multiple same-zone positions. |
| CONFIG-01 | DONE (visible source) | RobustInputs now requires penetration>0 and 0<preclose_minutes<=60. Portfolio risk percentage, QA capital and daily-loss percentage checks apply only when their corresponding modes are enabled. Eighteen source-derived valid/invalid parameter cases pass; final envelope-specific restrictions remain REF-01. |
| NUM-01 | OPEN | Verify Python price normalization, floating comparison boundaries and account-currency risk against native NormalizeDouble/OrderCalcProfit/OrderCalcMargin. Acceptance: native boundary vectors at half-points, exact free-space/target/risk thresholds and both directions; no unexplained tolerance. |
| DATA-01 | PARTIAL | DONE: CSV loader applies MT5 disabled-value list, canonical dotted dates, normal/high priority validation, positive bounds, swap normalization and row-level invalid-row skipping; 20 regression cases pass. Remaining: native StringToDouble boundary vectors, malformed CSV field-count behavior and native broker-calendar/session acquisition. Acceptance: identical surviving zones/IDs and window state, including invalid rows and overnight gaps. |
| API-01 | OPEN | Audit every reachable public action/signal helper for stale semantics. Production uses MarketState, while legacy vector helpers and generate_actions accept externally prepared candidates. Acceptance: canonical calculation path and compatibility boundaries are explicit; supported public paths cannot silently claim parity while using old lifecycle rules. |
| TRACE-01 | OPEN | Complete field-by-field state coverage and native trace normalization. Validate all 143 glossary entries, clearly distinguishing shared trading state from native-only release/journal/chart state. Acceptance: no shared mutable field omitted; timestamps and identities normalized explicitly; strict comparison reports first timestamp/event/field mismatch. |
| REF-01 | EXTERNAL | Obtain matching XauRobustLiveEnvelope.mqh, currently absent from the repository and archive. Compile the complete EA and inspect final callbacks, release guards and reconciliation. Do not infer these behaviors from the visible ApprovedStrategyOn* bodies. |
| ACCEPT-01 | WAITING ON NATIVE EVIDENCE | Run both implementations with identical ticks, native candles/bootstrap, raw zones, settings, account state, symbol specifications and execution events. Record source/input hashes and compare every signal/request/fill/position/shared-state transition. Completion requires zero unexplained differences; Python-only tests or source inspection cannot close this item. |

Work order: close independently testable source/API/state gaps while building the recorded execution boundary; retain unresolved native requirements explicitly. Missing reference material does not suspend safe local work. No live deployment or real-money enablement is authorized by this task.


## Verification

The 2026-10-02 source audit corrected reversal invalidation to close in creation order and stop at the first rejection, pending cash risk to `max(0,-profit)`, and open-position risk to use tracked initial SL when the live SL is nonpositive. All five new cases failed before the fixes; the combined source-parity/execution/input/zone suite then passed 85 cases. Two additional compatibility-replay cases pass. The ratchet package entry point was corrected to `br_pre_commit.src.ratchet`; the ratchet passes when run with repository-root environment variables. Native callback/identity and complete-EA evidence remain open.

Final 2026-10-02 pre-commit run passes Ruff, formatting, the repository pytest hook and incremental ratchet. The previous ratchet failures are superseded by the corrected package entry point and current dependency state. Glossary validation reports 143 unique names, 4,001 in-range nonblank source references and no invalid anchors. `git diff --check` passes. This verifies the local batch, not native parity.

Regression coverage includes defaults, actual-R targets, High expansion, fill quotas, parent renewal, failed cancellation, overnight positions, requested-price anchors, native-open crossings, bootstrap rejection, session gaps/carry/cutoffs, raw-zone filters and strict first-difference reporting. These are Python/source-derived checks. No paired native execution result is available.
