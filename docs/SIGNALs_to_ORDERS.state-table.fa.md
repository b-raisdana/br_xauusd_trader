# Signal-to-Order State Table

Companion quick reference to [Signals to Orders](SIGNALs_to_ORDERS.md). Rows describe the documented EA behavior; source of truth: `mt5/MQL5/Experts/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5`. “No request” means no initial `CTrade` order call. Fill processing and ongoing order/position management are outside scope.

## Candidate paths

| Situation | Required conditions | State/action | Result |
|---|---|---|---|
| Reversal buy (`R-B`) | Trend-qualified zone touch; reversal enabled; daily/restart/session and profile gates pass; reversal fill allowance remains; position slot and optional candle slot available; valid levels and risk reservation | Claim the zone/direction/bar touch slot before most entry checks; use Ask for geometry and tracking | Submit fixed-volume `trade.Buy` market request (`price=0.0`) |
| Reversal sell (`R-S`) | Same reversal gates as buy | Claim touch slot before most entry checks; use Bid for geometry and tracking | Submit fixed-volume `trade.Sell` market request (`price=0.0`) |
| Direct breakout buy (`BO-B`) | Confirmed buffered close; `InpEnableDirectBreakout=true`; daily/restart/reversal-session, optional normal-zone-only, position, level, risk and optional candle-slot checks pass | Direct path is disabled by default; breakout can still create a pullback cycle when this path is disabled | Submit fixed-volume market `trade.Buy` (`price=0.0`); calculations use sampled Ask |
| Direct breakout sell (`BO-S`) | Same direct-breakout gates as buy | Same behavior; calculations use sampled Bid | Submit fixed-volume market `trade.Sell` (`price=0.0`) |
| Pullback buy (`PB-B`) | Eligible breakout creates a cycle; pullback remains enabled/permitted; cycle is unique for broker day + zone + direction and within its bar window; penetration reached; management gates pass | Wait until exact zone high is valid as a Buy Stop beyond current Ask by Stops Level | Submit `trade.BuyStop` at the exact normalized zone high, GTC |
| Pullback sell (`PB-S`) | Same pullback gates as buy | Wait until exact zone low is valid as a Sell Stop beyond current Bid by Stops Level | Submit `trade.SellStop` at the exact normalized zone low, GTC |
| Breakout with direct path disabled | Breakout signal qualifies for pullback creation | Record/manage pullback cycle; no direct market request | Not itself an order |

## Shared gates and outcomes

| Situation or condition | Reversal | Direct breakout | Pullback | State/action |
|---|---|---|---|---|
| Daily stop or restart lock active | Blocked | Blocked | Creation/placement blocked | No new request |
| Entry family disabled | `InpEnableReversal=false` blocks | `InpEnableDirectBreakout=false` blocks direct request | `InpEnablePullback=false` blocks cycle/entry | Other enabled paths are evaluated independently |
| Session cutoff | Reversal session gate | Uses reversal session gate | Pullback session gate | `SESSION_ALL_FLAT`: both blocked in default 5-minute pre-close window; `SESSION_PB_FLAT`: pullback only; `SESSION_BASELINE_CARRY`: these session entry blocks disabled |
| Live position cap reached | Blocked | Blocked | Blocked | `MVPHasLiveSlot` counts EA-magic open positions, not pending orders; default cap is 3. A recognized fill that exceeds the cap is handled separately by the fill callback. |
| Optional one-new-order-per-candle slot already claimed | Blocked | Blocked | Blocked | One global slot across entry families; claim occurs before `CTrade` and is not restored after request failure. Default is disabled. |
| Position/volume parameters | Fixed volume and valid symbol volume constraints required | Same | Same | `InpTestVolumeLot` is validated at initialization; no automatic lot reduction for risk or margin |
| Profile, priority, or free-space gate fails | Blocked | Optional normal-zone-only gate may block high-priority zones | Pullback permission/free-space gate may block cycle or entry | Directional free-space equality passes; only values strictly below threshold block. Explicit research controls default on. |
| No adjacent stop zone, `R0 <= 0`, or no qualifying target zone | Blocked | Blocked | Blocked | No fallback SL/TP is substituted |
| Portfolio cash-risk reservation fails | Blocked when risk mode is on | Same | Same | Invalid budget/inputs or failed native `OrderCalcProfit` also blocks; `OFF` skips reservation. Tolerance: remaining must be at least `-$0.01`, and new risk <= remaining + `$0.01`. |
| Margin precheck fails or reports low free margin | Not blocked by this check | Same | Same | Logged only; actual broker/platform request result determines acceptance |

## Quotas, cycles, and restart state

| Situation | Condition/state update | Consequence |
|---|---|---|
| Reversal touch is rejected after touch-slot claim | Slot is keyed by M15 bar, zone and direction and is claimed before most `SendReversal` restrictions | No second same-direction attempt for that zone in the same bar, including after profile, quota, risk, daily-state or execution rejection |
| Reversal quota available | Counts recognized fills, not touches or submitted-but-unfilled requests. Explicit controls: normal zone allows one fill unless high-only blocks it; high zone uses `InpHighReversalMaxPerDay`. Non-control MVP fallback is high-only with profile-dependent quota. | Eligible reversal may proceed; `SPACE15_HIGHSPACE_H2` additionally requires `$15` directional free space |
| Pullback quota available | Counts recognized fills. Explicit controls: normal zone uses `InpNormalPullbackMaxPerDay` (0 blocks); high zone uses `InpHighPullbackMaxPerDay` only when positive (0 means unlimited). Defaults: 2 normal, 10 high. | Eligible pullback may proceed |
| Duplicate pullback breakout | An active cycle already exists for the same broker day + zone + direction | Keep the existing cycle unchanged; do not restart it |
| Pending order disappears without recognized fill | Its cycle remains eligible | May retry the same exact edge, subject to current gates and stop validity |
| Same-day EA deal history or live EA order/position found at initialization | `DetectSameDayRestartFailClosed` sets `g_restart_lock`; history-selection errors count as prior-deal evidence | Restart maintenance attempts to delete EA orders and close EA positions, updates previous Bid, and skips normal evaluation. Lock clears on broker day change; prior quotas/trend/daily-loss state is not restored. |
| `InpAllowSameDayFreshStart=true` and no live EA exposure | Fresh-start exception permits initialization despite same-day deal history | Starts fresh in-memory state; does not restore old quota, trend or daily-loss state |
| Live release-envelope latch active | Emergency stop, account/permission/identity failure, external XAU exposure, kill-button or deinitialization emergency can latch | Runtime guard remains false; day change alone does not resume live EA; reinitialization is required. Strategy Tester bypasses this guard. |

## Price and request outcomes

| Item | Reversal | Direct breakout | Pullback |
|---|---|---|---|
| Entry price used for geometry | Buy Ask / sell Bid | Sampled Ask / Bid | Exact normalized zone edge |
| Request price argument | Market `price=0.0` | Market `price=0.0` | Zone high Buy Stop / zone low Sell Stop |
| Stop and target | Adjacent-zone stop with `InpRCapUSD` cap; first target zone meeting `InpTargetR0Multiplier * R0` | Normal R geometry | Normal R geometry |
| High-priority reversal geometry | Expanded stop distance using `InpHighReversalSLMultiplier` (default 1.5); target must satisfy multiplier against expanded R0 | — | — |
| Pullback edge currently invalid | — | — | Wait and retry unchanged exact edge; require fresh tick and distance >= `SYMBOL_TRADE_STOPS_LEVEL * _Point` |
| Expected accepted retcode | `DONE` or `DONE_PARTIAL` | `DONE` or `DONE_PARTIAL` | `PLACED` or `DONE` |
| API boolean/retcode indicates failure | Deactivate request metadata; no market retry queue | Same | Retain cycle for later retry; no pending ticket recorded |
| API indicates accepted/placed | Submission accepted according to checked retcode | Same | Same; does not prove a fill or position exists |

## References

| Decision | Source method |
|---|---|
| Reversal checks and market request | `SendReversal`; `ProcessDirectionalReversalTouches` |
| Pullback cycle and pending request | `CreatePullbackCycle`; `ManagePullbackCycles`; `CanPlaceExactStop`; `PlaceConservativePending` |
| Direct breakout request | `SendDirectBreakout`; `ProcessClosedBar` |
| Profile, quota and free-space rules | `MVPDirectionalFreeSpace`; `MVPPullbackAllowed`; `MVPReversalAllowed`; `AllowedReversalCountForZone` |
| Levels and risk reservation | `CalculateRBasedSLTP`; `CalculateExperimentalHighReversalSLTP`; `PortfolioRiskEvaluateNew` |
| Position and candle slots | `MVPHasLiveSlot`; `ClaimGlobalEntrySlot` |
