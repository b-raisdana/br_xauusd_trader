# Runbook

Codex keeps this file updated with exact repeatable commands.

## Environment
- OS: Windows host verified on 2026-09-06
- Python version: project-local CPython 3.11.15 (created through uv 0.11.25)
- Historical Python packages: MetaTrader5, NumPy 2.5.2, Polars 1.44.1
- Main platform: MetaTrader 5 / MQL5
- Installed MT5 Terminal and MetaEditor: build 6151 under `C:\Program Files\MetaTrader 5`
- Historical broker profile: MetaQuotes-Demo
- Required external apps: MT5 terminal and compiler; Python environment for research/replay
- GitHub CLI: 2.100.0; private `origin` is `https://github.com/behrad203-tech/XAAUSD-PAction-projectFolder.git`

## Setup
```powershell
$env:UV_CACHE_DIR = Join-Path (Resolve-Path '.') '.uv-cache'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap_python.ps1
```

The explicit execution-policy flag is required on the currently verified Windows host. The cache override keeps agent/sandbox runs project-local; normal interactive use may omit it.

## Run unit tests
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1
```

This proves current Python domain contracts plus repository/migration integrity; historical runners remain isolated under `legacy_reference/PREVIOUS_TECHNICAL_BUNDLE/`.

## Inspect environment and repository status

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check_environment.ps1
.\.venv\Scripts\python.exe .\scripts\project_status.py
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
```powershell
.\.venv\Scripts\python.exe .\scripts\generate_mql_vectors.py --check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\compile_mt5.ps1
```

The current source is research-only and inert. The compile script accepts `-MetaEditorPath` when MT5 is installed elsewhere. A zero-warning compile is not Strategy Tester, broker parity, or live approval. Do not treat the historical EA under `legacy_reference/` as current.

## Recovery after reboot
1. Open project folder.
2. Start required external apps.
3. Verify environment.
4. Run smoke check.
5. Continue from `CURRENT_STATE.md`.

## Troubleshooting
Record only recurring operational fixes, not one-off debug chatter.
