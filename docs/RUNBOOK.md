# Runbook

Codex keeps this file updated with exact repeatable commands.

## Shared pre-commit setup

Run the pre-commit setup script from the Windows checkout. This installs the pinned shared hook and normalizes its shell launchers. Git commits run the shared wrapper in the active Python environment. Use a feature branch because the wrapper protects `main`. Reinstall after moving the checkout.

## Local Python checks

Use the existing project environment. Direct pre-commit invocations need the same shared-tool paths that `.git/hooks/pre-commit` exports:

```powershell
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
$env:PYTHONPATH = "$PWD\br_pre_commit\src"
$env:BR_PRE_COMMIT_REPO_ROOT = "$PWD\br_pre_commit"
$env:USER_REPO_ROOT = "$PWD"
python -m pytest
python -m pre_commit run --all-files
```

`pandera_validate` validates copies by default. Mutating state transforms opt into `inplace=True`; input normalization then affects the supplied frame, while output schemas reject dtype drift without coercion.

## Environment

- Main platform: MetaTrader 5 / MQL5
- GitHub CLI: available; private `origin` is the project remote

## Vectorbt

Installed in the project environment; preserves compatible NumPy/pandas constraints. Import, a three-price holding portfolio with expected 2% return, and dependency check passed. Newer releases conflict with the project's constraints. Reinstall with the project environment's pip.

The explicit extra index overrides this host's failing NVIDIA index for this command. This optional installation is not part of the project dependency manifest.

## Setup

Bootstrap the Python environment using the project setup script.

The explicit execution-policy flag is required on the currently verified Windows host. The cache override keeps agent/sandbox runs project-local; normal interactive use may omit it.

## Run unit tests

Run the quality gate script. This proves current Python domain contracts plus repository/migration integrity; historical runners remain isolated under `legacy_reference/PREVIOUS_TECHNICAL_BUNDLE/`.

## Inspect environment and repository status

```text
Inspect environment, then check project status.
```

## Run backtest

```text
Use Python replay for causally valid screening; use MT5 Every Tick Based on Real Ticks for finalist acceptance.
```

Read-only raw tick acquisition uses explicit UTC boundaries and writes only to ignored local cache:

```text
Export MT5 ticks to CSV with explicit UTC range and output path under data/cache/.
```

Do not assign Broker Days from UTC until the terminal time basis for that run is explicitly verified. Tick cache is generated evidence and must not be committed.

## Fetch cTrader market data

Register `http://localhost:8080/callback` in the cTrader Open API application, then store only `CTRADER_CLIENT_ID` and `CTRADER_CLIENT_SECRET` in `.env`. On the first invocation, each live data command opens browser authorization in the host browser, stores the resulting refresh token in ignored `.env`, and continues automatically. If automatic launch fails, open the printed URL manually before the five-minute callback timeout:

```text
cTrader market data commands for XAUUSD on 1min timeframe, order book, and trades.
```

The default OAuth scope is read-only `accounts`. Override the registered callback with `CTRADER_REDIRECT_URI`; request `CTRADER_OAUTH_SCOPE=trading` only when a future command needs trading access.

The inert contract smoke emits five time/Bid probe markers when its local smoke configuration enables `InpEmitTimeBasisProbe`. Correlate that ordered sequence against UTC terminal history with local values only:

```text
Match MT5 time basis with terminal, symbol, server-time, and bid probes.
```

The matcher checks 30-minute offsets from UTC-14 through UTC+14 and fails unless exactly one offset contains the full contiguous sequence. Keep probe values and the resolved Broker-specific offset in ignored/local runtime configuration; do not commit them.

## Generate report

```text
Generate compact Signal/Trade/Reject ledgers linked to semantic Rule IDs.
```

## MT5 compile/test

```text
Generate MQL vectors with check flag; compile MT5; run MT5 contract smoke.
```

The current source is research-only and inert. The compile script accepts a path argument when MT5 is installed elsewhere. The smoke runner requires all other MetaTrader instances to be closed, discovers the matching terminal data root, copies only the ignored compiled EA, and requires the 19-vector, coordinator, full-day current event-loop, read-only Native/Visual and five time-probe markers. Neither a zero-warning compile nor this smoke is strategy acceptance or live approval. Do not treat the historical EA under `legacy_reference/` as current.

## Recovery after reboot

1. Open project folder.
2. Start required external apps.
3. Verify environment.
4. Run smoke check.
5. Continue from `CURRENT_STATE.md`.

## Troubleshooting

Record only recurring operational fixes, not one-off debug chatter.
