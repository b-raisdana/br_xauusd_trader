# Runbook

Codex keeps this file updated with exact repeatable commands.

## Shared pre-commit setup

Run `powershell -ExecutionPolicy Bypass -File scripts/setup_pre_commit.ps1` from the Windows checkout. This installs the pinned `br_pre_commit` submodule hook and normalizes its shell launchers to LF. Git commits run the shared wrapper in the active Python environment; that environment needs pre-commit, Ruff and project test dependencies. Use a feature branch because the wrapper protects `main`. Reinstall after moving the checkout.

## Environment
- OS: Windows host verified on 2026-09-06
- Python version: project-local CPython 3.12 (required by the active dependency set)
- Historical Python packages: MetaTrader5, NumPy 2.5.2, Polars 1.44.1
- Main platform: MetaTrader 5 / MQL5
- Installed MT5 Terminal and MetaEditor: build 6151 under `C:\Program Files\MetaTrader 5`
- Required external apps: MT5 terminal and compiler; Python environment for research/replay
- GitHub CLI: 2.100.0; private `origin` is `https://github.com/behrad203-tech/XAAUSD-PAction-projectFolder.git`

## Vectorbt

Installed `vectorbt==0.28.2` in `.venv` on 2026-09-16, preserving NumPy 2.1.3 and pandas 3.0.5. Import, a three-price holding portfolio with expected 2% return, and `pip check` passed. Newer releases conflict with the project's NumPy/pandas constraints. Reinstall with:

```powershell
.\.venv\Scripts\python.exe -m pip install 'vectorbt==0.28.2' 'numpy>=1.26.4,<2.2' 'pandas==3.0.5' --index-url https://pypi.org/simple --extra-index-url https://pypi.org/simple
.\.venv\Scripts\python.exe -m pip check
```

The explicit extra index overrides this host's failing NVIDIA index for this command. This optional installation is not part of the project dependency manifest.

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

## Fetch cTrader market data

Register `http://localhost:8080/callback` in the cTrader Open API application, then store only `CTRADER_CLIENT_ID` and `CTRADER_CLIENT_SECRET` in `.env`. On the first invocation, each live data command opens browser authorization in the host browser, stores the resulting refresh token in ignored `.env`, and continues automatically. If automatic launch fails, open the printed URL manually before the five-minute callback timeout:

```bash
ctrader-cli fetch-candles --symbol XAUUSD --timeframe 1min
ctrader-cli stream-orderbook --symbol XAUUSD
ctrader-cli stream-trades --symbol XAUUSD
```

The default OAuth scope is read-only `accounts`. Override the registered callback with `CTRADER_REDIRECT_URI`; request `CTRADER_OAUTH_SCOPE=trading` only when a future command needs trading access.

The inert contract smoke emits five time/Bid probe markers when its local smoke configuration enables `InpEmitTimeBasisProbe`. Correlate that ordered sequence against UTC terminal history with local values only:

```powershell
.\.venv\Scripts\python.exe .\scripts\match_mt5_time_basis.py `
  --terminal "C:\Program Files\MetaTrader 5\terminal64.exe" `
  --symbol XAUUSD `
  --server-time <YYYY-MM-DDTHH:MM:SS> `
  --bids <bid1,bid2,bid3,bid4,bid5>
```

The matcher checks 30-minute offsets from UTC-14 through UTC+14 and fails unless exactly one offset contains the full contiguous sequence. Keep probe values and the resolved Broker-specific offset in ignored/local runtime configuration; do not commit them.

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

The current source is research-only and inert. The compile script accepts `-MetaEditorPath` when MT5 is installed elsewhere. The smoke runner requires all other MetaTrader instances to be closed, discovers the matching terminal data root (or accepts `-DataRoot`), copies only the ignored compiled EA, and requires the 19-vector, coordinator, full-day current event-loop, read-only Native/Visual and five time-probe markers. Neither a zero-warning compile nor this smoke is strategy acceptance or live approval. Do not treat the historical EA under `legacy_reference/` as current.

## Recovery after reboot
1. Open project folder.
2. Start required external apps.
3. Verify environment.
4. Run smoke check.
5. Continue from `CURRENT_STATE.md`.

## Troubleshooting
Record only recurring operational fixes, not one-off debug chatter.
