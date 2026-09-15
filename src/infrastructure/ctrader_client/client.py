"""cTrader Open API real-time client.

The client is split into two layers:

* :class:`RealtimeTransport` performs the SSL/TCP connection and message I/O
  using the ``ctrader-open-api`` Twisted client. It is the only component that
  talks to the network.
* :class:`CTraderClient` owns the application-level state machine (connect ->
  authorise the application -> list accounts -> authorise the account ->
  resolve symbols -> subscribe to streams) and routes every received message
  through :meth:`receive`, which is a pure function of incoming messages and
  outgoing ``transport.send`` calls. That makes the whole auth/ subscription
  flow unit-testable with a fake transport and synthetic protobuf messages.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol

from ctrader_open_api import Client, Protobuf, TcpProtocol
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthRes,
    ProtoOAApplicationAuthRes,
    ProtoOADepthEvent,
    ProtoOAErrorRes,
    ProtoOAGetAccountListByAccessTokenRes,
    ProtoOAGetTickDataRes,
    ProtoOASpotEvent,
    ProtoOASymbolByIdRes,
    ProtoOASymbolsListRes,
)
from twisted.internet import reactor  # noqa: F401  (required by the transport)
from twisted.internet.defer import Deferred

from .auth import OAuthClient
from .models import (
    CTraderAccount,
    CTraderError,
    LightSymbolInfo,
    SymbolInfo,
)
from .streams import (
    build_account_auth_request,
    build_application_auth_request,
    build_get_account_list_request,
    build_get_tick_data_request,
    build_subscribe_depth_request,
    build_subscribe_spots_request,
    build_symbol_by_id_request,
    build_symbols_list_request,
    is_heartbeat,
    parse_accounts,
    parse_depth_event,
    parse_error,
    parse_spot_event,
    parse_symbol,
    parse_symbols_list,
    parse_tick_data_page,
)

__all__ = ["CTraderClient", "RealtimeTransport", "Transport"]

# Payload-type constants (one int per message kind) used to route messages.
PT_ERROR = ProtoOAErrorRes().payloadType
PT_APP_AUTH_RES = ProtoOAApplicationAuthRes().payloadType
PT_ACCOUNT_LIST_RES = ProtoOAGetAccountListByAccessTokenRes().payloadType
PT_ACCOUNT_AUTH_RES = ProtoOAAccountAuthRes().payloadType
PT_SYMBOLS_LIST_RES = ProtoOASymbolsListRes().payloadType
PT_SYMBOL_BY_ID_RES = ProtoOASymbolByIdRes().payloadType
PT_SPOT_EVENT = ProtoOASpotEvent().payloadType
PT_DEPTH_EVENT = ProtoOADepthEvent().payloadType
PT_TICK_DATA_RES = ProtoOAGetTickDataRes().payloadType


class Transport(Protocol):
    """Minimal network transport the client depends on (dependency-injected)."""

    def connect(self) -> None: ...

    def send(self, message: Any) -> Any: ...

    def close(self) -> None: ...

    def on_connected(self, callback: Callable[[], None]) -> None: ...

    def on_message(self, callback: Callable[[Any], None]) -> None: ...

    def on_disconnected(self, callback: Callable[[Any], None]) -> None: ...


class RealtimeTransport:
    """Live TCP/SSL transport backed by the ``ctrader-open-api`` Twisted client."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._client = Client(settings.host, settings.port, TcpProtocol)
        self._on_connected_cb: Optional[Callable[[], None]] = None
        self._on_message_cb: Optional[Callable[[Any], None]] = None
        self._on_disconnected_cb: Optional[Callable[[Any], None]] = None
        self._client.setConnectedCallback(self._connected)
        self._client.setDisconnectedCallback(self._disconnected)
        self._client.setMessageReceivedCallback(self._received)

    def on_connected(self, callback: Callable[[], None]) -> None:
        self._on_connected_cb = callback

    def on_message(self, callback: Callable[[Any], None]) -> None:
        self._on_message_cb = callback

    def on_disconnected(self, callback: Callable[[Any], None]) -> None:
        self._on_disconnected_cb = callback

    def connect(self) -> None:
        self._client.startService()

    def send(self, message: Any) -> Any:
        return self._client.send(message)

    def close(self) -> None:
        try:
            self._client.stopService()
        except Exception:
            pass

    def _connected(self, _client: Any) -> None:
        if self._on_connected_cb is not None:
            self._on_connected_cb()

    def _disconnected(self, _client: Any, reason: Any) -> None:
        if self._on_disconnected_cb is not None:
            self._on_disconnected_cb(reason)

    def _received(self, _client: Any, message: Any) -> None:
        if self._on_message_cb is not None:
            self._on_message_cb(message)


class CTraderClient:
    """Authenticated cTrader Open API client and stream dispatcher."""

    def __init__(
        self,
        settings: Any,
        oauth: Optional[OAuthClient] = None,
        transport: Optional[Transport] = None,
    ) -> None:
        self.settings = settings
        self._oauth = oauth or OAuthClient.from_settings(settings)
        self._transport: Transport = transport or RealtimeTransport(settings)
        self._access_token: Optional[str] = None
        self._account_id: Optional[int] = None
        self._symbols: dict[int, SymbolInfo] = {}
        self._lights_by_id: dict[int, LightSymbolInfo] = {}
        self._pending_resolve: Optional[tuple[str, "Deferred"]] = None
        self._pending_light: Optional[LightSymbolInfo] = None
        self._pending_tick: Optional[tuple[int, "Deferred"]] = None
        self._handlers: dict[str, list[Callable[..., None]]] = {}
        self._state = "new"
        self._ready: "Deferred" = Deferred()
        self._select_account_login = getattr(settings, "account_login", None)
        self._transport.on_connected(self._on_transport_connected)
        self._transport.on_message(self.receive)
        self._transport.on_disconnected(self._on_disconnected)

    # -- public API --------------------------------------------------------

    def on(self, event: str, handler: Callable[..., None]) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def connect(self) -> None:
        """Open the transport and send the application-auth request."""
        self._transport.connect()

    def wait_ready(self) -> Deferred:
        """Deferred that fires with the account id once the session is authed."""
        return self._ready

    def resolve_symbol(self, symbol_name: str) -> Deferred:
        """Fetch the catalogue, then the full symbol, for ``symbol_name``."""
        deferred: Deferred = Deferred()
        self._pending_resolve = (symbol_name, deferred)
        assert self._account_id is not None
        self._send(build_symbols_list_request(self._account_id))
        return deferred

    def subscribe_live_price(self, symbol_id: int) -> None:
        """Subscribe to live spot/quote ticks (the live-price snapshot source)."""
        assert self._account_id is not None
        self._send(build_subscribe_spots_request(self._account_id, [symbol_id]))

    def subscribe_tick_stream(self, symbol_id: int) -> None:
        """Subscribe to the live tick/price stream (ProtoOASpotEvent)."""
        assert self._account_id is not None
        self._send(build_subscribe_spots_request(self._account_id, [symbol_id]))

    def subscribe_orderbook(self, symbol_id: int) -> None:
        """Subscribe to order-book depth updates for ``symbol_id``."""
        assert self._account_id is not None
        self._send(build_subscribe_depth_request(self._account_id, symbol_id))

    def fetch_tick_data(self, symbol_id: int, from_timestamp: int, to_timestamp: int) -> Deferred:
        """Request a page of historical tick data."""
        deferred: Deferred = Deferred()
        self._pending_tick = (symbol_id, deferred)
        assert self._account_id is not None
        self._send(build_get_tick_data_request(self._account_id, symbol_id, from_timestamp, to_timestamp))
        return deferred

    def close(self) -> None:
        self._transport.close()

    # -- transport callbacks ----------------------------------------------

    def _on_transport_connected(self) -> None:
        self._set_state("connected")
        self._send(build_application_auth_request(self.settings.client_id, self.settings.client_secret))

    def _on_disconnected(self, reason: Any) -> None:
        self._set_state("disconnected")
        self._notify("disconnected", reason)

    # -- message dispatch -------------------------------------------------

    def receive(self, message: Any) -> None:
        """Route one incoming transport message through the state machine."""
        if is_heartbeat(message):
            return
        payload_type = message.payloadType
        inner = Protobuf.extract(message)
        if payload_type == PT_ERROR:
            self._route_error(inner)
        elif payload_type == PT_APP_AUTH_RES:
            self._route_app_auth_res()
        elif payload_type == PT_ACCOUNT_LIST_RES:
            self._route_account_list_res(inner)
        elif payload_type == PT_ACCOUNT_AUTH_RES:
            self._route_account_auth_res(inner)
        elif payload_type == PT_SYMBOLS_LIST_RES:
            self._route_symbols_list_res(inner)
        elif payload_type == PT_SYMBOL_BY_ID_RES:
            self._route_symbol_by_id_res(inner)
        elif payload_type == PT_SPOT_EVENT:
            self._route_spot_event(inner)
        elif payload_type == PT_DEPTH_EVENT:
            self._route_depth_event(inner)
        elif payload_type == PT_TICK_DATA_RES:
            self._route_tick_data_res(inner)
        # Unknown payload types are ignored for forward compatibility.

    def _route_error(self, message: Any) -> None:
        error = parse_error(message)
        self._set_state("error")
        self._notify("error", error)
        if not self._ready.called:
            self._ready.errback(error)

    def _route_app_auth_res(self) -> None:
        if self._state != "connected":
            return
        try:
            self._access_token = self._oauth.get_access_token()
        except CTraderError as exc:
            self._notify("error", exc)
            if not self._ready.called:
                self._ready.errback(exc)
            return
        self._set_state("app_authed")
        assert self._access_token is not None
        self._send(build_get_account_list_request(self._access_token))

    def _route_account_list_res(self, message: Any) -> None:
        accounts = parse_accounts(message)
        account = self._select_account(accounts)
        if account is None:
            error = CTraderError(
                "The access token is valid but owns no authorised account",
                code="NO_ACCOUNT",
            )
            self._notify("error", error)
            if not self._ready.called:
                self._ready.errback(error)
            return
        self._account_id = account.ctid_trader_account_id
        assert self._access_token is not None
        self._send(build_account_auth_request(account.ctid_trader_account_id, self._access_token))

    def _route_account_auth_res(self, message: Any) -> None:
        self._account_id = message.ctidTraderAccountId
        self._set_state("account_authed")
        if not self._ready.called:
            self._ready.callback(self._account_id)

    def _route_symbols_list_res(self, message: Any) -> None:
        lights = parse_symbols_list(message)
        for light in lights:
            self._lights_by_id[light.symbol_id] = light
        self._notify("symbols", lights)
        if self._pending_resolve is not None:
            name, _deferred = self._pending_resolve
            symbol_id = self._lookup_symbol_id(name, lights)
            if symbol_id is not None:
                lookup = self._lights_by_id.get(symbol_id)
                if lookup is not None:
                    self._pending_light = lookup
                assert self._account_id is not None
                self._send(build_symbol_by_id_request(self._account_id, symbol_id))

    def _route_symbol_by_id_res(self, message: Any) -> None:
        if self._pending_resolve is None or self._pending_light is None:
            return
        name, deferred = self._pending_resolve
        symbol = parse_symbol(message, self._pending_light)
        if symbol is not None:
            self._symbols[symbol.symbol_id] = symbol
        if deferred.called:
            return
        deferred.callback(symbol)
        self._pending_resolve = None
        self._pending_light = None

    def _route_spot_event(self, message: Any) -> None:
        digits = self._digits_for(message.symbolId)
        if digits is None:
            return
        self._notify("spot", parse_spot_event(message, digits))

    def _route_depth_event(self, message: Any) -> None:
        digits = self._digits_for(message.symbolId)
        if digits is None:
            return
        self._notify("depth", parse_depth_event(message, digits))

    def _route_tick_data_res(self, message: Any) -> None:
        if self._pending_tick is None:
            return
        symbol_id, deferred = self._pending_tick
        self._pending_tick = None
        page = parse_tick_data_page(message, symbol_id)
        self._notify("tick", page)
        if not deferred.called:
            deferred.callback(page)

    def _digits_for(self, symbol_id: int) -> Optional[int]:
        symbol = self._symbols.get(symbol_id)
        return symbol.digits if symbol is not None else None

    # -- helpers -----------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self._state = state

    def _notify(self, event: str, *args: Any) -> None:
        for handler in list(self._handlers.get(event, [])):
            handler(*args)

    def _send(self, message: Any) -> Any:
        return self._transport.send(message)

    def _select_account(self, accounts: list[CTraderAccount]) -> Optional[CTraderAccount]:
        if not accounts:
            return None
        login = self._select_account_login
        if login is not None:
            for account in accounts:
                if account.trader_login == login:
                    return account
        return accounts[0]

    @staticmethod
    def _lookup_symbol_id(name: str, symbols: list[LightSymbolInfo]) -> Optional[int]:
        needle = name.upper().strip()
        for symbol in symbols:
            if symbol.symbol_name.strip().upper() == needle and symbol.enabled:
                return symbol.symbol_id
        return None
