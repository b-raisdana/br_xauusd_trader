# Runbook

Codex keeps this file updated with exact repeatable commands.

## Environment
- OS: Windows host verified on 2026-09-06
- Python version: project-local CPython 3.11.15 (created through uv 0.11.25)
- Historical Python packages: MetaTrader5, NumPy 2.5.2, Polars 1.44.1
- Main platform: MetaTrader 5 / MQL5
- Installed MT5 Terminal and MetaEditor: build 6151 under `C:\Program Files\MetaTrader 5`
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

Read-only raw tick acquisition uses explicit UTC boundaries and writes only to ignored local cache:

```powershell
.\.venv\Scripts\python.exe .\scripts\export_mt5_ticks.py `
  --terminal "C:\Program Files\MetaTrader 5\terminal64.exe" `
  --symbol XAUUSD `
  --from-utc 2026-08-28T10:00:00+00:00 `
  --to-utc 2026-08-28T10:15:00+00:00 `
  --output data/cache/xauusd_20260828_1000_1015_utc.csv
```

Do not assign Broker Days from UTC until the terminal time basis for that run is explicitly verified. Tick cache is generated evidence and must not be committed.

## Generate report
```text
Generate compact Signal/Trade/Reject ledgers linked to semantic Rule IDs.
```

## MT5 compile/test
```powershell
.\.venv\Scripts\python.exe .\scripts\generate_mql_vectors.py --check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\compile_mt5.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mt5_contract_smoke.ps1
```

The current source is research-only and inert. The compile script accepts `-MetaEditorPath` when MT5 is installed elsewhere. The smoke runner requires all other MetaTrader instances to be closed, discovers the matching terminal data root (or accepts `-DataRoot`), copies only the ignored compiled EA, and requires both the 16-vector and read-only Native-adapter markers. Neither a zero-warning compile nor this smoke is strategy acceptance or live approval. Do not treat the historical EA under `legacy_reference/` as current.

## Recovery after reboot
1. Open project folder.
2. Start required external apps.
3. Verify environment.
4. Run smoke check.
5. Continue from `CURRENT_STATE.md`.

## Troubleshooting
Record only recurring operational fixes, not one-off debug chatter.
