# Code Optimization TODO

## P1 — RESOLVED

- **[P1] `src/application/xauusd_trading_strategy_1_vector/vectorized_replay.py:246` `_run_state_machine`** — **RESOLVED**: Replaced with Numba JIT-compiled kernel in `execution_batch/kernel.py` (`ReplayKernel` jitclass) and `execution_batch/scan.py` (`scan` @njit). The old scalar `itertuples` loop driving one transition per tick is now a typed recurrence over precomputed arrays with no Python tick callbacks.

## P2

- **[P2] `src/application/xauusd_trading_strategy_1_vector/backtest.py:63` `_extract_replay_signals`** — weakness: materializes dense price, signal, size and fee matrices across all timeline rows and all positions, including cross-stream cells with no events. Optimization: project and simulate one stream at a time, then combine stream-level report outputs without changing independent account grouping. Factor: memory footprint and algorithmic complexity. Hot path: no, one report pass; peak memory grows with ticks × positions. Coverage: synthetic same-tick, multi-stream projection and Vectorbt artifact tests; production-scale memory is unmeasured. Mutation-safety: pending.
