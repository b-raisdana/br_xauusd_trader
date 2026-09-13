"""Pure builders and parsers for the cTrader Open API protobuf messages.

This module contains no network or Twisted code, so every function here is
unit-tested with synthetic protobuf messages. The ``CTraderClient`` in
``client.py`` is the only place that touches the live TCP transport; it delegates
all message construction and parsing to the functions defined here.

Price encoding
--------------
cTrader transmits every price as an integer scaled by ``10 ** digits`` (see
``infrastructure.ctrader_client.rate.decode_price``). The live spot and depth events therefore
carry raw integers that must be divided by the symbol's ``digits`` to become
human-readable prices; the symbol's ``digits``/``pipPosition`` come from a
``ProtoOASymbolByIdRes`` request, not from the stream itself.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import (
    ProtoHeartbeatEvent,
)
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
from google.protobuf.descriptor import FieldDescriptor

from .models import (
    CTraderAccount,
    CTraderError,
    DepthQuote,
    LightSymbolInfo,
    OrderBookUpdate,
    SpotTick,
    SymbolInfo,
    TickData,
    TickPage,
)
from .rate import decode_price

__all__ = [
    "build_account_auth_request",
    "build_application_auth_request",
    "build_get_account_list_request",
    "build_get_tick_data_request",
    "build_symbol_by_id_request",
    "build_subscribe_depth_request",
    "build_subscribe_spots_request",
    "build_symbols_list_request",
    "find_symbol_id",
    "is_heartbeat",
    "parse_accounts",
    "parse_depth_event",
    "parse_error",
    "parse_spot_event",
    "parse_symbol",
    "parse_symbols_list",
    "parse_tick_data_page",
]


def build_application_auth_request(client_id: str, client_secret: str) -> ProtoOAApplicationAuthReq:
    request = ProtoOAApplicationAuthReq()
    request.clientId = client_id
    request.clientSecret = client_secret
    return request


def build_get_account_list_request(access_token: str) -> ProtoOAGetAccountListByAccessTokenReq:
    request = ProtoOAGetAccountListByAccessTokenReq()
    request.accessToken = access_token
    return request


def build_account_auth_request(account_id: int, access_token: str) -> ProtoOAAccountAuthReq:
    request = ProtoOAAccountAuthReq()
    request.ctidTraderAccountId = account_id
    request.accessToken = access_token
    return request


def build_symbols_list_request(account_id: int) -> ProtoOASymbolsListReq:
    request = ProtoOASymbolsListReq()
    request.ctidTraderAccountId = account_id
    request.includeArchivedSymbols = False
    return request


def build_symbol_by_id_request(account_id: int, symbol_id: int) -> ProtoOASymbolByIdReq:
    request = ProtoOASymbolByIdReq()
    request.ctidTraderAccountId = account_id
    request.symbolId.append(int(symbol_id))
    return request


def build_subscribe_spots_request(
    account_id: int, symbol_ids: Sequence[int], include_timestamp: bool = True
) -> ProtoOASubscribeSpotsReq:
    request = ProtoOASubscribeSpotsReq()
    request.ctidTraderAccountId = account_id
    request.subscribeToSpotTimestamp = include_timestamp
    for symbol_id in symbol_ids:
        request.symbolId.append(int(symbol_id))
    return request


def build_subscribe_depth_request(
    account_id: int, symbol_id: int
) -> ProtoOASubscribeDepthQuotesReq:
    request = ProtoOASubscribeDepthQuotesReq()
    request.ctidTraderAccountId = account_id
    request.symbolId.append(int(symbol_id))
    return request


def build_get_tick_data_request(
    account_id: int, symbol_id: int, from_timestamp: int, to_timestamp: int
) -> ProtoOAGetTickDataReq:
    request = ProtoOAGetTickDataReq()
    request.ctidTraderAccountId = account_id
    request.symbolId = int(symbol_id)
    request.type = 1
    request.fromTimestamp = int(from_timestamp)
    request.toTimestamp = int(to_timestamp)
    return request


def parse_error(message: Any) -> CTraderError:
    """Parse an extracted ``ProtoOAErrorRes`` payload into a :class:`CTraderError`."""
    field = message.DESCRIPTOR.fields_by_name["errorCode"]
    if field.label == FieldDescriptor.LABEL_REPEATED:
        code = ",".join(str(item) for item in message.errorCode)
    elif message.HasField("errorCode"):
        code = str(message.errorCode)
    else:
        code = None
    description = message.description if message.HasField("description") else ""
    return CTraderError(str(description) if description else "cTrader error", code=code)


def parse_accounts(message: Any) -> list[CTraderAccount]:
    """Parse a ``ProtoOAGetAccountListByAccessTokenRes`` into accounts."""
    accounts: list[CTraderAccount] = []
    for raw in message.ctidTraderAccount:
        trader_login = int(raw.traderLogin) if raw.HasField("traderLogin") else 0
        accounts.append(
            CTraderAccount(
                ctid_trader_account_id=int(raw.ctidTraderAccountId),
                trader_login=trader_login,
                is_live=bool(raw.isLive),
            )
        )
    return accounts


def parse_symbols_list(message: Any) -> list[LightSymbolInfo]:
    """Parse a ``ProtoOASymbolsListRes`` into light symbol descriptors."""
    symbols: list[LightSymbolInfo] = []
    for raw in message.symbol:
        symbols.append(
            LightSymbolInfo(
                symbol_id=int(raw.symbolId),
                symbol_name=raw.symbolName,
                enabled=bool(raw.enabled),
                description=raw.description,
                base_asset_id=int(raw.baseAssetId) if raw.baseAssetId else None,
                quote_asset_id=int(raw.quoteAssetId) if raw.quoteAssetId else None,
            )
        )
    return symbols


def find_symbol_id(symbols: Sequence[LightSymbolInfo], symbol_name: str) -> Optional[int]:
    needle = symbol_name.upper().strip()
    for symbol in symbols:
        if symbol.symbol_name.strip().upper() == needle and symbol.enabled:
            return symbol.symbol_id
    return None


def parse_symbol(message: Any, light: LightSymbolInfo) -> Optional[SymbolInfo]:
    """Combine a ``ProtoOASymbolByIdRes`` with its light descriptor to get digits."""
    if not message.symbol:
        return None
    raw = message.symbol[0]
    return SymbolInfo(
        symbol_id=light.symbol_id,
        symbol_name=light.symbol_name,
        digits=int(raw.digits),
        pip_position=int(raw.pipPosition),
        enabled=light.enabled,
        description=light.description,
        base_asset_id=light.base_asset_id,
        quote_asset_id=light.quote_asset_id,
    )


def parse_spot_event(message: Any, digits: int) -> SpotTick:
    """Parse a ``ProtoOASpotEvent`` into a :class:`SpotTick`."""
    has_bid = message.HasField("bid")
    has_ask = message.HasField("ask")
    return SpotTick(
        symbol_id=int(message.symbolId),
        bid=decode_price(message.bid, digits) if has_bid else None,
        ask=decode_price(message.ask, digits) if has_ask else None,
        timestamp=int(message.timestamp),
        has_bid=has_bid,
        has_ask=has_ask,
    )


def parse_depth_event(message: Any, digits: int) -> OrderBookUpdate:
    """Parse a ``ProtoOADepthEvent`` into an :class:`OrderBookUpdate`."""
    new_quotes = tuple(
        DepthQuote(
            quote_id=int(quote.id),
            size=int(quote.size),
            bid=decode_price(quote.bid, digits) if quote.HasField("bid") else None,
            ask=decode_price(quote.ask, digits) if quote.HasField("ask") else None,
        )
        for quote in message.newQuotes
    )
    deleted = tuple(int(quote_id) for quote_id in message.deletedQuotes)
    return OrderBookUpdate(
        symbol_id=int(message.symbolId),
        new_quotes=new_quotes,
        deleted_quote_ids=deleted,
    )


def parse_tick_data_page(message: Any, symbol_id: int) -> TickPage:
    """Parse a ``ProtoOAGetTickDataRes`` into a :class:`TickPage`."""
    ticks = tuple(
        TickData(timestamp=int(sample.timestamp), tick=int(sample.tick))
        for sample in message.tickData
    )
    return TickPage(symbol_id=symbol_id, ticks=ticks, has_more=bool(message.hasMore))


def is_heartbeat(message: Any) -> bool:
    return message.payloadType == ProtoHeartbeatEvent().payloadType
