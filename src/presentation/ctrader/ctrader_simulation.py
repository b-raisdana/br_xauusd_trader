"""Offline cTrader client state-machine simulation."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

import typer
from ctrader_open_api import Protobuf
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoMessage

from infrastructure.ctrader_client import CTraderClient, CTraderSettings, OAuthClient
from presentation.ctrader.ctrader_samples import (
    SIM_ACCOUNT_ID,
    SIM_SYMBOL_ID,
    SIM_TICKER,
    _make_account_list,
    _symbol_by_id_message,
    _symbols_list_message,
)


def _wrap(message: Any) -> ProtoMessage:
    envelope = ProtoMessage()
    envelope.payloadType = message.payloadType
    envelope.payload = message.SerializeToString()
    return envelope


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


def simulate() -> None:
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
    sample = tick.tickData.add()
    sample.timestamp = 1700000000
    sample.tick = 260340000
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
