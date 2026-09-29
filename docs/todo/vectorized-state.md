# Vectorized state processing

Scope: active `src/application/xauusd_trading_strategy_1_vector/`. State calculations use pandas/NumPy batches; sparse candidate construction, PB feedback and optional execution replay use ordered loops. [Current MT5 comparison](../Divergence%20Report%20-%20MT5%20vs%20Python%20vs%20Documentation.md) supersedes old MVP equivalence claims.

## Implemented

- [x] Gather preceding observed same-day M15 extrema; cap configurable trend points(default 3), seed open from native candle and forward-fill trend within day.
- [x] Per-zone engagement via cumulative masks; unique reversal candidates; ordered BO candidates and parent-window snapshots; PB penetration/pending/fill feedback.
- [x] Per-stream optional replay preserves execution state across daily artifacts; rollover explicitly resolves exposure before replacing coordinator.
- [x] Manifest order/position projections consume snapshots. Actions are populated only with replay configuration.

## Remaining work

- [ ] **Reference alignment:** new EA retains trend/previous quote across days and uses exactly three native closed bars. Resolve bootstrap, midnight close, native-open engagement and sparse-bar differences with paired state fixtures.
- [ ] **Feedback ownership:** remove mismatch between precomputed opening cooldown and actual PB fills; new EA ends cycle on fill and requires a later BO. Prove renewal, expiry, rejected deletion and parent lineage at each event.
- [ ] **Usage/slots:** match fill counters versus attempts and the EA's default-disabled one-order slot. Verify rejected submissions do not masquerade as fills.
- [ ] **Execution contract:** align risk/targets/R0 protection and session/restart lifecycle per [acceptance tasks](Vectorization.Remaining%20not-implemented%20placeholders.md).
- [ ] **Scalar-oracle scope:** any old coordinator test oracle, including inactive-window aging behavior, must first be reconciled with current MQ5. An obsolete helper is not the source of truth.

Earlier synthetic performance evidence (2026-09-19: 100,000 ticks, 0.607 s vector state versus 10.280 s scalar trend, exact trend/reference agreement) concerns that revision and narrow oracle, not current full execution or trading profitability. No rerun or new runtime parity is claimed here.
