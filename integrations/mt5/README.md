# MT5 Integration Profile

Use this profile when MetaTrader 5 is part of validation or live execution.

## Recommended architecture
- Python: research, data preparation, fast backtests, analytics.
- Shared deterministic fixtures: parity evidence.
- MQL5 EA: final MT5 Strategy Tester and preferred deterministic live path.
- MetaTrader5 Python package: Terminal data/access/order integration when required.

## Important limitation
MT5 Strategy Tester is designed for MQL5 programs and does not directly execute a Python strategy through the official MetaTrader5 Python package.

## Required project decisions
Record:
- whether live engine is MQL5 or Python;
- broker/server/symbol mapping;
- timezone mapping;
- spread/commission assumptions;
- lot/tick size/point semantics;
- order filling modes;
- session/rollover behavior.

## Parity gate
For Python research + MQL5 live:
use the same fixed fixtures where possible and compare:
- signal timestamp;
- direction;
- entry reference;
- stop/target;
- size;
- state transitions;
- exit reason.

## Secrets
Never commit account number/password/token.
Use local environment/secure configuration.

## Live
Real-money activation requires `LIVE_GATES.md` and explicit Leader approval.
