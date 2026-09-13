"""Unit tests for infrastructure.ctrader_client.settings."""

from __future__ import annotations

import pytest

from infrastructure.ctrader_client.models import CTraderError
from infrastructure.ctrader_client.settings import CTraderSettings


@pytest.fixture(autouse=True)
def _clear_ctrader_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "CTRADER_CLIENT_ID",
        "CTRADER_CLIENT_SECRET",
        "CTRADER_REFRESH_TOKEN",
        "CTRADER_ACCESS_TOKEN",
        "CTRADER_ACCOUNT_LOGIN",
        "CTRADER_SYMBOL",
        "CTRADER_HOST",
        "CTRADER_PORT",
    ):
        monkeypatch.delenv(key, raising=False)


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CTRADER_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("CTRADER_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("CTRADER_REFRESH_TOKEN", "test_refresh_token")


class TestFromEnv:
    def test_success_with_refresh_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_required(monkeypatch)
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.client_id == "test_client_id"
        assert settings.client_secret == "test_secret"
        assert settings.refresh_token == "test_refresh_token"
        assert settings.access_token is None

    def test_success_with_access_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTRADER_CLIENT_ID", "test_client_id")
        monkeypatch.setenv("CTRADER_CLIENT_SECRET", "test_secret")
        monkeypatch.setenv("CTRADER_ACCESS_TOKEN", "test_access_token")
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.access_token == "test_access_token"
        assert settings.refresh_token is None

    def test_missing_client_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTRADER_CLIENT_SECRET", "test_secret")
        monkeypatch.setenv("CTRADER_REFRESH_TOKEN", "test_refresh_token")
        with pytest.raises(CTraderError, match="CTRADER_CLIENT_ID"):
            CTraderSettings.from_env(env_path=None)

    def test_missing_client_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTRADER_CLIENT_ID", "test_client_id")
        monkeypatch.setenv("CTRADER_REFRESH_TOKEN", "test_refresh_token")
        with pytest.raises(CTraderError, match="CTRADER_CLIENT_SECRET"):
            CTraderSettings.from_env(env_path=None)

    def test_missing_both_tokens_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CTRADER_CLIENT_ID", "test_client_id")
        monkeypatch.setenv("CTRADER_CLIENT_SECRET", "test_secret")
        with pytest.raises(CTraderError, match="CTRADER_REFRESH_TOKEN"):
            CTraderSettings.from_env(env_path=None)

    def test_defaults_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_required(monkeypatch)
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.symbol == "XAUUSD"
        assert settings.host == "demo.ctraderapi.com"
        assert settings.port == 5035

    def test_custom_symbol_and_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_required(monkeypatch)
        monkeypatch.setenv("CTRADER_SYMBOL", "EURUSD")
        monkeypatch.setenv("CTRADER_HOST", "live.ctraderapi.com")
        monkeypatch.setenv("CTRADER_PORT", "5035")
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.symbol == "EURUSD"
        assert settings.host == "live.ctraderapi.com"

    def test_is_live_true_for_non_demo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_required(monkeypatch)
        monkeypatch.setenv("CTRADER_HOST", "live.ctraderapi.com")
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.is_live is True

    def test_is_live_false_for_demo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_required(monkeypatch)
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.is_live is False

    def test_has_token_true_with_refesh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_required(monkeypatch)
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.has_token is True

    def test_has_token_false_directly(self) -> None:
        settings = CTraderSettings(
            client_id="id",
            client_secret="secret",
            refresh_token=None,
            access_token=None,
            account_login=None,
        )
        assert settings.has_token is False

    def test_account_login_parsed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_required(monkeypatch)
        monkeypatch.setenv("CTRADER_ACCOUNT_LOGIN", "9011925")
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.account_login == 9011925

    def test_account_login_fallback_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_required(monkeypatch)
        monkeypatch.setenv("ctrader_demo_account_login_number", "12345")
        settings = CTraderSettings.from_env(env_path=None)
        assert settings.account_login == 12345
