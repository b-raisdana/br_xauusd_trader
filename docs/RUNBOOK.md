# Runbook

Codex keeps this file updated with exact repeatable commands.

## Environment
- OS: Windows for MT5 execution; current migration assembly ran in a Linux workspace
- Python version: Verify in the target Repository environment
- Historical Python packages: MetaTrader5, NumPy 2.5.2, Polars 1.44.1
- Main platform: MetaTrader 5 / MQL5
- Historical broker profile: MetaQuotes-Demo
- Required external apps: MT5 terminal and compiler; Python environment for research/replay

## Setup
```text
Use scripts/bootstrap_python.ps1 only after Codex verifies it against the migrated historical v4 bootstrap.
```

## Run unit tests
```text
Current tests must be reconstructed from docs/TODO.md before claiming PASS.
Historical runners are under legacy_reference/PREVIOUS_TECHNICAL_BUNDLE/.
```

## Run backtest
```text
Use Python replay for causally valid screening; use MT5 Every Tick Based on Real Ticks for finalist acceptance.
```

## Generate report
```text
Generate compact Signal/Trade/Reject ledgers linked to semantic Rule IDs.
```

## MT5 compile/test
```text
Recover the current .mq5/.set and broker profile, compile with #property strict, then run the Contract and acceptance matrix in docs/TODO.md.
```

## Recovery after reboot
1. Open project folder.
2. Start required external apps.
3. Verify environment.
4. Run smoke check.
5. Continue from `CURRENT_STATE.md`.

## Troubleshooting
Record only recurring operational fixes, not one-off debug chatter.
