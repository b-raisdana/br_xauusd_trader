# Divergence Report: MT5 vs Python vs Documentation

Audit updated 2026-09-30 against [XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5](../mt5/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5). The replacement EA supersedes the former MVP, Include and Generated files. The Python implementation now ports the visible strategy transitions; **exact native runtime parity is not yet established**.

## Reference boundary

`XauRobustLiveEnvelope.mqh` is missing from the repository and `mt5/archive.zip`. Final event handlers, release/account guards, emergency handling and reconciliation cannot be compiled or audited. `<Trade/Trade.mqh>` is a separate standard platform dependency. No successful native build, matching native trace, profitability or live readiness is claimed.

## Current Python flow

1. [CLI](../src/application/xauusd_trading_strategy_1_vector/__main__.py) loads zones, requests complete zone days and 30 days of prior M15 history, derives broker-calendar day labels and invokes the runner. Three actual closed M15 bars are required; production never synthesizes bootstrap candles. Tests explicitly supply synthetic history.
2. [Runner](../src/application/xauusd_trading_strategy_1_vector/runner.py) persists daily ticks and available preceding candles through `ResultFilesManifest`. Unique covering native M15 bars and chronological ticks are validated per broker/symbol.
3. [MarketState](../src/application/xauusd_trading_strategy_1_vector/market.py) persists across daily partitions. Session safety precedes new-bar processing. New bar ages cycles, processes native shift1 close with old trend/zones, changes day, assigns bar/reference and seeds engagement from native open. Trend and previous Bid persist across days. Missing bars are not replayed.
4. Restart guard precedes trend, directional gap/engagement/reversal touches, PB handling and protection. Reversal side/bar claims precede entry gates. BO IDs use `BO#01`; closing invalidated reversals must succeed before direct entry/PB creation.
5. [ExecutionReplay](../src/application/xauusd_trading_strategy_1_vector/replay.py) owns optional order/fill/position, quota, risk and protection transitions. Simulated settlement is performed before current-tick signal processing, after new-bar processing; that ordering is an explicit replay assumption, not proven native callback ordering.
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

Legacy vector helpers remain importable for isolated callers/tests, but production `process_tick_data` uses `MarketState`. Their old daily-reset/cooldown contracts are not a second parity implementation.

## Remaining differences and acceptance requirements

| Boundary | Outstanding work/evidence |
|---|---|
| Complete EA | Supply matching envelope, compile on MT5, record build and input hashes |
| Broker outcomes | Replay uses supplied profit/margin/cost formulas and acceptance with quote-side full fills. Native slippage, partial deals, retcodes, asynchronous callback order, stop-trigger scheduling, net commission/swap/fee and symbol specifications require recorded native outcomes or a matching terminal adapter |
| Native identity | Replay IDs are synthetic; position identifier/ticket distinction and Magic-only cross-symbol callback behavior require explicit identity/event normalization |
| Session state | Explicit session_windows now supply containing start/end, gaps, overnight windows, native-format keys/from/to and per-position carry audit. Native schedule acquisition remains external; legacy per-date ends assume midnight start |
| Restart/reconciliation | Explicit restart_days is not native Magic history/exposure discovery; envelope projection/reconciliation unavailable |
| Input edge cases | Python schema rejects malformed frames; MT5 logs/skips invalid CSV rows. Decimal price rounding needs native boundary vectors before claiming bit-for-bit NormalizeDouble equivalence |
| Signals-only | Touch/window candidates do not prove executable signals without economics and broker outcomes. Use configured replay for execution acceptance comparisons |
| Telemetry/release | Raw notes, journal sequence/file/chart state, terminal object internals and missing-envelope release controls have no complete Python counterpart |
| End-to-end proof | Run both paths on identical ticks, native candles including bootstrap, broker calendar/sessions, zone rows and EA settings. Compare every signal, request, fill, position and corresponding state after each ordered callback/tick, with first differing timestamp/field. Do not substitute old scalar-oracle tests or this source audit for that evidence |

[State glossary CSV](State-Variables.Glossary.csv) covers all143 current declarations; PARTIAL means implemented/related state with remaining native evidence, not proven parity. [Glossary notes](State-Variables.Glossary.md) retain the retired inventory disposition. MQ5 SHA-256: `b8bbf960e443c2fa8f2acab297b63d36f5a88473add5caf78eb403536f9ac923`.

## Verification

Source-derived regression tests cover defaults, actual-R targets, High expansion, quotas, parent renewal, failed cancellation, overnight positions, requested-price risk anchors, native-open crossings, bootstrap rejection and strict trace mismatch reporting. Full-suite and pre-commit results are recorded in [the active parity task](todo/vectorized-state.md); native parity remains pending.
