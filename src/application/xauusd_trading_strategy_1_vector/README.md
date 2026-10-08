# XAUUSD strategy replay

The production calculation path uses an ordered `MarketState` per broker/symbol and optional `ExecutionReplay`, retained across daily manifest partitions. Its trading defaults and visible transitions follow [the replacement MT5 source](../../../mt5/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5). Exact native parity remains unproven; see [the divergence report](../../../docs/todo/MT5-Python.Divergence.md).

`process_tick_data` accepts a `ResultFilesManifest`. Provide chronological ticks and unique native M15 candles covering each observed bar plus at least three closed bootstrap bars. The runner retains prior history. Trend and previous Bid survive day changes; current-candle extrema never enter their own reference. Full final zone days are acquired, with broker-calendar conversion from configured timezone.

Default mode emits candidate/state collections. The active runner rejects execution replay and does not produce order/position artifacts. `ExecutionReplay` remains a separate API; its use requires explicit `ReplayConfig` economics and EA inputs.

Per-tick `mt5_state` exposes shared MQ5 state names. `trace.first_difference` compares normalized traces strictly without tolerances or ignored fields. Native ticket identity and callback order must be supplied/normalized explicitly. Event/order/position collections preserve simultaneous records; scalar output columns select one snapshot and cannot represent the full ledger.

The CLI requests a vectorbt report by default; `--no-backtest` skips it. The report runs only when the manifest contains position artifacts. The active signals-only runner produces none, so the CLI logs a warning and completes without a backtest report. Vectorbt remains a separate report, not a native-parity oracle. `debug` is accepted but unused. Legacy vector helpers remain for isolated callers/tests; production flow uses the ordered controller. No performance, profitability or live-readiness claim follows from source tests.
