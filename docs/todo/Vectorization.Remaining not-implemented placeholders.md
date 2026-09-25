# Vectorization: remaining placeholders and MT5 equivalents

Audited 2026-09-24 against the working tree. The EA is [mt5/XAUUSD_MVP.mq5](../../mt5/XAUUSD_MVP.mq5), not `mt5/XAUUSD/_MVP.mq5`. **All three Python placeholders and all three unfinished connections below remain unfinished in the vectorized implementation. MT5 equivalents largely exist, but do not complete the Python TODOs.**

This is a source audit, not a new compile, Strategy Tester run or parity certification. MT5 execution requires the guarded tester path; `OnInit` rejects `InpEnableTrading=true`. Existing acceptance evidence is in [FINAL_TEST_REPORT.md](../FINAL_TEST_REPORT.md).

## Python status: NOT IMPLEMENTED

The three implementation placeholders remain:

| Location                                                                                                                                                                          | What is missing                                                                                                                                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [actions.py:17](C:/Code/XAAUSD-PAction-projectFolder/src/application/xauusd_trading_strategy_1_vector/actions.py:17) — `generate_actions`                                         | Always sets `action = None`. No candidate selection, risk checks, SL/TP calculation, or actionable orders.                                                                                          |
| [result_processing.py:58](C:/Code/XAAUSD-PAction-projectFolder/src/application/xauusd_trading_strategy_1_vector/result_processing.py:58) — `generate_order_management_columns`    | Generates synthetic IDs/timestamps only. Order type, direction, status, entry, SL and TP remain empty; no order lifecycle.                                                                          |
| [result_processing.py:105](C:/Code/XAAUSD-PAction-projectFolder/src/application/xauusd_trading_strategy_1_vector/result_processing.py:105) — `generate_position_tracking_columns` | Generates IDs for supposed fills, but does not track actual positions, size, entry price, P&L, protection, or closing. It also compares status with `"FILLED"` although the schema expects an enum. |

There are also **unfinished connections**:

- **Pullback execution feedback:** the signal function accepts feedback, but this directory contains no producer of actual fills/pending updates.
- **Signal output:** [process_tick_data](C:/Code/XAAUSD-PAction-projectFolder/src/application/xauusd_trading_strategy_1_vector/vectorized_strategy.py:69) omits reversal and pullback signals from its normal returned result.
- **Entry-attempt tracking:** `attempted_bars` is initialized but never updated or enforced.

`NOT_TESTED` means not manually tested once by the developer; the marker alone does not mean not implemented. The current schema represents order status as integer execution-enum values, so comparing it to the string `"FILLED"` is incompatible.

## MT5 status by item

| Python item | MT5 equivalent and status |
|---|---|
| Action generation | **IMPLEMENTED:** `ProcessTesterCandidates` (EA line 1121) checks candidate availability, prepares protected entries, audits and submits them through [XauRequests.mqh](../../mt5/include/XauRequests.mqh) and [XauTesterBroker.mqh](../../mt5/include/XauTesterBroker.mqh). |
| Order management | **IMPLEMENTED:** [XauExecution.mqh](../../mt5/include/XauExecution.mqh) maintains request projections and native order/position bindings; the EA processes submission, rejection, fill, modification, cancellation and close outcomes. |
| Position tracking | **IMPLEMENTED for native lifecycle, protection and realized accounting; NOT IMPLEMENTED as an equivalent per-tick position/P&L table.** The EA reads native identifiers, entry, volume and SL/TP, manages protection/closing, and calculates realized P&L from deals. No equivalent exported per-tick `position_unrealized_pnl` field is populated. |
| Pullback execution feedback | **IMPLEMENTED:** accepted submissions set pending state; `ApplyProjectOwnedNativeOutcome` (EA line 691) records fills and initializes TP state; `ApplyTesterPendingCancellation` (line 781) removes pending state. |
| Signal output | **IMPLEMENTED as direct consumption, not DataFrame output:** `ProcessCurrentEventLoopTick` (EA line 1248) passes close-bar breakouts and tick reversal/pullback candidates to `ProcessTesterCandidates`. Python still omits reversal/pullback signals from its public returned result. |
| Entry-attempt tracking | **IMPLEMENTED:** `CandidateAttemptAvailable` and `CommitPreparedEntryAttempt` in `XauRequests.mqh` use `RecordEntryAttempt` in [XauState.mqh](../../mt5/include/XauState.mqh). |

## MT5 calculations and references

### Actions, prices and risk

`ProcessTesterCandidates` processes candidates in array order. Close-bar breakouts are processed before tick candidates; `ProcessCoordinatorTick` appends reversals before pullbacks. This is sequential selection, not scored ranking.

The calculations in [XauContracts.mqh](../../mt5/include/XauContracts.mqh) use `BASE_R_USD=6`:

| Calculation | Current implementation |
|---|---|
| Initial Buy SL | Nearest zone whose high is strictly below entry; `SL=max(zone.high, entry-6)`. |
| Initial Sell SL | Nearest zone whose low is strictly above entry; `SL=min(zone.low, entry+6)`. Missing stop zone rejects entry. |
| Initial TP | Buy: nearest zone low at least 6 above entry. Sell: nearest zone high at least 6 below entry. Missing qualifying zone rejects entry. |
| Free space | Buy: `next_zone.low-current_zone.high`; Sell: `current_zone.low-previous_zone.high`. Require strictly `>3`; missing adjacent zone fails. |
| Cash risk | [XauNative.mqh](../../mt5/include/XauNative.mqh), `NativeCashRisk`: absolute native `OrderCalcProfit` from entry to SL at the symbol/volume. Existing positions with SL at/beyond entry in the profitable direction contribute zero exposure risk. |
| Portfolio gate | `realized_gross_loss + open_position_risk + pending_order_risk + proposed_risk <= capital*0.15 + 1e-9`. |
| Daily loss | For capital below 300, latch the lock when net realized P&L `<= -capital*0.20`; the lock remains until daily reset. |
| Volume/concurrency/margin | Fixed 0.01 lot; capital 200 allows 3 open positions, capital 300 allows 5; other capital values fail. Require native `OrderCalcMargin <= ACCOUNT_MARGIN_FREE` and valid directional SL/entry/TP ordering. |

**Scope discrepancy:** `PrepareCandidateEntry` applies free space to all three families, including Breakout; `RULES.md` explicitly names Reversal/Pullback for this gate. This audit records code behavior without changing or resolving the rule.

Breakout/Reversal use market orders; Pullback uses pending stops. `SubmitTesterPreparedEntry` sends market Buy at fresh Ask and Sell at fresh Bid with deviation 20 points, or a stop at the candidate's exact entry. SL/TP are attached at creation. Preparation uses candidate entry; the native market fill may differ and is recorded separately.

References: [MT5 stop/target calculations](../../mt5/include/README.md#risk-stop--target), [portfolio and safety](../../mt5/include/README.md#portfolio--safety), and [RULES.md](../RULES.md), sections 10–13: `FREE_SPACE_DEFINITION`, `FREE_SPACE_MINIMUM`, `INITIAL_STOP`, `INITIAL_TARGET`, `FIXED_LOT_AND_CONCURRENCY`, `DAILY_REALIZED_LOSS_GUARD`, `PORTFOLIO_RISK_BUDGET`.

### Orders, positions, P&L and protection

The EA creates `REQ-N` request IDs, writes an order audit, creates an execution projection, submits the order, and binds the native order ticket. Immediate fills and `OnTradeTransaction` callbacks correlate that order with its position identifier. `ProjectExecutionOutcome` records lifecycle status, fill/close price, SL/TP and transition time; rejected modifications preserve existing protection. Cancellation and close helpers send native requests.

[XauTesterRisk.mqh](../../mt5/include/XauTesterRisk.mqh), `LoadTesterRealizedRisk`, selects broker-day history, filters symbol/magic, groups by position ID, and sums `DEAL_PROFIT + DEAL_SWAP + DEAL_COMMISSION + DEAL_FEE`. Groups with an `OUT`/`OUT_BY` deal contribute to net realized P&L; negative group totals contribute their absolute value to realized gross loss. This is the implemented aggregation, not a separate partial-close accounting model or unrealized-P&L calculation.

`TesterPositionRiskFree` sums recorded commission/fee/swap costs, clamps cost to at least zero, and divides it by absolute native cash profit for a favorable 1 USD price move. `RF=entry+offset` for Buy and `entry-offset` for Sell. It uses recorded costs, not estimated future exit costs.

`ManageTesterProfitProtection` calls `ProfitProtectionStop`: favorable movement is `Bid-entry` for Buy or `entry-Ask` for Sell; `step=floor(favorable/6)`. At `step>=1`, proposed SL is `RF+(step-1)*6` for Buy or `RF-(step-1)*6` for Sell, only when tighter than current SL and valid against TP. Native acceptance determines whether protection changes.

`ManageTesterPullbackTp` checks strict closed-candle/current-candle direction at the 1 USD pre-zone crossing. If valid and another target zone exists, it proposes a one-zone TP extension; if strict movement subsequently fails, it restores initial TP or closes at market if price has already crossed initial TP. Operational safety cancels pending orders and flattens positions at session end or same-day restart; opposite reversals can also close on a valid breakout.

References: [MT5 main pipeline](../../mt5/README.md#core-pipeline-functions), [projection lifecycle](../../mt5/include/README.md#projection-lifecycle), [profit protection](../../mt5/include/README.md#profit-protection), [TP failure](../../mt5/include/README.md#pullback-tp-failure), and [RULES.md](../RULES.md), sections 9 and 12–14: `EXTEND_PULLBACK_TP`, `RISK_FREE_PRICE`, `PROFIT_PROTECTION`, `NATIVE_COSTS`, `SESSION_END_FLATTEN`, `RESTART_FAIL_CLOSED`.

### Pullback feedback and entry attempts

`EvaluatePullbackPrice` considers only bars `t+1` through `t+5`, with no pending order and available daily usage. Buy penetration latches at `Bid <= zone.high-0.20`, Sell at `Bid >= zone.low+0.20`; entry stays at zone high/low respectively. Accepted submission sets `pending_active`; a normal fill increments daily usage, clears pending and penetration, and keeps the parent window active. Normal zones allow one fill/day; High zones have no daily fill cap. Pending removal clears pending state; expiry deactivates the window. The EA also has a fill-recovery fallback that increments zone usage when normal window recording is unavailable.

`CandidateAttemptAvailable` rejects an already-used `candidate.bar_id`. After an actual submission attempt, `CommitPreparedEntryAttempt` records the bar whether accepted or rejected. Reversal usage increments on the attempt; Pullback daily usage increments on fill. Pre-submission risk rejection does not consume the attempt. A new broker day clears attempted bars. The key is the candidate bar ID: close-bar Breakout carries the just-closed bar ID.

References: [pullback window functions](../../mt5/include/README.md#pullback-window), [MT5 include reference](../../mt5/include/README.md) (`XauRequests.mqh` functions), and [RULES.md](../RULES.md), sections 7–8 and 13: `REVERSAL_USAGE_COMMIT`, `PULLBACK_CONSERVATIVE_ENTRY`, `PULLBACK_WINDOW`, `PULLBACK_MULTI_PER_BREAKOUT`, `PULLBACK_DAILY_USAGE`, `ONE_NEW_ORDER_PER_CANDLE`.

## Remaining vectorized work and completion criteria

- [ ] Implement `generate_actions`: select eligible candidates, apply confirmed risk/SL/TP rules, and emit typed requests; verify allowed/rejected cases and selection ordering against intended MT5 semantics.
- [ ] Replace synthetic order columns with execution-driven lifecycle projection, actual IDs, typed status, prices and timestamps; verify submission, rejection, cancellation, fill, modification and close transitions.
- [ ] Implement position state, volume/entry, directional mark price, realized/unrealized P&L, protection and closing using native costs/specifications and enum-compatible fill detection; verify lifecycle/accounting cases.
- [ ] Connect execution acceptance/fill/cancellation outcomes to pullback feedback in causal order; verify pending suppression, daily limits, penetration reset, expiry and multiple fills per parent.
- [ ] Include reversal/pullback signals in the public result and schema for empty/nonempty inputs; verify preservation through downstream processing.
- [ ] Enforce/update entry-attempt state across families; verify rejected attempted orders consume the bar, pre-submission rejection does not, and daily reset clears it. Explicitly test close-bar Breakout versus current-bar tick candidates.
