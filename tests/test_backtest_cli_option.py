import pytest
from typer.testing import CliRunner

from application.xauusd_trading_strategy_1_vector import __main__ as entrypoint


@pytest.mark.parametrize(("args", "expected"), [([], True), (["--no-backtest"], False)])
def test_cli_backtest_enabled_by_default_and_disabled_by_switch(monkeypatch, args, expected):
    received = {}

    async def fake_main(**kwargs):
        received.update(kwargs)

    monkeypatch.setattr(entrypoint, "main", fake_main)

    result = CliRunner().invoke(entrypoint.app, args)

    assert result.exit_code == 0, result.output
    assert received["backtest"] is expected
