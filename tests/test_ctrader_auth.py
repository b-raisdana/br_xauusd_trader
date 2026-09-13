"""Unit tests for infrastructure.ctrader_client.auth (OAuth2 token management)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from infrastructure.ctrader_client.auth import (
    TOKEN_URL,
    OAuthClient,
    exchange_authorization_code,
    exchange_refresh_token,
)
from infrastructure.ctrader_client.models import CTraderError, TokenResponse


class TestTOKEN_URL:
    def test_url(self) -> None:
        assert TOKEN_URL == "https://openapi.ctrader.com/apps/token"


class TestExchangeRefreshToken:
    @patch("infrastructure.ctrader_client.auth.requests")
    def test_success(self, mock_requests: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "accessToken": "new_access",
            "refreshToken": "new_refresh",
            "expiresIn": 3600,
            "tokenType": "bearer",
            "scope": "trading",
        }
        mock_requests.get.return_value = mock_resp
        mock_requests.RequestException = requests.RequestException

        token = exchange_refresh_token("client_id", "client_secret", "refresh_token")
        assert token.access_token == "new_access"
        assert token.refresh_token == "new_refresh"
        assert token.expires_in == 3600
        assert token.token_type == "bearer"
        assert token.scope == "trading"

        mock_requests.get.assert_called_once()
        call_kwargs = mock_requests.get.call_args
        assert call_kwargs.kwargs["params"]["grant_type"] == "refresh_token"
        assert call_kwargs.kwargs["params"]["client_id"] == "client_id"

    @patch("infrastructure.ctrader_client.auth.requests")
    def test_error_code_raises(self, mock_requests: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errorCode": "INVALID_REFRESH_TOKEN", "description": "bad"}
        mock_requests.get.return_value = mock_resp
        mock_requests.RequestException = requests.RequestException

        with pytest.raises(CTraderError) as exc_info:
            exchange_refresh_token("cid", "sec", "bad")
        assert exc_info.value.code == "INVALID_REFRESH_TOKEN"
        assert "bad" in exc_info.value.message

    @patch("infrastructure.ctrader_client.auth.requests")
    def test_missing_fields_raises(self, mock_requests: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"something": "else"}
        mock_requests.get.return_value = mock_resp
        mock_requests.RequestException = requests.RequestException

        with pytest.raises(CTraderError, match="missing field"):
            exchange_refresh_token("cid", "sec", "refresh")


class TestExchangeAuthorizationCode:
    @patch("infrastructure.ctrader_client.auth.requests")
    def test_success(self, mock_requests: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "accessToken": "access_from_code",
            "refreshToken": "refresh_from_code",
            "expiresIn": 3600,
            "tokenType": "bearer",
        }
        mock_requests.get.return_value = mock_resp
        mock_requests.RequestException = requests.RequestException

        token = exchange_authorization_code("cid", "sec", "auth_code", "https://redirect.com")
        assert token.access_token == "access_from_code"
        assert token.refresh_token == "refresh_from_code"
        call_kwargs = mock_requests.get.call_args
        assert call_kwargs.kwargs["params"]["grant_type"] == "authorization_code"
        assert call_kwargs.kwargs["params"]["code"] == "auth_code"
        assert call_kwargs.kwargs["params"]["redirect_uri"] == "https://redirect.com"


class TestOAuthClient:
    def test_get_access_token_uses_cache(self) -> None:
        client = OAuthClient(
            client_id="cid",
            client_secret="sec",
            refresh_token="refresh",
            access_token="cached_token",
            _expires_at=9999999999.0,
        )
        assert client.get_access_token() == "cached_token"

    @patch("infrastructure.ctrader_client.auth.exchange_refresh_token")
    def test_get_access_token_refreshes_when_expired(self, mock_exchange: MagicMock) -> None:
        mock_exchange.return_value = TokenResponse(
            access_token="new_access",
            refresh_token="new_refresh",
            expires_in=3600,
            token_type="bearer",
            scope="",
        )
        client = OAuthClient(
            client_id="cid",
            client_secret="sec",
            refresh_token="old_refresh",
            access_token="expired",
            _expires_at=0.0,
        )
        result = client.get_access_token()
        assert result == "new_access"
        assert client.refresh_token == "new_refresh"
        mock_exchange.assert_called_once_with("cid", "sec", "old_refresh")

    def test_get_access_token_no_refresh_token_raises(self) -> None:
        client = OAuthClient(
            client_id="cid",
            client_secret="sec",
            refresh_token=None,
            access_token=None,
        )
        with pytest.raises(CTraderError, match="No refresh token"):
            client.get_access_token()

    def test_from_settings(self) -> None:
        from infrastructure.ctrader_client.settings import CTraderSettings

        settings = CTraderSettings(
            client_id="cid",
            client_secret="sec",
            refresh_token="refresh",
            access_token="access",
            account_login=None,
        )
        client = OAuthClient.from_settings(settings)
        assert client.client_id == "cid"
        assert client.client_secret == "sec"
        assert client.refresh_token == "refresh"
        assert client.access_token == "access"
