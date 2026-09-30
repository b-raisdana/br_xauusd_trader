# MT5 source parity

Objective: Python must match the replacement MQ5 signals, positions and corresponding internal state on identical inputs. Status: visible source transitions implemented; exact native acceptance remains open. [Current comparison](../Divergence%20Report%20-%20MT5%20vs%20Python%20vs%20Documentation.md).

- [x] Ordered market controller: native three-bar bootstrap, close-before-day-change, continuous trend/Bid, native-open engagement and directional touch slots.
- [x] Replay: explicit EA defaults, adjacent-zone protection, actual R0, High expansion, fill quotas, cycle completion, risk reservations, retry stages and day/session/restart assumptions.
- [x] CLI explicit execution JSON, full zone-day acquisition, retained candle history and shared-state snapshots.
- [x] Replace obsolete test expectations with native-source formulas and independent candle/BO oracles; retain negative data validation.
- [x] Explicit containing session windows/from/to/carry audit with gap and cutoff transitions; native schedule acquisition remains external.
- [ ] Recorded native deal/retcode/cost/timing adapter and native numeric boundary vectors.
- [ ] Obtain missing XauRobustLiveEnvelope.mqh and compile the complete EA.
- [ ] Run paired native/Python fixtures and compare every ordered event/shared field with no unexplained mismatch. Include slippage, rejected sends/deletes/modifies/closes, partial deals, session gaps and restart.
- [ ] Full acceptance and documentation verdict: keep PARTIAL until native evidence satisfies the objective.

Validation: 178 tests and pre-commit passed before the final session-window addition; 23 focused parity tests pass including three new session-mode cases. Final gate rerun pending. Earlier performance/scalar benchmarks describe retired revisions and are not acceptance evidence for this port.
