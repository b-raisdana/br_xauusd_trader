# State variables glossary

Audited 2026-09-29 against [the replacement MQ5](../mt5/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5) and the active Python signals/optional replay paths. [CSV inventory](State-Variables.Glossary.csv) contains **143 unique rows: 52 inputs, 62 fields in five structs, and 29 globals/constants/objects**. This replaces the obsolete MVP inventory; it does not assert equivalent state transitions.

## Scope

- Include every visible `Inp*`, `EA_MAGIC`, `trade`, `g_*`, and field of `RawZone`, `ZoneRuntime`, `PullbackCycle`, `RequestMeta`, `PositionTrack`.
- Exclude transient locals, platform CTrade internals and enum members. Locals can be Python counterparts without becoming inventory entries.
- The missing `XauRobustLiveEnvelope.mqh` prevents enumeration of envelope-owned state and verification of final event wiring. No missing code is inferred from declarations.
- Python scope: selected `the_strategy.py`, its called trend/engagement/signals/actions/cache helpers, optional `ExecutionReplay`, its called package domain helpers and shared zone/models. An unused scalar helper is not evidence of active behavior.
- Default CLI and optional replay differ: the CLI supplies no `ReplayConfig`. Replay-only counterparts do not imply CLI execution.

## CSV contract and evidence

UTF-8 CSV; original six columns remain in order, followed by `Parity Verdict`, `Update Flow / Difference`, and `MT5 Write Functions`. Standard quoting, one header, one row per scoped name.

| Column | Interpretation |
|---|---|
| MT5-Name | Exact current declaration or qualified struct field |
| Py-Difference | Closest active representation; an analogue is not equivalence |
| MT5 Used as Input | Direct source-read locations, including logging and array/field accesses |
| MT5 Modifies the Value | Initialization, direct assignment/update/resize and identified sort/merge reference mutation anchors |
| Py Used as Input / Py Modifies the Value | **Function/class review anchors**, not exhaustive expression-level access indexes; inspect named lifecycle functions with the row's flow explanation |
| Parity Verdict | ABSENT: no corresponding active state/control; PARTIAL: related representation with caveats; DIFFERENT: identified update/semantic mismatch |
| Update Flow / Difference | Initialization, mutation/reset/lifecycle and Python difference |
| MT5 Write Functions | Owning functions for explicit writes; declaration-only entries are identified |

References use repository-relative `path:line,line; path:line`, sorted and deduplicated. `NONE` means no explicit access; `NOT_IMPLEMENTED` means no mapped Python state/control. Read-modify-write belongs in both MQL columns; declarations initialize globals/inputs but struct declarations are not runtime writes. Array rows cover member updates; struct field rows include `arr`/`out` aliases in zone merging. Whole-record copies transport all fields and are discussed in lifecycle text rather than expanded into invented field expressions. Platform object method internals are unavailable; `trade` mutation anchors include configuration, while native request operations appear as object uses.

Unlike the retired glossary contract, the Python columns intentionally give review anchors rather than claiming a complete alias-sensitive read/write index. Each mapped row identifies the functions to inspect and states its transition difference; matching locations in both columns do not mean every function both reads and writes every mapped field. MQL locations are an aid to source review, not proof of native runtime ordering.

## Findings

- **62 DIFFERENT, 25 PARTIAL, 56 ABSENT; no full-parity verdict.** Absence includes MT5-specific native identity/telemetry/release controls, not only missing trading logic.
- Trend references use exactly three native closed bars across days in MT5; Python uses available preceding observed same-day bars and resets daily trend.
- MT5 previous Bid survives bar changes and engagement seeds from native open. Python resets previous Bid at bar starts and seeds from first observed tick.
- MT5 reversal_usage is an enum changed on fill/exit; Python's same-name field counts attempts. MT5 has a separate fill counter and per-side signal-bar stamps.
- MT5 PB fill ends its cycle; Python clears pending/penetration but retains the window. Static opening cooldown is independent of replay fills. Normal/High caps are2/10 versus1/unlimited.
- Requested risk anchor, actual fill, immutable R0, sticky R stage, desired SL and retry state are distinct MT5 concepts; Python does not reproduce that management model.
- Input rows expose actual assignments, including12-unit filters and30% risk budget, rather than inconsistent adjacent comments.

See [the divergence report](Divergence%20Report%20-%20MT5%20vs%20Python%20vs%20Documentation.md) for phase ordering, defaults and missing-envelope limitations. Declaration coverage, CSV schema/uniqueness and source-reference ranges are checked without executing either trading engine. Static correspondence is not runtime parity.

Validation result: all 143 declarations covered exactly once; 1,903 cited line occurrences exist and match MQL identifiers or Python function/class anchors; 34 local links in changed Markdown resolve; `git diff --check` passes. Audited MQ5 SHA-256: `b8bbf960e443c2fa8f2acab297b63d36f5a88473add5caf78eb403536f9ac923`. These checks validate the documentation's structure and references, not semantic equivalence or broker outcomes.

## Prior inventory disposition

Every one of the 73 prior glossary rows is accounted for below. These are migration references, not additional current MQ5 declarations; successor transitions are detailed in the CSV. Removed telemetry does not imply that journal events are equivalent stored state.

| Prior name | Current disposition |
|---|---|
| `g_time_basis_probe_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_execution_projections` | g_requests / g_positions; native deal-driven model replaces projection records |
| `g_execution_bindings` | RequestMeta.comment / PositionTrack.position_id and position_ticket; no binding file |
| `EXECUTION_BINDINGS_FILE` | Removed; native comment/request metadata instead of persisted binding file |
| `ORDER_AUDIT_FILE` | Replaced by InpJournalFile / InpSummaryFile CSV outputs |
| `g_market_state` | Split across scalar globals, g_zones and g_cycles |
| `g_current_bar_time` | g_bar_time |
| `g_event_loop_ready` | Removed; initialization return plus day-valid/restart/session gates; envelope unknown |
| `g_event_loop_failure_reported` | Removed; no equivalent failure-log latch in visible body |
| `g_breakout_candidate_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_reversal_candidate_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_pullback_candidate_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_tester_attempt_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_tester_accept_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_tester_reject_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_request_sequence` | Removed; MakeComment uses type/day/zone/side, not request sequence |
| `g_event_sequence` | g_event_seq |
| `g_daily_loss_locked` | g_daily_stop |
| `g_operational_lock` | g_restart_lock / g_session_preclose_active; different reset semantics |
| `g_session_cancel_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_session_close_count` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_session_zero_exposure` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_restart_lock` | Retained name; now native history/exposure detection with fresh-start option |
| `g_max_open_positions` | InpMaxLivePositions is a configured cap, not observed maximum telemetry |
| `g_gate_rejections` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_final_net_realized` | g_daily_realized_net; daily state, not deinit summary cache |
| `g_final_gross_loss` | g_daily_realized_gross_loss; daily state, not deinit summary cache |
| `g_invalid_price_rejections` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_other_broker_rejections` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_protection_modifies` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_protection_modify_rejects` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_sl_loosen_violations` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_tp_extensions` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_tp_restores` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_tp_market_closes` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_tp_modify_rejects` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_tp_close_rejects` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_breakout_conflict_closes` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_symbol_spec_emitted` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_attribution_attempts` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_attribution_accepts` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_attribution_rejects` | Removed diagnostic/counter state; no equivalent stored variable in supplied body; envelope unavailable |
| `g_runtime_requests` | g_requests / g_positions; new metadata/management fields |
| `XauMarketCoordinator.broker_day` | g_day_key |
| `XauMarketCoordinator.bar_id` | g_bar_time |
| `XauMarketCoordinator.day_active` | g_day_valid; zone availability, not same contract |
| `XauMarketCoordinator.bar_active` | No separate flag; g_bar_time/init control flow |
| `XauMarketCoordinator.bar_open` | Native iOpen local; no stored global open |
| `XauMarketCoordinator.last_bid` | g_prev_bid |
| `XauMarketCoordinator.last_ask` | No global previous Ask |
| `XauMarketCoordinator.breakout_sequence` | g_breakout_seq |
| `XauMarketCoordinator.trend` | g_trend / g_ref_high / g_ref_low |
| `XauMarketCoordinator.zones` | g_zones / ZoneRuntime fields |
| `XauMarketCoordinator.pullbacks` | g_cycles / PullbackCycle fields |
| `XauMarketCoordinator.reversal_keys` | ZoneRuntime.last_reversal_buy_signal_bar / last_reversal_sell_signal_bar |
| `XauMarketCoordinator.attempted_bars` | g_last_new_order_bar; optional physical-bar slot |
| `XauTrendReferenceState.trend` | g_trend; persists across days |
| `XauTrendReferenceState.count` | Removed; UpdateTrendReference requires exactly 3 native bars |
| `XauTrendReferenceState.highs` | CopyRates local array ? g_ref_high; no persisted history array |
| `XauTrendReferenceState.lows` | CopyRates local array ? g_ref_low; no persisted history array |
| `XauDailyZoneSignalState.zone` | ZoneRuntime geometry/identity/priority |
| `XauDailyZoneSignalState.buy_engaged` | ZoneRuntime.engaged_buy |
| `XauDailyZoneSignalState.sell_engaged` | ZoneRuntime.engaged_sell |
| `XauDailyZoneSignalState.reversal_usage` | ZoneRuntime.reversal_usage enum + reversal_fill_count; not attempt count |
| `XauDailyZoneSignalState.pullback_fills` | ZoneRuntime.pullback_fill_count |
| `XauPullbackWindowState.parent_breakout_id` | PullbackCycle.parent_breakout_id |
| `XauPullbackWindowState.zone` | PullbackCycle.zone_id / zone_low / zone_high / day_key |
| `XauPullbackWindowState.direction` | PullbackCycle.buy |
| `XauPullbackWindowState.bar_offset` | PullbackCycle.valid_bar_no |
| `XauPullbackWindowState.active` | PullbackCycle.active; ends on fill |
| `XauPullbackWindowState.penetration_latched` | PullbackCycle.penetration_latched |
| `XauPullbackWindowState.pending_active` | PullbackCycle.order_ticket plus OrderSelect; native identity, not bool |
| `XauPullbackWindowState.sequence` | Removed; no per-cycle emitted-candidate sequence |
