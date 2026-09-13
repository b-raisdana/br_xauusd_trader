"""Offline smoke tests for the cTrader presentation CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from infrastructure.ctrader_client.models import TokenResponse
from presentation.ctrader.ctrader_cli import app
from presentation.ctrader.ctrader_oauth import load_live_settings

runner = CliRunner()


def test_parse_command_completes_with_synthetic_messages() -> None:
    result = runner.invoke(app, ["parse"])

    assert result.exit_code == 0
    assert "[parse] error -> TEST_ERROR: demo error" in result.stdout


def test_simulate_command_completes_offline_client_lifecycle() -> None:
    result = runner.invoke(app, ["simulate"])

    assert result.exit_code == 0
    assert "total sent requests=8 final state=account_authed" in result.stdout


def test_live_settings_authorizes_and_persists_missing_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CTRADER_CLIENT_ID", "client-id")
    monkeypatch.setenv("CTRADER_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("CTRADER_REFRESH_TOKEN", "")
    monkeypatch.setenv("CTRADER_ACCESS_TOKEN", "")
    token = TokenResponse("access", "refresh", 3600, "bearer", "accounts")

    def authorize(*args: object, **kwargs: object) -> TokenResponse:
        return token

    monkeypatch.setattr("presentation.ctrader.ctrader_oauth.authorize_interactively", authorize)
    monkeypatch.setattr("presentation.ctrader.ctrader_oauth.DEFAULT_ENV_PATH", tmp_path / ".env")

    settings = load_live_settings("stream-orderbook")

    assert settings.access_token == "access"
    assert settings.refresh_token == "refresh"
    assert (tmp_path / ".env").read_text() == "CTRADER_REFRESH_TOKEN=refresh\n"
