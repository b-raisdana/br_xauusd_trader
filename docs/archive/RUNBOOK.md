# Runbook

Codex keeps this file updated with exact repeatable commands.

## Environment

- Main platform: MetaTrader 5 / MQL5
- Required external apps: MT5 terminal and compiler; Python environment for research/replay
- GitHub CLI: available

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
ctrader-cli fetch-candles --symbol XAUUSD --timeframe 1min
ctrader-cli stream-orderbook --symbol XAUUSD
ctrader-cli stream-trades --symbol XAUUSD
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
