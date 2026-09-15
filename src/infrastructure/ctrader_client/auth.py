"""cTrader Open API OAuth2 token management.

The cTrader Open API authenticates applications with an OAuth2 access token
obtained from ``https://openapi.ctrader.com/apps/token``. An access token is
issued once (via the interactive authorization-code grant) and then refreshed
with a refresh token. See ``docs/ctrader.md`` for the one-time setup.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

from .models import CTraderError, TokenResponse

__all__ = [
    "OAuthClient",
    "TOKEN_URL",
    "exchange_authorization_code",
    "exchange_refresh_token",
]

TOKEN_URL = "https://openapi.ctrader.com/apps/token"
REFRESH_GRANT = "refresh_token"
AUTH_CODE_GRANT = "authorization_code"
_TOKEN_TTL_SAFETY_MARGIN = 60


def _exchange(params: dict[str, str]) -> TokenResponse:
    try:
        response = requests.get(TOKEN_URL, params=params, timeout=20)
    except requests.RequestException as exc:
        raise CTraderError(f"OAuth token request failed: {exc}", code="NETWORK") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise CTraderError(f"OAuth token response was not JSON: {response.text[:200]}", code="OAUTH") from exc
    error_code = data.get("errorCode")
    if error_code:
        raise CTraderError(data.get("description") or str(error_code), code=error_code)
    try:
        return TokenResponse(
            access_token=data["accessToken"],
            refresh_token=data["refreshToken"],
            expires_in=int(data.get("expiresIn", 0)),
            token_type=data.get("tokenType", "bearer"),
            scope=data.get("scope", ""),
        )
    except KeyError as exc:
        raise CTraderError(f"OAuth response missing field {exc}", code="OAUTH") from exc


def exchange_refresh_token(client_id: str, client_secret: str, refresh_token: str) -> TokenResponse:
    """Refresh an access token using a stored refresh token."""
    return _exchange(
        {
            "grant_type": REFRESH_GRANT,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    )


def exchange_authorization_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> TokenResponse:
    """Exchange a one-time authorization code for an access + refresh token."""
    return _exchange(
        {
            "grant_type": AUTH_CODE_GRANT,
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )


@dataclass
class OAuthClient:
    """Holds cTrader OAuth credentials and caches a refreshed access token."""

    client_id: str
    client_secret: str
    refresh_token: Optional[str] = None
    access_token: Optional[str] = None
    _expires_at: float = 0.0
    _last_token: Optional[TokenResponse] = None

    def __post_init__(self) -> None:
        if self.access_token and not self._expires_at:
            self._expires_at = time.time()

    @classmethod
    def from_settings(cls, settings) -> "OAuthClient":
        return cls(
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            refresh_token=settings.refresh_token,
            access_token=settings.access_token,
        )

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing first if necessary."""
        if self.access_token and time.time() < self._expires_at:
            return self.access_token
        if not self.refresh_token:
            raise CTraderError("No refresh token configured; complete the OAuth grant first.", code="AUTH")
        token = exchange_refresh_token(self.client_id, self.client_secret, self.refresh_token)
        self.access_token = token.access_token
        self.refresh_token = token.refresh_token or self.refresh_token
        self._last_token = token
        self._expires_at = time.time() + max(1.0, token.expires_in) - _TOKEN_TTL_SAFETY_MARGIN
        return self.access_token
