# Vector entry point flow

Updated 2026-10-01. CLI -> zone/tick/native-M15 acquisition -> broker day/bar keys -> daily ResultFilesManifest -> MarketState/optional ExecutionReplay -> previous-candle context -> order/position projections -> export/summary -> optional vectorbt report. Shared acceptance work lives in [MT5-Python.Divergence.md](MT5-Python.Divergence.md).

## Implemented

- [x] Tick acquisition forwards symbol, covers complete zone days and rejects empty input; export accepts CSV/Parquet.
- [x] Prior native M15 history is retained; startup requires three closed candles, and each tick bar requires a unique covering native candle.
- [x] Raw CSV/zip zones use MT5 disabled/date/priority/bound rules before typed validation.
- [x] CLI `--execution-config` or programmatic ReplayConfig enables explicit-economics replay. Default mode remains signals-only; `--backtest` requires execution configuration.
- [x] Per-stream market/execution state persists across daily artifacts. Previous M15 output context uses a many-to-one join; tick/state indexes agree. Export consumes manifest artifacts.

## Remaining work

- [ ] Remove prohibited Python tick/candle iteration throughout the reachable flow, including history scans and row callbacks; follow the [audited vectorization plan](vectorized-operation-improment.plan.md) for exact locations, replacements and acceptance invariants.
- [ ] Debug is accepted/passed but unused by runner. Implement and test a meaningful behavior or remove the unsupported option.
- [ ] Reporting must use complete events/position collections before claiming a full ledger: scalar projection chooses one position, and vectorbt has independent cash/cost/direction assumptions.
- [ ] Complete native execution, timestamp/identity normalization and paired acceptance fixtures under the consolidated tracker; the missing envelope still prevents complete native callback verification.
