# cTrader Open API Client

## Overview

A client providing authenticated real-time streaming of XAUUSD market data (spots, order-book depth, tick history) via the cTrader Open API.

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

A fallback key `ctrader_demo_account_login_number` is also read by the settings loader.

## OAuth2 Flow (one-time)

1. Register an application and obtain its `client_id` and `client_secret`.
2. Register a localhost callback URI, or set `CTRADER_REDIRECT_URI` to another registered localhost URI with an explicit port.
3. Put `CTRADER_CLIENT_ID` and `CTRADER_CLIENT_SECRET` in `.env` (never commit `.env`).
4. Run any live data command. If no token exists, it opens cTrader authorization in the host browser, captures the localhost callback, exchanges the code, saves `CTRADER_REFRESH_TOKEN` to `.env` with owner-only permissions, and continues the original command. If browser launch is unavailable, open the printed URL manually while the command waits for the callback.

The default `accounts` scope is read-only and sufficient for market-data fetching. Set `CTRADER_OAUTH_SCOPE=trading` only for commands that genuinely need trading permission.

The OAuth client caches the access token and auto-refreshes using the refresh token when it expires (60-second safety margin).

## Usage

The client exposes event-based streaming:

- Register handlers via `on("spot", callback)` for spot price updates.
- `wait_ready()` fires when the connection is established, providing the account ID.
- `subscribe_live_price(symbol_id)` starts live price subscription after readiness.
- `connect()` initiates the transport.

## Transport

The live transport uses an SSL connection to the cTrader API. For unit testing, the client accepts any transport that implements `connect`, `send`, `close`, and the `on_*` callback registrations.

## Manual Testing CLI

A CLI exercises every implemented client capability without needing live credentials:

- `settings`, `decode`, `rate`, `build`, `parse`, `simulate` — offline and safe to run anywhere.
- `oauth` — performs live HTTP to the cTrader token endpoint and requires real OAuth credentials in `.env`.