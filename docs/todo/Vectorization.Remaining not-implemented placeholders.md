# MT5/Python parity follow-up

Reviewed 2026-09-29 against [the replacement EA](../../mt5/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5) and current Python. The filename is retained for existing links; the former blanket placeholder list is obsolete. [Detailed differences](../Divergence%20Report%20-%20MT5%20vs%20Python%20vs%20Documentation.md) and [field inventory](../State-Variables.Glossary.csv) define the current evidence.

## Completed source capabilities

- [x] Python emits BO/reversal/PB candidates and per-zone engagement; signals are no longer discarded placeholders.
- [x] Optional ExecutionReplay implements actions, risk/margin/concurrency, orders/positions, P&L, cancellation, fills and management. This marks implementation presence, not new-EA equivalence or a new test pass.
- [x] Result-manifest stages project order/position snapshots and join prior M15 context with cardinality validation.
- [x] Documentation and all 143 visible MT5 state/input declarations audited; no trading code changed.

## Remaining acceptance work

- [ ] **Reference delivery:** obtain matching `XauRobustLiveEnvelope.mqh`; inspect final callbacks, release/account guards and state; compile with all dependencies. Acceptance: reproducible compiler result and envelope state added to glossary. Do not activate trading to resolve this dependency.
- [ ] **Data/time/state parity:** use shared broker-time and native-bar fixtures. Compare exact three-bar bootstrap, overnight sticky trend, native-open engagement, previous-Bid continuity, midnight close and sparse/gapped bars. Acceptance: first differing field/event trace explained and resolved against designated source semantics.
- [ ] **Candidate/fill ownership:** align optional direct BO, successful-conflict-close prerequisite, slot default, fill-based reversal limits, PB fill ending its cycle, subsequent BO renewal and2/10 PB defaults. Acceptance: repeated/rejected candidates, same-tick ordering and postfill renewal agree in both paths.
- [ ] **Protection/accounting:** align signal-zone adjacent stop, actual-R0 target, High1.5 expansion,12-unit selectivity,30% portfolio default, postfill/pending reservations, native economics and R0-stage structural SL. Acceptance: exact boundary and rejected modification/cancel fixtures plus P&L reconciliation. Existing strict-PB TP behavior differs from the supplied body; do not silently assume it remains a required port feature.
- [ ] **Operational lifecycle:** compare containing-session modes/retries, same-day restart/fresh-start, rollover exposure and partial/repeated transaction behavior. Acceptance: matching native/replay event traces with unresolved exposure explicitly retained/reported.
- [ ] **CLI execution/reporting:** intentionally expose replay only with explicit economics/session configuration; repair final-day acquisition bound and debug contract; retain all events for reporting rather than relying on scalar last-position projections. Acceptance: offline end-to-end fixture proves chosen mode, complete interval and multi-position/short accounting without MT5 calls.

Existing Python tests against former scalar contracts remain useful regressions but cannot establish parity with this replacement. No real-money enablement is included in these tasks.
