# Vectorized entrypoint flow

The active contract is pandas-native signals-only processing. [Native columnar migration](vectorized-operation-improment.plan.md) records the implementation, output tables, tests and separate execution-replay scope.

- **DONE:** CLI -> `run_vectorized_strategy` -> manifest source artifacts -> per-stream `ColumnarMarket` -> `process_native_stream`/`process_columns` -> primitive tick state plus signal/window event tables and observed candle state.
- **DONE:** Daily source files and broker/symbol groups are orchestration units; calculations operate on complete Series without Python tick/candle iteration. Terminal state survives daily partitions and duplicate timestamps retain `stream_tick` identity.
- **DONE:** Typed manifest categories are `ticks`, `candles`, `signal_state`, `signals`, `windows` and `per_candle_states`. Export joins original ticks with primitive state and writes separate signal/window Parquet files. Summary counts event rows.
- **DONE:** Execution configurations and backtests are rejected before data acquisition. Scalar/recorded replay and legacy order/position projections are separate APIs and do not run from the native entrypoint.
- **TODO, separate scope:** Migrate execution economics/lifecycle feedback and native callback replay before reconnecting them to the columnar pipeline. Native acceptance requires matching recordings and source identity; passing Python tests does not prove native parity or authorize live trading.
