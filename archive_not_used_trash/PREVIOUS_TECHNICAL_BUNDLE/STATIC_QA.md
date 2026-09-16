# AR-OPS-01 Static QA

- MQL5 braces balanced: PASS
- `InpStrategyCapitalBasisUSD`: PASS
- `OpsReadState`: PASS
- `OpsWriteState`: PASS
- `EnterOpsDayLock`: PASS
- `OpsCancelAllPending`: PASS
- `OpsFlattenAllPositions`: PASS
- `MaybeSimulateOpsRestart`: PASS
- `OPS_RESTART_DAY_LOCK_ENTERED`: PASS
- `g_ops_day_lock`: PASS
- Real compiler + Real-Tick equivalence remain authority.
- FAST v2 per-row CUSTOM date windows: PASS by harness source audit.
- Scenario count reduced 10 -> 6 without reducing MT5 tick model.
