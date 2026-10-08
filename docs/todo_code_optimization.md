# Code Optimization TODO

## P1

- **[P1] `src/application/xauusd_trading_strategy_1_vector/vectorized_replay.py:246` `_run_state_machine`** — weakness: drives every market tick through Python `itertuples` and scalar state transitions. Optimization: batch-reconstruct independent state and feed only irreducible recurrence through a typed NumPy/Numba kernel. Factor: vectorization. Hot path: yes, one transition per replay tick. Coverage: 21 scalar-oracle lifecycle tests plus replay integration regressions; full per-tick differential coverage is incomplete. Mutation-safety: pending.

## P2

- **[P2] `src/application/xauusd_trading_strategy_1_vector/backtest.py:201` `_extract_replay_signals`** — weakness: materializes dense price, signal, size and fee matrices across all timeline rows and all positions, including cross-stream cells with no events. Optimization: project and simulate one stream at a time, then combine stream-level report outputs without changing independent account grouping. Factor: memory footprint and algorithmic complexity. Hot path: no, one report pass; peak memory grows with ticks × positions. Coverage: synthetic same-tick, multi-stream projection and Vectorbt artifact tests; production-scale memory is unmeasured. Mutation-safety: pending.
