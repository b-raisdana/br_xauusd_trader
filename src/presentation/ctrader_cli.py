"""Manual test CLI for the cTrader Open API client.

Exposes every implemented ``infrastructure.ctrader_client`` capability as a
CLI command so a developer can manually exercise the pure utilities (price
decoding, rate helpers, protobuf builders/parsers, env-based settings) and the
live OAuth/token exchange, plus a fully offline *simulation* of the client state
machine (connect -> application auth -> account auth -> symbol resolution ->
subscribe live price/orderbook -> fetch tick data -> incoming spot/depth/tick
events) driven entirely by synthetic protobuf messages and a fake transport.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

import typer
from ctrader_open_api import Protobuf
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoMessage

# Ensure ``src`` is importable when run as a loose script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.ctrader_client import (
    CTraderClient,
    CTraderSettings,
    OAuthClient,
    build_account_auth_request,
    build_application_auth_request,
    build_get_account_list_request,
    build_get_tick_data_request,
    build_subscribe_depth_request,
    build_subscribe_spots_request,
    build_symbol_by_id_request,
    build_symbols_list_request,
    decode_price,
    exchange_authorization_code,
    exchange_refresh_token,
    pip_size,
    point,
)
from infrastructure.ctrader_client.models import CTraderError, TickPage
from infrastructure.ctrader_client.streams import (
    parse_accounts,
    parse_depth_event,
    parse_error,
    parse_spot_event,
    parse_symbol,
    parse_symbols_list,
    parse_tick_data_page,
)

app = typer.Typer(
    help="Manual test CLI for the cTrader Open API client (infrastructure.ctrader_client).",
    add_completion=False,
)

# Account/symbol constants reused by the offline simulation.
SIM_SYMBOL_ID = 100
SIM_ACCOUNT_ID = 9011925
SIM_TICKER = "XAUUSD"
SIM_DIGITS = 5
SIM_PIP_POSITION = 4

_ENV_KEYS = (
    "CTRADER_CLIENT_ID",
    "CTRADER_CLIENT_SECRET",
    "CTRADER_REFRESH_TOKEN",
    "CTRADER_ACCESS_TOKEN",
    "CTRADER_ACCOUNT_LOGIN",
    "CTRADER_SYMBOL",
    "CTRADER_HOST",
    "CTRADER_PORT",
)


def _wrap(message: Any) -> ProtoMessage:
    """Serialize a protobuf message into a ProtoMessage envelope (like receive)."""
    envelope = ProtoMessage()
    envelope.payloadType = message.payloadType
    envelope.payload = message.SerializeToString()
    return envelope


def _make_account_list(
    account_id: int = SIM_ACCOUNT_ID, login: int = SIM_ACCOUNT_ID, is_live: bool = False
) -> Any:
    msg = Protobuf.get("ProtoOAGetAccountListByAccessTokenRes")
    msg.accessToken = "fake_token"
    acct = msg.ctidTraderAccount.add()
    acct.ctidTraderAccountId = account_id
    acct.traderLogin = login
    acct.isLive = is_live
    return msg


def _symbols_list_message(symbol_id: int = SIM_SYMBOL_ID, name: str = SIM_TICKER) -> Any:
    msg = Protobuf.get("ProtoOASymbolsListRes")
    msg.ctidTraderAccountId = SIM_ACCOUNT_ID
    sym = msg.symbol.add()
    sym.symbolId = symbol_id
    sym.symbolName = name
    sym.enabled = True
    sym.description = "Gold vs USD"
    sym.baseAssetId = 1
    sym.quoteAssetId = 2
    return msg


def _symbol_by_id_message(
    symbol_id: int = SIM_SYMBOL_ID, name: str = SIM_TICKER, digits: int = SIM_DIGITS
) -> Any:
    msg = Protobuf.get("ProtoOASymbolByIdRes")
    msg.ctidTraderAccountId = SIM_ACCOUNT_ID
    raw = msg.symbol.add()
    raw.symbolId = symbol_id
    raw.digits = digits
    raw.pipPosition = SIM_PIP_POSITION
    return msg


def _payload_name(message: Any) -> str:
    try:
        return message.DESCRIPTOR.full_name
    except AttributeError:
        return type(message).__name__


def _fmt_sent(messages: list[Any]) -> str:
    lines = [
        f"  [{i}] {_payload_name(m)} payloadType={m.payloadType}" for i, m in enumerate(messages)
    ]
    return "\n".join(lines) if lines else "  (none)"


class _FakeOAuth(OAuthClient):
    """OAuthClient stub that yields a constant access token (no network)."""

    def __init__(self, token: str = "fake_token") -> None:
        self.client_id = "fake_id"
        self.client_secret = "fake_secret"
        self.refresh_token: Optional[str] = None
        self.access_token = token
        self._expires_at: float = float("inf")
        self._last_token = None

    def get_access_token(self) -> str:
        return self.access_token or ""


class _FakeTransport:
    """Records sent requests and replays synthetic responses via feed()."""

    def __init__(self) -> None:
        self.sent: list[Any] = []
        self._connected_cb: Optional[Callable[[], None]] = None
        self._message_cb: Optional[Callable[[Any], None]] = None
        self._disconnected_cb: Optional[Callable[[Any], None]] = None

    def on_connected(self, callback: Callable[[], None]) -> None:
        self._connected_cb = callback

    def on_message(self, callback: Callable[[Any], None]) -> None:
        self._message_cb = callback

    def on_disconnected(self, callback: Callable[[Any], None]) -> None:
        self._disconnected_cb = callback

    def connect(self) -> None:
        if self._connected_cb is not None:
            self._connected_cb()

    def send(self, message: Any) -> None:
        self.sent.append(message)

    def close(self) -> None:
        pass

    def feed(self, message: Any) -> None:
        assert self._message_cb is not None, "transport not wired to a client"
        self._message_cb(message)


# -- commands -----------------------------------------------------------------


@app.command()
def settings() -> None:
    """Load and display cTrader settings from .env / environment."""
    try:
        cfg = CTraderSettings.from_env()
    except CTraderError as exc:
        typer.echo(f"[settings] {exc}")
        typer.echo("Environment variable status:")
        for key in _ENV_KEYS:
            typer.echo(f"  {key} = {'set' if os.getenv(key) else 'unset'}")
        raise typer.Exit(code=1) from None
    typer.echo(
        json.dumps(
            {
                "client_id": cfg.client_id,
                "refresh_token": "<set>" if cfg.refresh_token else None,
                "access_token": "<set>" if cfg.access_token else None,
                "account_login": cfg.account_login,
                "symbol": cfg.symbol,
                "host": cfg.host,
                "port": cfg.port,
                "is_live": cfg.is_live,
                "has_token": cfg.has_token,
            },
            indent=2,
        )
    )


@app.command()
def decode(
    raw: int = typer.Argument(..., help="Raw integer price from cTrader (e.g. 260340000)"),
    digits: int = typer.Argument(..., help="Symbol digits (e.g. 5 for XAUUSD)"),
) -> None:
    """Decode a raw integer cTrader price into a human-readable float."""
    typer.echo(f"decode_price(raw={raw}, digits={digits}) = {decode_price(raw, digits)}")


@app.command()
def rate(
    pip_position: int = typer.Argument(..., help="Pip decimal position (e.g. 4 -> 0.0001)"),
    digits: int = typer.Argument(..., help="Digits for point size (e.g. 5 -> 0.00001)"),
) -> None:
    """Print pip_size and point helpers."""
    typer.echo(f"pip_size(pip_position={pip_position}) = {pip_size(pip_position)}")
    typer.echo(f"point(digits={digits}) = {point(digits)}")


@app.command(name="build")
def build_msgs() -> None:
    """Build every request message with sample values and print their envelope."""
    account_id = SIM_ACCOUNT_ID
    symbol_id = SIM_SYMBOL_ID
    messages = {
        "application_auth": build_application_auth_request("cid", "secret"),
        "get_account_list": build_get_account_list_request("access_token"),
        "account_auth": build_account_auth_request(account_id, "access_token"),
        "symbols_list": build_symbols_list_request(account_id),
        "symbol_by_id": build_symbol_by_id_request(account_id, symbol_id),
        "subscribe_spots": build_subscribe_spots_request(account_id, [symbol_id]),
        "subscribe_depth": build_subscribe_depth_request(account_id, symbol_id),
        "get_tick_data": build_get_tick_data_request(account_id, symbol_id, 1700000000, 1700003600),
    }
    for name, msg in messages.items():
        typer.echo(f"[build] {name}: payloadType={msg.payloadType} full_name={_payload_name(msg)}")
        typer.echo(f"  {msg}")


@app.command(name="parse")
def parse_msgs() -> None:
    """Parse synthetic cTrader responses into domain models and print them."""
    digits = SIM_DIGITS

    accounts = parse_accounts(_make_account_list())
    typer.echo(f"[parse] accounts -> {accounts}")

    lights = parse_symbols_list(_symbols_list_message())
    typer.echo(f"[parse] symbols_list -> {lights}")

    sym = parse_symbol(_symbol_by_id_message(), lights[0])
    if sym is None:
        raise CTraderError("synthetic symbol response did not contain the requested symbol")
    typer.echo(f"[parse] symbol_by_id -> {sym}")
    typer.echo(
        f"        price_scale={sym.price_scale} pip_size={sym.pip_size} point={sym.point} "
        f"decode(260340000)={sym.decode_price(260340000)}"
    )

    spot = Protobuf.get("ProtoOASpotEvent")
    spot.ctidTraderAccountId = SIM_ACCOUNT_ID
    spot.symbolId = SIM_SYMBOL_ID
    spot.bid = 260340000
    spot.ask = 260360000
    spot.timestamp = int(time.time())
    typer.echo(f"[parse] spot -> {parse_spot_event(spot, digits)}")

    depth = Protobuf.get("ProtoOADepthEvent")
    depth.ctidTraderAccountId = SIM_ACCOUNT_ID
    depth.symbolId = SIM_SYMBOL_ID
    q = depth.newQuotes.add()
    q.id = 1
    q.size = 100000
    q.bid = 260330000
    q.ask = 260370000
    depth.deletedQuotes.append(2)
    typer.echo(f"[parse] depth -> {parse_depth_event(depth, digits)}")

    tick = Protobuf.get("ProtoOAGetTickDataRes")
    tick.ctidTraderAccountId = SIM_ACCOUNT_ID
    sample = tick.tickData.add()
    sample.timestamp = 1700000000
    sample.tick = 260340000
    tick.hasMore = False
    page: TickPage = parse_tick_data_page(tick, SIM_SYMBOL_ID)
    typer.echo(f"[parse] tick_page -> {page}")
    typer.echo(f"        decoded prices -> {page.decode_prices(digits)}")

    err = Protobuf.get("ProtoOAErrorRes")
    err.errorCode = "TEST_ERROR"
    err.description = "demo error"
    typer.echo(f"[parse] error -> {parse_error(err)}")


@app.command()
def simulate() -> None:
    """Run the full client state machine offline with a fake transport.

    Exercises connect -> application auth -> account auth -> symbol resolution ->
    subscribe live price/orderbook -> fetch tick data -> incoming spot/depth/tick
    events using synthetic protobuf messages. No network access required.
    """
    settings = CTraderSettings(
        client_id="cid",
        client_secret="secret",
        refresh_token=None,
        access_token="access",
        account_login=None,
        symbol=SIM_TICKER,
        host="demo.ctraderapi.com",
        port=5035,
    )
    transport = _FakeTransport()
    client = CTraderClient(settings, oauth=_FakeOAuth(), transport=transport)

    seen: dict[str, list[Any]] = {
        "spot": [],
        "depth": [],
        "symbols": [],
        "tick": [],
        "error": [],
    }
    for event in ("spot", "depth", "symbols", "tick", "error"):
        client.on(event, seen[event].append)

    typer.echo(f"[simulate] client.connect() initial state={client._state}")
    client.connect()
    typer.echo("[simulate] after connect, sent requests:")
    typer.echo(_fmt_sent(transport.sent))

    transport.feed(_wrap(Protobuf.get("ProtoOAApplicationAuthRes")))
    typer.echo(
        f"[simulate] fed ProtoOAApplicationAuthRes -> state={client._state} "
        f"access_token={client._access_token}"
    )

    transport.feed(_wrap(_make_account_list(is_live=False)))
    typer.echo(
        f"[simulate] fed ProtoOAGetAccountListByAccessTokenRes -> state={client._state} "
        f"account_id={client._account_id}"
    )
    typer.echo("[simulate] sent requests now:")
    typer.echo(_fmt_sent(transport.sent))

    transport.feed(_wrap(Protobuf.get("ProtoOAAccountAuthRes", ctidTraderAccountId=SIM_ACCOUNT_ID)))
    typer.echo(
        f"[simulate] fed ProtoOAAccountAuthRes -> state={client._state} "
        f"ready={client._ready.called}"
    )

    typer.echo(f"[simulate] client.resolve_symbol('{SIM_TICKER}')")
    deferred = client.resolve_symbol(SIM_TICKER)

    transport.feed(_wrap(_symbols_list_message()))
    typer.echo(f"[simulate] fed ProtoOASymbolsListRes -> symbols events={len(seen['symbols'])}")

    transport.feed(_wrap(_symbol_by_id_message()))
    resolved = deferred.result if deferred.called else None
    typer.echo(
        f"[simulate] fed ProtoOASymbolByIdRes -> resolve called={deferred.called} symbol={resolved}"
    )

    client.subscribe_live_price(SIM_SYMBOL_ID)
    client.subscribe_orderbook(SIM_SYMBOL_ID)
    client.fetch_tick_data(SIM_SYMBOL_ID, 1700000000, 1700003600)
    typer.echo("[simulate] after subscribe + fetch, sent requests:")
    typer.echo(_fmt_sent(transport.sent))

    tick = Protobuf.get("ProtoOAGetTickDataRes")
    tick.ctidTraderAccountId = SIM_ACCOUNT_ID
    s = tick.tickData.add()
    s.timestamp = 1700000000
    s.tick = 260340000
    tick.hasMore = False
    transport.feed(_wrap(tick))
    typer.echo(
        f"[simulate] fed ProtoOAGetTickDataRes -> tick events={len(seen['tick'])} "
        f"page={seen['tick'][-1] if seen['tick'] else None}"
    )

    spot = Protobuf.get("ProtoOASpotEvent")
    spot.ctidTraderAccountId = SIM_ACCOUNT_ID
    spot.symbolId = SIM_SYMBOL_ID
    spot.bid = 260340000
    spot.ask = 260360000
    spot.timestamp = int(time.time())
    transport.feed(_wrap(spot))

    depth = Protobuf.get("ProtoOADepthEvent")
    depth.ctidTraderAccountId = SIM_ACCOUNT_ID
    depth.symbolId = SIM_SYMBOL_ID
    dq = depth.newQuotes.add()
    dq.id = 1
    dq.size = 100000
    dq.bid = 260330000
    dq.ask = 260370000
    transport.feed(_wrap(depth))
    typer.echo(
        f"[simulate] fed ProtoOASpotEvent + ProtoOADepthEvent -> "
        f"spot events={len(seen['spot'])} depth events={len(seen['depth'])}"
    )
    typer.echo(f"[simulate] last spot -> {seen['spot'][-1] if seen['spot'] else None}")
    typer.echo(f"[simulate] last depth -> {seen['depth'][-1] if seen['depth'] else None}")

    client.close()
    typer.echo(
        f"[simulate] DONE. total sent requests={len(transport.sent)} final state={client._state}"
    )


# -- OAuth subcommands --------------------------------------------------------

oauth_app = typer.Typer(help="OAuth2 token exchange (requires real credentials in .env).")


def _token_summary(token: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "access_token": token.access_token[:8] + "...",
        "expires_in": token.expires_in,
        "token_type": token.token_type,
        "scope": token.scope,
    }
    summary["refresh_token"] = token.refresh_token[:8] + "..." if token.refresh_token else None
    return summary


@oauth_app.command("refresh")
def oauth_refresh(
    client_id: str = typer.Option(..., "--client-id", envvar="CTRADER_CLIENT_ID"),
    client_secret: str = typer.Option(..., "--client-secret", envvar="CTRADER_CLIENT_SECRET"),
    refresh_token: str = typer.Option(..., "--refresh-token", envvar="CTRADER_REFRESH_TOKEN"),
) -> None:
    """Exchange a refresh token for a new access/refresh token (live network)."""
    token = exchange_refresh_token(client_id, client_secret, refresh_token)
    typer.echo(json.dumps(_token_summary(token), indent=2))


@oauth_app.command("auth-code")
def oauth_auth_code(
    client_id: str = typer.Option(..., "--client-id", envvar="CTRADER_CLIENT_ID"),
    client_secret: str = typer.Option(..., "--client-secret", envvar="CTRADER_CLIENT_SECRET"),
    code: str = typer.Option(..., "--code"),
    redirect_uri: str = typer.Option(..., "--redirect-uri"),
) -> None:
    """Exchange a one-time authorization code for tokens (live network)."""
    token = exchange_authorization_code(client_id, client_secret, code, redirect_uri)
    typer.echo(json.dumps(_token_summary(token), indent=2))


app.add_typer(oauth_app, name="oauth")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
