"""Offline smoke tests for the cTrader presentation CLI."""

from typer.testing import CliRunner

from presentation.ctrader.ctrader_cli import app

runner = CliRunner()


def test_parse_command_completes_with_synthetic_messages() -> None:
    result = runner.invoke(app, ["parse"])

    assert result.exit_code == 0
    assert "[parse] error -> TEST_ERROR: demo error" in result.stdout


def test_simulate_command_completes_offline_client_lifecycle() -> None:
    result = runner.invoke(app, ["simulate"])

    assert result.exit_code == 0
    assert "total sent requests=8 final state=account_authed" in result.stdout
