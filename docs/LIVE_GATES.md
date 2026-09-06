# Live Trading Gates

Current project state: `G0 — Research`. Historical F2 evidence does not promote the changed current Rulebook to G1/G2.

A profitable or passing backtest is not permission to trade real money.

## G0 — Research
Requirements:
- hypothesis/rules documented;
- reproducible data/config;
- no real-money execution.

## G1 — Backtest Validated
Requirements:
- relevant Rule tests PASS;
- realistic material costs modeled;
- no known leakage/look-ahead;
- regression evidence;
- sensitivity/robustness review appropriate to strategy.

## G2 — Platform Parity
For separate research/live implementations:
- same deterministic fixtures;
- signal/entry/exit/risk parity within defined tolerance;
- differences documented.

For MT5:
- final MQL5 path compiled;
- relevant MT5 Strategy Tester evidence available.

## G3 — Demo / Paper / Testnet
Requirements:
- live data path verified;
- order lifecycle verified;
- disconnect/restart behavior reviewed;
- logging and reconciliation working;
- kill/disable mechanism tested.

## G4 — Limited Live
Requires explicit Project Leader approval.
Use deliberately limited exposure and predefined rollback/disable criteria.

## G5 — Scale
Requires new evidence and explicit Project Leader approval if risk materially increases.

## Hard prohibitions
- Never enable real-money trading merely because code/tests pass.
- Never store live credentials in Git.
- Never silently increase risk limits.
- Never bypass broker/exchange safeguards to automate faster.
