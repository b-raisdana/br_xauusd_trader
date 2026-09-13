"""cTrader Open API client for streaming XAUUSD market data.

Public surface:

* :class:`CTraderSettings` -- env-based configuration.
* :class:`OAuthClient` -- OAuth2 refresh/token management.
* :class:`CTraderClient` -- authenticated real-time client (spots, depth, ticks).
* :class:`RealtimeTransport` -- Twisted TCP/SSL transport used by the client.
"""

from __future__ import annotations

from .auth import OAuthClient, exchange_authorization_code, exchange_refresh_token
from .client import CTraderClient, RealtimeTransport, Transport
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
    TokenResponse,
)
from .rate import decode_price, pip_size, point
from .settings import CTraderSettings
from .streams import (
    build_account_auth_request,
    build_application_auth_request,
    build_get_account_list_request,
    build_get_tick_data_request,
    build_subscribe_depth_request,
    build_subscribe_spots_request,
    build_symbol_by_id_request,
    build_symbols_list_request,
)

__all__ = [
    "CTraderAccount",
    "CTraderClient",
    "CTraderError",
    "CTraderSettings",
    "DepthQuote",
    "LightSymbolInfo",
    "OAuthClient",
    "OrderBookUpdate",
    "RealtimeTransport",
    "SpotTick",
    "SymbolInfo",
    "TickData",
    "TickPage",
    "TokenResponse",
    "Transport",
    "build_account_auth_request",
    "build_application_auth_request",
    "build_get_account_list_request",
    "build_get_tick_data_request",
    "build_subscribe_depth_request",
    "build_subscribe_spots_request",
    "build_symbol_by_id_request",
    "build_symbols_list_request",
    "decode_price",
    "exchange_authorization_code",
    "exchange_refresh_token",
    "pip_size",
    "point",
]
