# cTrader Open API Client

## Overview

`src/ctrader_client/` is a Python package providing authenticated real-time
streaming of XAUUSD market data (spots, order-book depth, tick history) via the
cTrader Open API.

## Architecture

```
auth.py     -- OAuth2 token exchange (refresh + authorization-code grants)
settings.py -- CTraderSettings: env-based configuration
models.py   -- Pure dataclasses: SpotTick, DepthQuote, SymbolInfo, TickPage, etc.
rate.py     -- Integer-price decoding (raw integer -> float)
streams.py  -- Pure Protobuf message builders + parsers (no I/O)
client.py   -- CTraderClient state machine + RealtimeTransport (Twisted-backed)
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `CTRADER_CLIENT_ID` | yes | OAuth2 application client ID |
| `CTRADER_CLIENT_SECRET` | yes | OAuth2 application client secret |
| `CTRADER_REFRESH_TOKEN` | one of refresh/access | Long-lived refresh token |
| `CTRADER_ACCESS_TOKEN` | one of refresh/access | Short-lived access token |
| `CTRADER_ACCOUNT_LOGIN` | no | Select account by trader login number |
| `CTRADER_SYMBOL` | no | Symbol name (default `XAUUSD`) |
| `CTRADER_HOST` | no | API host (default `demo.ctraderapi.com`) |
| `CTRADER_PORT` | no | API port (default `5035`) |

A fallback key `ctrader_demo_account_login_number` is also read by
`CTraderSettings.from_env`.

## OAuth2 Setup (one-time)

1. Register an application at https://openapi.ctrader.com/apps
2. Obtain the `client_id` and `client_secret`
3. Complete the interactive authorization-code grant to receive a
   `refresh_token`
4. Set the variables in `.env` (never commit `.env`)

The `OAuthClient` caches the access token and auto-refreshes using the refresh
token when it expires (60-second safety margin).

## Usage

```python
from ctrader_client import CTraderClient, CTraderSettings, OAuthClient

settings = CTraderSettings.from_env()
oauth = OAuthClient.from_settings(settings)
client = CTraderClient(settings, oauth=oauth)

client.on("spot", lambda tick: print(f"bid={tick.bid} ask={tick.ask}"))

ready = client.wait_ready()  # Deferred fires with account_id
ready.addCallback(lambda acct_id: client.subscribe_live_price(100))
client.connect()
```

## Transport

The live transport uses the `ctrader-open-api` Twisted client over SSL. For
unit testing, `CTraderClient` accepts any `Transport` (Protocol) that
implements `connect`, `send`, `close`, and the `on_*` callback registrations.
