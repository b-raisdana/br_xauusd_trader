# Divergence Report: MT5 vs Python vs Documentation

## Scope and conclusion

Source audit dated 2026-09-29. The Leader-designated replacement is [XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5](../mt5/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5). The former MVP/include/generated source and its test claims do not describe this EA. Existing documentation moves/deletions are preserved; [the glossary](State-Variables.Glossary.csv) now resides directly under `docs/`.

**Python and the new EA are not equivalent.** Python now has causal state, reversal/pullback candidates and an optional execution replay, making the old blanket placeholder claims obsolete. The CLI does not enable replay; replay itself retains different lifecycle, quota, risk and protection rules.

**The supplied EA is incomplete:** final include `XauRobustLiveEnvelope.mqh` is absent from the working tree and `mt5/archive.zip`. Final platform callbacks, account/release guards, emergency handling and reconciliation cannot be audited. Only `ApprovedStrategyOn*` bodies are visible. No successful compile or runtime parity is claimed. `<Trade/Trade.mqh>` is a separate standard platform dependency.

This review documents source behavior without changing strategy code or trading rules. Deleted Rules/Decisions/test reports are not recreated or treated as current evidence.

## Reachable Python flow

Sources: [entry point](../src/application/xauusd_trading_strategy_1_vector/__main__.py), [runner](../src/application/xauusd_trading_strategy_1_vector/runner.py), [strategy](../src/application/xauusd_trading_strategy_1_vector/the_strategy.py), [signals](../src/application/xauusd_trading_strategy_1_vector/signals.py), [replay](../src/application/xauusd_trading_strategy_1_vector/replay.py).

1. CLI → `asyncio.run(main)` → zone loader → tick/M15 fetches → floor bar time/normalize broker_day → runner. Current acquisition end is **last zone day + two hours − epsilon**, not next midnight. Candle timestamps are explicitly UTC; this path provides no broker-calendar conversion. Tick conversion now forwards requested symbol.
2. Runner enters config contexts and saves daily tick/candle artifacts through `ResultFilesManifest`. Strategy reads these artifacts, partitions broker/symbol, rejects decreasing timestamps and requires unique covering M15 candles. Daily state initializes independently.
3. `_process_bar_boundaries` reads candle opens and gathers only preceding observed same-day candle extrema, up to `TREND_POINTS_N=3`; bootstrap/unobserved history is excluded. `update_trend` reduces references and forward-fills threshold events per day.
4. Per-zone cumulative engagement → BO candidates/window-opening snapshots → unique reversal candidates → signals-only PB scan. BO close comes from the last observed tick before the next same-day bar. Final/day-boundary closes are not emitted.
5. Only with caller-supplied `execution=ReplayConfig(...)`: `generate_actions` calls one `ExecutionReplay` per stream, retained across days. `_roll` → session/restart lock → pending/SL/TP settlement → daily lock/cancel/flatten → management → BO submissions → PB evaluation → reversal/PB submissions → quote/snapshots/pruning. Economics and acceptance are injected offline assumptions, not terminal outcomes.
6. Manifest stages join the **previous** M15 candle with `validate="many_to_one"`, project orders/positions, export and report. Collections preserve multiple records, but scalar projections take the **last** snapshot and `action` takes the first action.

The CLI passes no execution configuration, leaving action/order/position outputs unexecuted despite candidate generation. `--backtest` feeds scalar position fields/Bid into vectorbt using independent default cash/fees/slippage; it does not enable replay, supply direction-aware short orders, or preserve a multi-position execution ledger. `debug` is accepted/passed but does not branch in the current runner.

## Detailed comparison

MQ5 anchors are functions in the replacement file. Python anchors are in the active package; optional replay behavior is distinguished from default CLI behavior.

| Area | New MQ5 body | Current Python / verdict |
|---|---|---|
| Modes | Disabled/demo/live declarations; missing envelope owns final wiring | Signals-only CLI and opt-in offline replay; no native reconciliation. Different scope; reference delivery incomplete |
| Zones | `LoadAllRawZones`: six-field CSV; disabled/invalid rows skipped; broker YYYY.MM.DD; missing daily zones mark day invalid | `ZoneCache` validates input schema, filters Enabled, date-only cache, missing day empty. Different failure policy |
| Merge/IDs | Low-only sort; gap<1.5; High dominates; premerge R IDs concatenate with & | low/high sort; same merge geometry; postmerge YYYY-MM-DD:R IDs. Identity/tie ordering differ |
| Bootstrap | `UpdateTrendReference`: exactly native shifts1–3, including prior day; four bars required at init | Only preceding observed same-day bars, first bar count 0. Different |
| Sticky trend | No day reset of g_trend; threshold update after new bar | New daily state; ffill within day. Overnight/bootstrap differ |
| Bar/day order | `ProcessNewBar`: age cycles → old close → day change → new reference/open | Daily partition drops cross-day close; old observed tick Bid used as close. Midnight/sparse/gapped bars differ |
| Previous Bid | Persists across bar/day; updated at end or locked return | Engagement/reversal replace previous Bid with current Bid at bar start. First-tick crossings suppressed |
| Engagement | Inclusive native-open seed, then directional crossings; multi-gap destination-only new latches | First observed tick containment, not bar_open; per-zone cumulative OR. Opening behavior differs; latching otherwise similar |
| Reversal | Updated UP/upward low touch→SELL; DOWN/downward high touch→BUY; no multi-gap; per-bar/zone/side claim before gates | Same predicates/dedup given equal inputs; differing trend/previous quote means no overall parity |
| Reversal quota | `AddPositionTrack` counts real fills Normal 1/High 2; usage enum unused/active/consumed changes on fill/exit | Replay reversal_usage counts prepared attempts, including rejected sends. Same-name state has different meaning |
| Global bar slot | `ClaimGlobalEntrySlot` optional, default off; enabled slot uses physical current bar before send | Always enforced on candidate bar; BO old bar versus reversal/PB current bar. Different |
| BO execution | Strict ±1 buffer/old trend; BO#01 IDs; invalidated reversal close must succeed before PB; direct entry default off | BO1 IDs; precomputed windows independent of close acceptance; replay submits BOs. Different |
| PB parent | Active parent retained; fill ends cycle; later BO can create next cycle | Static five-bar opening cooldown ignores actual fills; active window survives fill. Different renewal ownership |
| PB penetration/window | ±0.20 inclusive; offset starts 1, expires after configured 5 new-bar transitions | Same default threshold and1–5 window; hard-coded timing. Partial |
| PB fill | Count fill, deactivate cycle, clear ticket | Count fill, clear pending/penetration, retain active window; may rearm same parent. Different |
| PB quota | Explicit Normal 2/High 10 fills; High 0 unlimited | Normal 1/High unlimited; CLI has no fills. Different |
| Pending lifecycle | Exact native stop validity then risk/send; ticket/disappearance retry; deletion requested on expiry | Synthetic submit/fill/cancel with injected acceptance. Rejected cancel retains pending; EA EndCycle deactivates even if delete fails. Different |
| Selectivity | PB gap≥12; High reversal gap≥12; Normal reversal lacks that filter; absent neighbor filter returns DBL_MAX | All families gap>3; absent neighbor fails. No matching profile/family toggles |
| Initial stop | Adjacent zone relative to signal zone, base cap 6; High reversal expands base R0×1.5 | Nearest qualifying boundary relative to candidate price, cap 6; no expansion. Different |
| Initial TP | Directional target distance≥actual R0×multiplier (default 1), including expanded High risk | Target distance≥fixed 6. Different when actual R0≠6 |
| Price anchors | Reversal request Ask/Bid, PB edge; stores requested anchor separately from actual fill | Preparation uses candidate Bid/old close/edge; market fill Ask/Bid; protection anchors fill. Different |
| Risk budget | Default GROSS_DAILY 30% initialization balance; OFF/NET/GROSS options, pending reservation enforcement and postfill overflow response | Fixed15% of configured 200/300; pre-entry gate, no matching postfill policy |
| Concurrency/lot | Configurable3/0.01 defaults; postfill closes newest on overflow | Fixed0.01; max3 at 200 or5 at 300; no identical overflow response |
| Daily loss | Native full-position net at tracked exit;20% below 300, optional override/QA bypass; cancel cycles | Simulated close P&L; fixed 20% below 300, sticky lock and cancel pending. Partial accounting/timing match |
| Protection | Sticky1R/1.5R/2R stages: actual-fill cost BE; requested-anchor +0.5R; confirmed structure trailing and retries | Fixed6-unit stair steps from fill/simulated costs; no matching stage/pivot/retry state |
| PB TP | No strict PB extension/restore manager in visible body | Replay extension/restore/close and opposing-reversal blocking remain implemented. Python-only relative to visible body |
| Session | Native containing session; ALL_FLAT default, carry/PB-only alternatives; preclose flag false outside session; repeated close attempts during cutoff | Injected end per date; sticky lock until day reset; flatten all. Different |
| Restart | Native same-day Magic history/exposure; optional exposure-free fresh start; next day unlock | Explicit restart_days only; no native discovery/reconstruction |
| Day exposure | Cancels cycles/resets daily zones, loss/slots; day change itself does not flatten positions; trend persists | `_roll` cancels pending/closes positions, fails on unresolved exposure, resets coordinator/counters |
| Transactions | Visible DEAL_ADD callback filters Magic, not explicitly symbol; full-position/non-partial assumption | Per-stream synthetic IDs/outcomes, no native tickets/partial-deal projector; envelope unknown |
| Audit | Native journal/summary, chart objects, retry/session telemetry | Manifest action/event/state snapshots; different diagnostic state |

## Defaults and reference caveats

- Read assignments, not scenario comments: ReversalHighOnly=false; PB/High reversal free space12 despite comments saying15; Normal PB2 despite selected1; High PB10; portfolio30%. Property version 2.20 differs from initialization journal text 2.10. Comments establish neither performance nor approval.
- Missing envelope behavior is unknown. It cannot be presumed to supply tested account guards, callbacks or reconciliation, and its variables cannot be inventoried.
- `EndCycle` attempts deletion but does not check success before deactivation. The old report's claim of logging-only expiry is obsolete.
- `ApprovedStrategyOnTradeTransaction` accumulates full-position net on tracked exit; `FindPositionTrack` matches identifier without requiring active. Partial/repeated exits need native fixtures; no idempotence claim is justified.
- New-bar `UpdateTrendReference` return is ignored, unlike init; short history reads can retain old references. Missing bars use native shift1 values tagged with stored prior bar time, without replaying intermediate bars.
- `HandleDayChange` runs after prior-close processing, preserves trend/previous Bid and does not itself close positions. That differs from both the former EA report and Python replay.
- Margin precheck functions explicitly log only. Native acceptance, portfolio gates and offline margin calculations are distinct boundaries.
- A parsed entry deal without matching active request metadata is tracked with default zero requested price/SL/TP/R0. Profit protection skips nonpositive R0; metadata recovery by an unseen envelope cannot be assumed.

## Documentation and validation

The glossary is rebuilt against every visible global, all fields of RawZone/ZoneRuntime/PullbackCycle/RequestMeta/PositionTrack, every declared input and EA_MAGIC. Each row gives read/write review anchors and lifecycle/verdict information. Obsolete MVP variables are removed from the current inventory; Git history retains them. See [glossary method](State-Variables.Glossary.md).

The old report's missing-candidate, all-null-action, unused-candle, symbol-propagation and unvalidated-join claims no longer describe the opt-in pipeline. Historical test results remain historical; they do not validate this source revision or the replacement EA. Old scalar contracts are not an independent oracle for this EA.

This documentation-only review validates inventory coverage, CSV shape/unique names, cited paths/line ranges and changed-document link/diff hygiene. It runs no strategy, backtest, terminal or broker connection and changes no implementation. Missing envelope blocks full MT5 inspection/build; static matches do not constitute runtime parity.

Follow-up acceptance: supply matching envelope and compile; align explicit defaults, broker time/zone identity and lifecycle semantics; compare first differing state/event at bootstrap, midnight, sparse bars, gaps, rejected sends/deletes/modifications, fills and restart; verify accounting and intentionally enable replay in any execution-mode integration. These remain implementation work, not completed parity claims.
