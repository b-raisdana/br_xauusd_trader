# XAUUSD robust MT5 strategy

Current source: [XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5](XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5), property version `2.20`. It replaces the former MVP EA, project `include/` modules and generated vectors/zones. `archive.zip` is historical material.

Last checked against the source on 2026-10-01.

## Build boundary

The source includes platform `<Trade/Trade.mqh>` and **`XauRobustLiveEnvelope.mqh`, missing from the working tree and archive.zip**. Only `ApprovedStrategyOnInit`, `ApprovedStrategyOnTick`, `ApprovedStrategyOnTradeTransaction` and `ApprovedStrategyOnDeinit` are defined here. Final platform event handlers and release functions belong to the missing dependency. A reproducible compile and complete release-guard audit require that matching file; no successful build or runtime validation is claimed.

## Input and output

- `InpRangesFile="ranges.csv"`: CSV columns date, lower, upper, priority, enabled, note. Broker dates use `YYYY.MM.DD`; priorities are normal/high. Only enabled values `false`, `0`, `no` and `off` (case-insensitive, trimmed) disable a row; other values enable it. Invalid dates/priorities or nonpositive bounds are logged/skipped. Reversed bounds normalize, zones use the source's low-only swap sort, IDs `R1...` are assigned before merging gaps strictly below 1.5, and merged IDs concatenate with `&`.
- Tester I/O uses `FILE_COMMON`; chart I/O uses terminal-local `MQL5/Files`. `#property tester_file "ranges.csv"` declares the resource. There is no generated daily-zone dependency.
- Output defaults: `XAUUSD_ROBUST_FINAL_journal.csv` and `XAUUSD_ROBUST_FINAL_summary.csv`; tester initialization deletes these logs.
- Initialization validates M15, hedging-account and volume compatibility, and requires current plus three closed native M15 bars.
- Release declarations default to disabled, login 0 and real-money confirmation false. Enforcement cannot be verified without the envelope; the filename does not establish live approval.

## Actual defaults

Assignments take precedence over adjacent comments describing earlier selected scenarios.

| Setting | Value |
|---|---|
| Explicit controls / reversal / pullback | true / true / true |
| Direct breakout / breakout Normal-only / reversal High-only | false / true / false |
| Base stop cap / target multiplier / lot | 6 / 1×actual R0 / 0.01 |
| PB / High reversal free-space minimum | 12 / 12; equality accepted |
| PB daily fills Normal / High | 2 / 10; High 0 means unlimited |
| Reversal daily fills Normal / High | 1 / 2 |
| High reversal stop expansion | 1.5×base R0; expanded R0 qualifies target |
| BO buffer / PB penetration / window | 1 / 0.20 / 5 observed bar transitions |
| One new order per candle | false |
| Session mode / preclose / position cap | ALL_FLAT / 5 minutes / 3 |
| Portfolio budget | GROSS_DAILY, 30% initialization balance; QA basis when enabled |
| Daily loss | 20% net realized below capital 300; optional override/QA bypass |
| Protection | Enabled; actual-R0 stages at 1R, 1.5R, 2R |
| Same-day fresh start / QA discovery / daily-loss override | false / false / false |
| Legacy profile | 4; used when explicit controls are disabled |

## Visible flow

1. Init: release preflight → configure CTrade/Magic 260911125 → capture balance → validate/load zones/session schedule → current day/bar → three closed-bar reference → native-open engagement → previous Bid/restart detection.
2. Tick: session safety → new bar → restart lock/flatten → trend → gap/engagement/reversal touches → PB management → profit protection → previous Bid.
3. New bar: age cycles → native shift1 close with old trend/zones → day change → current bar/reference → native-open engagement. Sticky trend and previous Bid survive day/bar changes; missing bars are not replayed.
4. Breakout: strict buffer/trend/engagement → ID → successfully close invalidated reversals → optional direct entry → filtered PB cycle.
5. PB: retain active parent, latch penetration, retry exact edge stop subject to native validity/risk, track ticket, expire/cancel. A recognized fill ends the cycle; a later BO can create another.
6. Deal callback body: Magic-filtered deal → comment/request metadata → position/fill counters/PB completion; exit → full-position net/gross accounting → usage/track update → daily-loss and pending-risk enforcement.

## State and limits

`g_raw_zones` holds inputs; `g_zones` holds daily geometry/engagement/quotas; `g_cycles` holds PB lifecycle; `g_requests` bridges requests to deals; `g_positions` holds position management. Scalars own day/bar/trend, accounting, session/restart and audit state. Restart discovery uses native history/exposure; exposure-free fresh start deliberately does not restore earlier quotas/losses.

`EndCycle` deactivates after requesting deletion without checking success. The visible deal callback filters Magic, not explicitly symbol, and assumes a non-partial full-position lifecycle for realized accounting. Envelope reconciliation is unknown. Initialization journal text still says 2.10 despite property 2.20.

## Python comparison

Python production uses `MarketState` with optional `ExecutionReplay`, configured through `--execution-config` or `ReplayConfig`. The visible source port includes continuous native-bar history, quota/risk/protection transitions, raw-zone row filtering, explicit containing-session windows and shared-state snapshots. Default Python mode is signals-only; candidate output is not evidence of native fills.

Remaining differences and acceptance work live in [MT5-Python.Divergence.md](../docs/todo/MT5-Python.Divergence.md). [Glossary CSV](../docs/State-Variables.Glossary.csv) and [glossary notes](../docs/State-Variables.Glossary.md) cover 143 visible declarations. Native execution outcomes, callback order, identity, numeric edge cases, broker schedule acquisition and the missing envelope still prevent an exact-parity claim. Python tests and the former MVP tests do not prove equivalent native results.

The current source hash is `b8bbf960e443c2fa8f2acab297b63d36f5a88473add5caf78eb403536f9ac923` (SHA-256). Compile and runtime evidence must identify this file, its matching envelope, settings and inputs together.
