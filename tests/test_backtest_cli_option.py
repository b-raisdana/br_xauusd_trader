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


def test_backtest_without_positions_is_skipped_with_warning(monkeypatch, caplog):
    class ManifestStub:
        def successful_days(self, category):
            assert category == "positions"
            return []

    monkeypatch.setattr(
        entrypoint,
        "print_backtest_report",
        lambda *args, **kwargs: pytest.fail("report must not run without positions"),
    )

    completed = entrypoint._print_backtest_if_positions(
        ManifestStub(), report_file="report.parquet", trades_file="trades.parquet"
    )

    assert completed is False
    assert "Backtest skipped" in caplog.text


def test_backtest_with_positions_calls_report(monkeypatch):
    class ManifestStub:
        def successful_days(self, category):
            assert category == "positions"
            return [object()]

    calls = []
    monkeypatch.setattr(entrypoint, "print_backtest_report", lambda *args, **kwargs: calls.append((args, kwargs)))
    manifest = ManifestStub()

    completed = entrypoint._print_backtest_if_positions(
        manifest, report_file="report.parquet", trades_file="trades.parquet", initial_cash=200
    )

    assert completed is True
    assert calls == [
        ((manifest,), {"report_file": "report.parquet", "trades_file": "trades.parquet", "initial_cash": 200})
    ]
