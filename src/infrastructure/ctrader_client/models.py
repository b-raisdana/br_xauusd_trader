"""cTrader Open API client domain models.

Pure value objects used by the request builders and response parsers in
``infrastructure.ctrader_client.streams``. None of these depend on the network
or on the cTrader protobuf runtime, so they are cheap to construct and test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


class CTraderError(Exception):
    """Raised for auth, connection, or protocol-level failures."""

    def __init__(self, message: str, code: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        return f"{self.code or 'error'}: {self.message}"


@dataclass(frozen=True, slots=True)
class TokenResponse:
    """Result of a cTrader OAuth2 token exchange."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"
    scope: str = ""


@dataclass(frozen=True, slots=True)
class LightSymbolInfo:
    """Minimal symbol info from the symbols-list response (no digit scale)."""

    symbol_id: int
    symbol_name: str
    enabled: bool = True
    description: str = ""
    base_asset_id: Optional[int] = None
    quote_asset_id: Optional[int] = None


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """A tradable symbol resolved from the cTrader account."""

    symbol_id: int
    symbol_name: str
    digits: int
    pip_position: int
    enabled: bool = True
    description: str = ""
    base_asset_id: Optional[int] = None
    quote_asset_id: Optional[int] = None

    @property
    def price_scale(self) -> int:
        """Divisor that converts a raw cTrader integer price to a float."""
        return 10**self.digits

    def decode_price(self, raw: int) -> float:
        """Convert a raw cTrader integer price to a floating-point price."""
        return raw / self.price_scale

    @property
    def pip_size(self) -> float:
        """Size of one pip for this symbol (e.g. 0.0001 for a 4-pipPosition FX pair)."""
        return 10**-self.pip_position

    @property
    def point(self) -> float:
        """Size of the smallest quoted price step."""
        return 10**-self.digits


@dataclass(frozen=True, slots=True)
class SpotTick:
    """A live spot/quote tick (ProtoOASpotEvent)."""

    symbol_id: int
    bid: Optional[float]
    ask: Optional[float]
    timestamp: int
    tick_id: Optional[int] = None
    has_bid: bool = False
    has_ask: bool = False


@dataclass(frozen=True, slots=True)
class DepthQuote:
    """A single price level in the order book (ProtoOADepthQuote)."""

    quote_id: int
    size: int
    bid: Optional[float] = None
    ask: Optional[float] = None


@dataclass(frozen=True, slots=True)
class OrderBookUpdate:
    """An order-book delta (ProtoOADepthEvent)."""

    symbol_id: int
    new_quotes: tuple[DepthQuote, ...] = ()
    deleted_quote_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class TickData:
    """A single historical tick sample (ProtoOATickData)."""

    timestamp: int
    tick: int


@dataclass(frozen=True, slots=True)
class TickPage:
    """A page of historical tick data (ProtoOAGetTickDataRes)."""

    symbol_id: int
    ticks: tuple[TickData, ...] = field(default_factory=tuple)
    has_more: bool = False

    def decode_prices(self, digits: int) -> list[tuple[int, float]]:
        """Decode each raw tick into (timestamp, price) using the symbol digit scale."""
        scale = 10**digits
        return [(t.timestamp, t.tick / scale) for t in self.ticks]


@dataclass(frozen=True, slots=True)
class CTraderAccount:
    """A cTID trader account returned by the account-list response."""

    ctid_trader_account_id: int
    trader_login: int
    is_live: bool
