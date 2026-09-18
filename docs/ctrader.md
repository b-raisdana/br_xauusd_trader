# cTrader Open API Client

## Overview

`src/infrastructure/ctrader_client/` is a Python package providing authenticated real-time streaming of XAUUSD market data (spots, order-book depth, tick history) via the cTrader Open API.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `CTRADER_CLIENT_ID` | yes | OAuth2 application client ID |
| `CTRADER_CLIENT_SECRET` | yes | OAuth2 application client secret |
| `CTRADER_REFRESH_TOKEN` | no | Long-lived refresh token; live data commands obtain and save it automatically when absent |
| `CTRADER_ACCESS_TOKEN` | no | Short-lived access token |
| `CTRADER_ACCOUNT_LOGIN` | no | Select account by trader login number |
| `CTRADER_SYMBOL` | no | Symbol name (default `XAUUSD`) |
| `CTRADER_HOST` | no | API host (default `demo.ctraderapi.com`) |
| `CTRADER_PORT` | no | API port (default `5035`) |
| `CTRADER_REDIRECT_URI` | no | Registered localhost callback (default `http://localhost:8080/callback`) |
| `CTRADER_OAUTH_SCOPE` | no | `accounts` for read-only data (default) or `trading` |

A fallback key `ctrader_demo_account_login_number` is also read by `CTraderSettings.from_env`.

## OAuth2 Setup (one-time)

1. Register an application at https://openapi.ctrader.com/apps and obtain its `client_id` and `client_secret`.
2. Register `http://localhost:8080/callback` as an application redirect URI, or set `CTRADER_REDIRECT_URI` to another registered localhost URI with an explicit port.
3. Put `CTRADER_CLIENT_ID` and `CTRADER_CLIENT_SECRET` in `.env` (never commit `.env`).
4. Run any live data command. If no token exists, it opens cTrader authorization in the host browser, captures the localhost callback, exchanges the code, saves `CTRADER_REFRESH_TOKEN` to `.env` with owner-only permissions, and continues the original command. If browser launch is unavailable, open the printed URL manually while the command waits for the callback.

The default `accounts` scope is read-only and sufficient for market-data fetching. Set `CTRADER_OAUTH_SCOPE=trading` only for commands that genuinely need trading permission.

The `OAuthClient` caches the access token and auto-refreshes using the refresh token when it expires (60-second safety margin).

## Usage

```python
from infrastructure.ctrader_client import CTraderClient, CTraderSettings, OAuthClient

settings = CTraderSettings.from_env()
oauth = OAuthClient.from_settings(settings)
client = CTraderClient(settings, oauth=oauth)

client.on("spot", lambda tick: print(f"bid={tick.bid} ask={tick.ask}"))

ready = client.wait_ready()  # Deferred fires with account_id
ready.addCallback(lambda acct_id: client.subscribe_live_price(100))
client.connect()
```

## Transport

The live transport uses the `ctrader-open-api` Twisted client over SSL. For unit testing, `CTraderClient` accepts any `Transport` (Protocol) that implements `connect`, `send`, `close`, and the `on_*` callback registrations.

## Manual testing CLI

A `typer`-based CLI lives under `src/presentation/` and exercises every implemented client capability without needing live credentials:

```text
cTrader CLI commands for settings, decoding, rate, building requests, parsing, simulating, OAuth, and live data operations.
```

Run it directly with `python src/presentation/ctrader_cli.py <command>`, as a module with `PYTHONPATH=src python -m presentation.ctrader_cli <command>`, or after an editable install via the `ctrader-cli` console script. The `oauth` subcommands perform live HTTP to the cTrader token endpoint and require real OAuth credentials in `.env`; `simulate`, `build`, `parse`, `decode`, `rate` and `settings` are offline and safe to run anywhere.
