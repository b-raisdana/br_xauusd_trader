# Vector entry point flow

Current status (2026-09-30): the ordered source port, explicit CLI replay configuration and full-day acquisition are implemented. The historical checklist below describes the pre-port audit; use [active parity work](vectorized-state.md) and [the current divergence report](../Divergence%20Report%20-%20MT5%20vs%20Python%20vs%20Documentation.md) for remaining acceptance gaps.
Reviewed 2026-09-29 against the active source. `__main__.py` → zone/tick/M15 acquisition → bar/day keys → `run_vectorized_strategy` → daily ResultFilesManifest → selected strategy → previous-candle context → order/position projections → export/summary → optional vectorbt report.

## Implemented

- [x] Tick conversion forwards requested symbol; empty tick input and unsupported export suffix fail explicitly.
- [x] Native candles enter strategy bar/reference computation through daily manifest artifacts; unique covering M15 candles are required.
- [x] Prior M15 output context uses many-to-one merge; tick/state indexes must agree. Export consumes manifest artifacts.
- [x] Order/position fields project replay snapshots; optional programmatic ReplayConfig enables actions and execution. Default CLI omits it.

## Remaining work

- [ ] **Complete final-day acquisition:** current end bound is maximum zone day + 2 hours−epsilon. Define/use full intended interval and verify last tick/minute/day coverage with mocked acquisition.
- [ ] **Execution mode:** expose intentional offline replay configuration with explicit economics/session inputs; prove CLI mode in deterministic integration tests. `--backtest` only reports scalar positions and does not enable replay.
- [ ] **Debug contract:** debug is accepted/passed but unused by runner. Implement/document a meaningful artifact/output difference or remove the unsupported option; verify both paths.
- [ ] **Reporting fidelity:** scalar projection chooses last order/position; vectorbt uses Bid and no short direction. Reconcile complete event collections, concurrent positions and costs before treating reporting as an execution ledger.
- [ ] **New-EA parity:** follow [current acceptance tasks](Vectorization.Remaining%20not-implemented%20placeholders.md); native bootstrap/cross-day state and current thresholds differ. The missing MT5 envelope prevents final event wiring verification.

No strategy execution or new runtime test evidence is claimed by this source audit. Previously recorded CLI tests apply only to their source revisions; current code must determine current behavior.
