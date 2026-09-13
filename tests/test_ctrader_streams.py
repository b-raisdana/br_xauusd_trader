"""Unit tests for infrastructure.ctrader_client.streams (protobuf builders and parsers)."""

from __future__ import annotations

from ctrader_helpers import wrap
from ctrader_open_api import Protobuf
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAGetAccountListByAccessTokenReq,
    ProtoOAGetTickDataReq,
    ProtoOASubscribeDepthQuotesReq,
    ProtoOASubscribeSpotsReq,
    ProtoOASymbolByIdReq,
    ProtoOASymbolsListReq,
)

from infrastructure.ctrader_client.models import (
    CTraderAccount,
    CTraderError,
    LightSymbolInfo,
)
from infrastructure.ctrader_client.rate import decode_price
from infrastructure.ctrader_client.streams import (
    build_account_auth_request,
    build_application_auth_request,
    build_get_account_list_request,
    build_get_tick_data_request,
    build_subscribe_depth_request,
    build_subscribe_spots_request,
    build_symbol_by_id_request,
    build_symbols_list_request,
    find_symbol_id,
    is_heartbeat,
    parse_accounts,
    parse_depth_event,
    parse_error,
    parse_spot_event,
    parse_symbol,
    parse_symbols_list,
    parse_tick_data_page,
)

# -- builder tests -----------------------------------------------------------


class TestBuildApplicationAuthRequest:
    def test_fields(self) -> None:
        req = build_application_auth_request("cid", "secret")
        assert isinstance(req, ProtoOAApplicationAuthReq)
        assert req.clientId == "cid"
        assert req.clientSecret == "secret"


class TestBuildGetAccountListRequest:
    def test_fields(self) -> None:
        req = build_get_account_list_request("tok123")
        assert isinstance(req, ProtoOAGetAccountListByAccessTokenReq)
        assert req.accessToken == "tok123"


class TestBuildAccountAuthRequest:
    def test_fields(self) -> None:
        req = build_account_auth_request(9011925, "tok123")
        assert isinstance(req, ProtoOAAccountAuthReq)
        assert req.ctidTraderAccountId == 9011925
        assert req.accessToken == "tok123"


class TestBuildSymbolsListRequest:
    def test_fields(self) -> None:
        req = build_symbols_list_request(9011925)
        assert isinstance(req, ProtoOASymbolsListReq)
        assert req.ctidTraderAccountId == 9011925
        assert req.includeArchivedSymbols is False


class TestBuildSymbolByIdRequest:
    def test_single_symbol(self) -> None:
        req = build_symbol_by_id_request(9011925, 100)
        assert isinstance(req, ProtoOASymbolByIdReq)
        assert req.ctidTraderAccountId == 9011925
        assert list(req.symbolId) == [100]


class TestBuildSubscribeSpotsRequest:
    def test_single_symbol(self) -> None:
        req = build_subscribe_spots_request(9011925, [100])
        assert isinstance(req, ProtoOASubscribeSpotsReq)
        assert req.ctidTraderAccountId == 9011925
        assert req.subscribeToSpotTimestamp is True
        assert list(req.symbolId) == [100]

    def test_multiple_symbols(self) -> None:
        req = build_subscribe_spots_request(9011925, [100, 200], include_timestamp=False)
        assert req.subscribeToSpotTimestamp is False
        assert list(req.symbolId) == [100, 200]


class TestBuildSubscribeDepthRequest:
    def test_fields(self) -> None:
        req = build_subscribe_depth_request(9011925, 100)
        assert isinstance(req, ProtoOASubscribeDepthQuotesReq)
        assert req.ctidTraderAccountId == 9011925
        assert list(req.symbolId) == [100]


class TestBuildGetTickDataRequest:
    def test_fields(self) -> None:
        req = build_get_tick_data_request(9011925, 100, 1700000000, 1700003600)
        assert isinstance(req, ProtoOAGetTickDataReq)
        assert req.ctidTraderAccountId == 9011925
        assert req.symbolId == 100
        assert req.type == 1
        assert req.fromTimestamp == 1700000000
        assert req.toTimestamp == 1700003600


# -- parser tests ------------------------------------------------------------


class TestParseAccounts:
    def test_multiple_accounts(self) -> None:
        msg = Protobuf.get("ProtoOAGetAccountListByAccessTokenRes")
        a1 = msg.ctidTraderAccount.add()
        a1.ctidTraderAccountId = 100
        a1.isLive = True
        a1.traderLogin = 9011925
        a2 = msg.ctidTraderAccount.add()
        a2.ctidTraderAccountId = 200
        a2.isLive = False
        a2.traderLogin = 9011926
        accounts = parse_accounts(msg)
        assert accounts[0] == CTraderAccount(100, 9011925, True)
        assert accounts[1] == CTraderAccount(200, 9011926, False)

    def test_no_trader_login(self) -> None:
        msg = Protobuf.get("ProtoOAGetAccountListByAccessTokenRes")
        a = msg.ctidTraderAccount.add()
        a.ctidTraderAccountId = 100
        a.isLive = True
        accounts = parse_accounts(msg)
        assert accounts[0].trader_login == 0


class TestParseSymbolsList:
    def test_multiple_symbols(self) -> None:
        msg = Protobuf.get("ProtoOASymbolsListRes")
        s1 = msg.symbol.add()
        s1.symbolId = 100
        s1.symbolName = "XAUUSD"
        s1.enabled = True
        s1.description = "Gold vs USD"
        s1.baseAssetId = 1
        s1.quoteAssetId = 2
        s2 = msg.symbol.add()
        s2.symbolId = 200
        s2.symbolName = "EURUSD"
        s2.enabled = False
        symbols = parse_symbols_list(msg)
        assert symbols[0] == LightSymbolInfo(100, "XAUUSD", True, "Gold vs USD", 1, 2)
        assert symbols[1] == LightSymbolInfo(200, "EURUSD", False)

    def test_empty(self) -> None:
        msg = Protobuf.get("ProtoOASymbolsListRes")
        assert parse_symbols_list(msg) == []


class TestFindSymbolId:
    def test_found(self) -> None:
        symbols = [LightSymbolInfo(100, "XAUUSD", True), LightSymbolInfo(200, "EURUSD", False)]
        assert find_symbol_id(symbols, "xauusd") == 100

    def test_disabled_skipped(self) -> None:
        symbols = [LightSymbolInfo(200, "EURUSD", False), LightSymbolInfo(100, "XAUUSD", True)]
        assert find_symbol_id(symbols, "EURUSD") is None

    def test_not_found(self) -> None:
        symbols = [LightSymbolInfo(100, "XAUUSD", True)]
        assert find_symbol_id(symbols, "GBPJPY") is None


class TestParseSymbol:
    def test_full_symbol(self) -> None:
        light = LightSymbolInfo(100, "XAUUSD", True, "Gold vs USD", 1, 2)
        msg = Protobuf.get("ProtoOASymbolByIdRes")
        raw = msg.symbol.add()
        raw.digits = 5
        raw.pipPosition = 4
        symbol = parse_symbol(msg, light)
        assert symbol is not None
        assert symbol.symbol_id == 100
        assert symbol.symbol_name == "XAUUSD"
        assert symbol.digits == 5
        assert symbol.pip_position == 4
        assert symbol.enabled is True
        assert symbol.description == "Gold vs USD"
        assert symbol.base_asset_id == 1
        assert symbol.quote_asset_id == 2

    def test_no_symbol(self) -> None:
        light = LightSymbolInfo(100, "XAUUSD", True)
        msg = Protobuf.get("ProtoOASymbolByIdRes")
        assert parse_symbol(msg, light) is None


class TestParseSpotEvent:
    def test_bid_and_ask(self) -> None:
        msg = Protobuf.get("ProtoOASpotEvent")
        msg.symbolId = 100
        msg.bid = 260340
        msg.ask = 260360
        msg.timestamp = 1700000000
        tick = parse_spot_event(msg, 5)
        assert tick.symbol_id == 100
        assert tick.bid == decode_price(260340, 5)
        assert tick.ask == decode_price(260360, 5)
        assert tick.timestamp == 1700000000
        assert tick.has_bid is True
        assert tick.has_ask is True

    def test_bid_only(self) -> None:
        msg = Protobuf.get("ProtoOASpotEvent")
        msg.symbolId = 100
        msg.bid = 260340
        msg.timestamp = 1700000000
        tick = parse_spot_event(msg, 5)
        assert tick.has_bid is True
        assert tick.has_ask is False
        assert tick.ask is None


class TestParseDepthEvent:
    def test_new_and_deleted(self) -> None:
        msg = Protobuf.get("ProtoOADepthEvent")
        msg.symbolId = 100
        q1 = msg.newQuotes.add()
        q1.id = 1
        q1.size = 100000
        q1.bid = 260330
        q1.ask = 260370
        q2 = msg.newQuotes.add()
        q2.id = 2
        q2.size = 50000
        msg.deletedQuotes.append(3)
        update = parse_depth_event(msg, 5)
        assert update.symbol_id == 100
        assert len(update.new_quotes) == 2
        assert update.new_quotes[0].quote_id == 1
        assert update.new_quotes[0].size == 100000
        assert update.new_quotes[0].bid == decode_price(260330, 5)
        assert update.new_quotes[0].ask == decode_price(260370, 5)
        assert update.deleted_quote_ids == (3,)

    def test_empty(self) -> None:
        msg = Protobuf.get("ProtoOADepthEvent")
        msg.symbolId = 100
        update = parse_depth_event(msg, 5)
        assert update.symbol_id == 100
        assert update.new_quotes == ()
        assert update.deleted_quote_ids == ()


class TestParseTickDataPage:
    def test_with_ticks(self) -> None:
        msg = Protobuf.get("ProtoOAGetTickDataRes")
        s1 = msg.tickData.add()
        s1.timestamp = 1700000000
        s1.tick = 260340000
        s2 = msg.tickData.add()
        s2.timestamp = 1700000001
        s2.tick = 260350000
        msg.hasMore = True
        page = parse_tick_data_page(msg, 100)
        assert page.symbol_id == 100
        assert len(page.ticks) == 2
        assert page.ticks[0].timestamp == 1700000000
        assert page.ticks[0].tick == 260340000
        assert page.has_more is True

    def test_decode_prices(self) -> None:
        msg = Protobuf.get("ProtoOAGetTickDataRes")
        s = msg.tickData.add()
        s.timestamp = 1700000000
        s.tick = 260340000
        page = parse_tick_data_page(msg, 100)
        decoded = page.decode_prices(5)
        assert decoded == [(1700000000, 2603.4)]


class TestParseError:
    def test_with_code_and_description(self) -> None:
        msg = Protobuf.get("ProtoOAErrorRes")
        msg.errorCode = "INVALID_TOKEN"
        msg.description = "Token expired"
        error = parse_error(msg)
        assert error.code == "INVALID_TOKEN"
        assert error.message == "Token expired"
        assert isinstance(error, CTraderError)

    def test_without_code(self) -> None:
        msg = Protobuf.get("ProtoOAErrorRes")
        msg.description = "Something went wrong"
        error = parse_error(msg)
        assert error.code is None
        assert error.message == "Something went wrong"

    def test_empty_description(self) -> None:
        msg = Protobuf.get("ProtoOAErrorRes")
        error = parse_error(msg)
        assert error.code is None
        assert error.message == "cTrader error"


class TestIsHeartbeat:
    def test_heartbeat_detected(self) -> None:
        hb = Protobuf.get("ProtoHeartbeatEvent")
        envelope = wrap(hb)
        assert is_heartbeat(envelope) is True

    def test_non_heartbeat(self) -> None:
        err = Protobuf.get("ProtoOAErrorRes")
        err.errorCode = "TEST"
        envelope = wrap(err)
        assert is_heartbeat(envelope) is False
