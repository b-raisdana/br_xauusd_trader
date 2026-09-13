"""Unit tests for ctrader_client.client state machine with a fake transport."""

from __future__ import annotations

from ctrader_helpers import wrap
from ctrader_open_api import Protobuf
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAGetAccountListByAccessTokenRes,
)

from ctrader_client.auth import OAuthClient
from ctrader_client.client import CTraderClient
from ctrader_client.models import CTraderError, SpotTick, SymbolInfo, TickPage
from ctrader_client.settings import CTraderSettings


class FakeOAuth(OAuthClient):
    """Lightweight OAuthClient subclass returning a fixed token."""

    def __init__(self, token: str = "fake_token") -> None:
        self.client_id = "fake_id"
        self.client_secret = "fake_secret"
        self.refresh_token: str | None = None
        self.access_token = token
        self._expires_at: float = float("inf")
        self._last_token = None
        self.calls = 0

    def get_access_token(self) -> str:
        self.calls += 1
        return self.access_token or ""


class FakeTransport:
    """Records sent messages and exposes callback registration."""

    def __init__(self) -> None:
        self.sent: list = []
        self._connected_cb = None
        self._message_cb = None
        self._disconnected_cb = None

    def on_connected(self, callback) -> None:
        self._connected_cb = callback

    def on_message(self, callback) -> None:
        self._message_cb = callback

    def on_disconnected(self, callback) -> None:
        self._disconnected_cb = callback

    def connect(self) -> None:
        if self._connected_cb is not None:
            self._connected_cb()

    def send(self, message) -> None:
        self.sent.append(message)

    def close(self) -> None:
        pass

    def feed(self, message) -> None:
        assert self._message_cb is not None
        self._message_cb(message)


def _settings(account_login: int | None = 9011925) -> CTraderSettings:
    return CTraderSettings(
        client_id="test_id",
        client_secret="test_secret",
        refresh_token="refresh",
        access_token="access",
        account_login=account_login,
        symbol="XAUUSD",
    )


def _make_acct_list(
    account_id: int = 9011925, login: int = 9011925, is_live: bool = True
) -> ProtoOAGetAccountListByAccessTokenRes:
    msg = Protobuf.get("ProtoOAGetAccountListByAccessTokenRes")
    msg.accessToken = "fake_token"
    acct = msg.ctidTraderAccount.add()
    acct.ctidTraderAccountId = account_id
    acct.traderLogin = login
    acct.isLive = is_live
    return msg


def _authed_client(login: int | None = 9011925) -> tuple[CTraderClient, FakeTransport]:
    """Create a client and run it through the full auth flow."""
    settings = _settings(account_login=login)
    transport = FakeTransport()
    client = CTraderClient(settings, oauth=FakeOAuth(), transport=transport)
    client.connect()
    transport.feed(wrap(Protobuf.get("ProtoOAApplicationAuthRes")))
    transport.feed(wrap(_make_acct_list()))
    transport.feed(wrap(Protobuf.get("ProtoOAAccountAuthRes", ctidTraderAccountId=9011925)))
    assert client._state == "account_authed"
    return client, transport


# -- connection --------------------------------------------------------------


class TestConnection:
    def test_connect_sends_app_auth(self) -> None:
        settings = _settings()
        transport = FakeTransport()
        client = CTraderClient(settings, oauth=FakeOAuth(), transport=transport)
        client.connect()
        assert len(transport.sent) == 1
        req = transport.sent[0]
        assert req.payloadType == Protobuf.get("ProtoOAApplicationAuthReq").payloadType
        assert req.clientId == "test_id"
        assert req.clientSecret == "test_secret"

    def test_initial_state(self) -> None:
        settings = _settings()
        transport = FakeTransport()
        client = CTraderClient(settings, oauth=FakeOAuth(), transport=transport)
        assert client._state == "new"
        assert client._account_id is None


# -- auth flow ---------------------------------------------------------------


class TestAuthFlow:
    def test_full_auth_flow(self) -> None:
        settings = _settings()
        transport = FakeTransport()
        client = CTraderClient(settings, oauth=FakeOAuth(), transport=transport)

        client.connect()
        assert len(transport.sent) == 1

        transport.feed(wrap(Protobuf.get("ProtoOAApplicationAuthRes")))
        assert client._state == "app_authed"
        assert client._access_token == "fake_token"
        assert len(transport.sent) == 2

        transport.feed(wrap(_make_acct_list()))
        assert client._account_id == 9011925
        assert len(transport.sent) == 3

        acct_auth = Protobuf.get("ProtoOAAccountAuthRes")
        acct_auth.ctidTraderAccountId = 9011925
        transport.feed(wrap(acct_auth))
        assert client._state == "account_authed"
        assert client._ready.called
        assert len(transport.sent) == 3

    def test_account_selected_by_login(self) -> None:
        settings = _settings(account_login=123)
        transport = FakeTransport()
        client = CTraderClient(settings, oauth=FakeOAuth(), transport=transport)
        client.connect()

        msg = Protobuf.get("ProtoOAGetAccountListByAccessTokenRes")
        msg.accessToken = "fake_token"
        a1 = msg.ctidTraderAccount.add()
        a1.ctidTraderAccountId = 111
        a1.traderLogin = 456
        a1.isLive = False
        a2 = msg.ctidTraderAccount.add()
        a2.ctidTraderAccountId = 222
        a2.traderLogin = 123
        a2.isLive = True
        transport.feed(wrap(Protobuf.get("ProtoOAApplicationAuthRes")))
        transport.feed(wrap(msg))
        assert client._account_id == 222

    def test_no_account_selected(self) -> None:
        settings = _settings(account_login=None)
        transport = FakeTransport()
        client = CTraderClient(settings, oauth=FakeOAuth(), transport=transport)
        client.connect()
        transport.feed(wrap(Protobuf.get("ProtoOAApplicationAuthRes")))
        transport.feed(wrap(_make_acct_list()))
        assert client._state != "account_authed"


# -- message routing ---------------------------------------------------------


class TestMessageRouting:
    def test_heartbeat_ignored(self) -> None:
        client, transport = _authed_client()
        before = len(transport.sent)
        transport.feed(wrap(Protobuf.get("ProtoHeartbeatEvent")))
        assert len(transport.sent) == before

    def test_error_routed_to_state(self) -> None:
        client, transport = _authed_client()
        err = Protobuf.get("ProtoOAErrorRes")
        err.errorCode = "TEST_ERROR"
        err.description = "something failed"
        transport.feed(wrap(err))
        assert client._state == "error"

    def test_error_notifies_handler(self) -> None:
        client, transport = _authed_client()
        received: list[CTraderError] = []
        client.on("error", received.append)
        err = Protobuf.get("ProtoOAErrorRes")
        err.errorCode = "TEST_ERROR"
        err.description = "something failed"
        transport.feed(wrap(err))
        assert len(received) == 1
        assert received[0].code == "TEST_ERROR"

    def test_unknown_payload_type_ignored(self) -> None:
        client, transport = _authed_client()
        before = len(transport.sent)
        msg = Protobuf.get("ProtoOAApplicationAuthReq")
        msg.clientId = "test"
        msg.clientSecret = "secret"
        transport.feed(wrap(msg))
        assert len(transport.sent) == before


# -- stream dispatch ---------------------------------------------------------


class TestStreamDispatch:
    def test_spot_event_with_symbol(self) -> None:
        client, transport = _authed_client()
        client._symbols[100] = SymbolInfo(
            symbol_id=100,
            symbol_name="XAUUSD",
            digits=5,
            pip_position=4,
        )

        received: list[SpotTick] = []
        client.on("spot", received.append)

        spot = Protobuf.get("ProtoOASpotEvent")
        spot.ctidTraderAccountId = 9011925
        spot.symbolId = 100
        spot.bid = 260340000
        spot.ask = 260360000
        spot.timestamp = 1700000000
        transport.feed(wrap(spot))
        assert len(received) == 1
        assert received[0].symbol_id == 100
        assert received[0].bid == 2603.4
        assert received[0].ask == 2603.6

    def test_spot_event_without_symbol_ignored(self) -> None:
        client, transport = _authed_client()
        received: list = []
        client.on("spot", received.append)

        spot = Protobuf.get("ProtoOASpotEvent")
        spot.ctidTraderAccountId = 9011925
        spot.symbolId = 999
        spot.bid = 260340
        spot.timestamp = 1700000000
        transport.feed(wrap(spot))
        assert received == []

    def test_depth_event_with_symbol(self) -> None:
        client, transport = _authed_client()
        client._symbols[100] = SymbolInfo(
            symbol_id=100,
            symbol_name="XAUUSD",
            digits=5,
            pip_position=4,
        )

        received: list = []
        client.on("depth", received.append)

        depth = Protobuf.get("ProtoOADepthEvent")
        depth.ctidTraderAccountId = 9011925
        depth.symbolId = 100
        q = depth.newQuotes.add()
        q.id = 1
        q.size = 100000
        q.bid = 260330000
        q.ask = 260370000
        transport.feed(wrap(depth))
        assert len(received) == 1
        assert received[0].symbol_id == 100
        assert received[0].new_quotes[0].bid == 2603.3

    def test_depth_event_without_symbol_ignored(self) -> None:
        client, transport = _authed_client()
        received: list = []
        client.on("depth", received.append)
        depth = Protobuf.get("ProtoOADepthEvent")
        depth.ctidTraderAccountId = 9011925
        depth.symbolId = 999
        q = depth.newQuotes.add()
        q.id = 1
        q.size = 100000
        transport.feed(wrap(depth))
        assert received == []


# -- symbol resolution -------------------------------------------------------


class TestSymbolResolution:
    def test_resolve_symbol(self) -> None:
        client, transport = _authed_client()
        deferred = client.resolve_symbol("XAUUSD")
        assert len(transport.sent) == 4
        assert transport.sent[-1].payloadType == Protobuf.get("ProtoOASymbolsListReq").payloadType

        syms = Protobuf.get("ProtoOASymbolsListRes")
        syms.ctidTraderAccountId = 9011925
        s = syms.symbol.add()
        s.symbolId = 100
        s.symbolName = "XAUUSD"
        s.enabled = True
        s.description = "Gold vs USD"
        s.baseAssetId = 1
        s.quoteAssetId = 2
        transport.feed(wrap(syms))
        assert len(transport.sent) == 5
        assert transport.sent[-1].payloadType == Protobuf.get("ProtoOASymbolByIdReq").payloadType

        sym_by_id = Protobuf.get("ProtoOASymbolByIdRes")
        sym_by_id.ctidTraderAccountId = 9011925
        raw = sym_by_id.symbol.add()
        raw.symbolId = 100
        raw.digits = 5
        raw.pipPosition = 4
        transport.feed(wrap(sym_by_id))
        assert deferred.called
        result = deferred.result
        assert isinstance(result, SymbolInfo)
        assert result.symbol_id == 100
        assert result.digits == 5


# -- tick data fetch ---------------------------------------------------------


class TestTickDataFetch:
    def test_fetch_tick_data(self) -> None:
        client, transport = _authed_client()
        received: list[TickPage] = []
        client.on("tick", received.append)

        deferred = client.fetch_tick_data(100, 1700000000, 1700003600)
        assert len(transport.sent) == 4
        assert transport.sent[-1].payloadType == Protobuf.get("ProtoOAGetTickDataReq").payloadType

        tick_data = Protobuf.get("ProtoOAGetTickDataRes")
        tick_data.ctidTraderAccountId = 9011925
        sample = tick_data.tickData.add()
        sample.timestamp = 1700000000
        sample.tick = 260340000
        tick_data.hasMore = False
        transport.feed(wrap(tick_data))
        assert deferred.called
        assert len(received) == 1
        assert received[0].symbol_id == 100
        assert len(received[0].ticks) == 1
