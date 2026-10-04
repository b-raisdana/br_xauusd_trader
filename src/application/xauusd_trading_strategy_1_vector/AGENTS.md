# AGENTS.md - strategy package

Delta to [`src/AGENTS.md`](../../AGENTS.md) and the root contract. Read those
first.

Package: `application/xauusd_trading_strategy_1_vector`. It owns the ordered
market-state transitions and the optional execution replay. See its
[README.md](README.md) for inputs/outputs and
[docs/architecture.md](../../../docs/architecture.md) for the responsibility map.

## Causal windows and ordering

- Current-candle extrema must **never** enter their own reference.
- Causal closed-candle windows only. Missing bars are never replayed.
- Callback/settlement order is chronological. Simulated settlement in
  `ExecutionReplay` happening before current-tick signal processing is an
  explicit **replay assumption**, not proven native ordering. Do not upgrade it
  in a report.
- Zone rows are filtered from raw input before use; full final zone days are
  acquired, with broker-calendar conversion from the configured timezone.

## State lifetime

- `MarketState` is per broker/symbol and retained **across daily manifest
  partitions**, so cross-day state survives a day boundary.
- Trend and previous Bid persist across day and bar changes.
- The runner retains prior history; production never synthesizes bootstrap
  candles. Three actual closed M15 bars are required, so tests must supply
  synthetic history explicitly.

## Stream isolation

Ticks must be chronological within each broker/symbol; M15 candles must be
unique per broker/symbol/`bar_time` and must cover every observed tick bar.
Duplicate-tick identity and per-stream isolation are contract requirements, not
incidental behavior.

## Recorded replay and parity

- `recorded_runner` **without** `--expected` produces no comparison. Report
  `compared=false` honestly; it never establishes parity.
- Compare checkpoints in order and report the **first** difference, not a
  summary verdict.
- Native evidence classes are distinct: offline regression, recorded
  comparison, MQ5 compile, native runtime parity. See
  [.agents/skills/strategy-parity](../../../.agents/skills/strategy-parity/SKILL.md).
- The MQ5 reference and its envelope are present under
  `mt5/MQL5/Experts/`, but **no compile or tester run has been performed**. Do
  not claim build success or parity. Source presence is not compile evidence.

## Known compliance gap

`the_strategy.py:process_native_stream` currently uses `zip`/`enumerate`/
`itertuples` over market rows and candle-derived lists. This is recorded
**technical debt against a confirmed rule**, not an exception to it. Coordinate
with [docs/todo/vectorized-operation-improment.plan.md](../../../docs/todo/vectorized-operation-improment.plan.md);
do not start a parallel implementation.

## Artifacts

State artifacts are large. Write them through the existing fire-and-forget
executor; do not concatenate `per_tick_state` or `per_candle_state` in memory.