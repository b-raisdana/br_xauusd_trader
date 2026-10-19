from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from application.xauusd_trading_strategy_1_vector import __main__ as entrypoint
from infrastructure.result_processing.io import ResultCategory, ResultFilesManifest


class ManifestStub(ResultFilesManifest):
    position_days: list[datetime]

    def successful_days(self, category: ResultCategory) -> list[datetime]:
        assert category == "positions"
        return self.position_days


@pytest.mark.parametrize(("args", "expected"), [([], True), (["--no-backtest"], False)])
def test_cli_backtest_enabled_by_default_and_disabled_by_switch(
    monkeypatch: pytest.MonkeyPatch, args: list[str], expected: bool
) -> None:
    received: dict[str, Any] = {}

    async def fake_main(**kwargs: Any) -> None:
        received.update(kwargs)

    monkeypatch.setattr(entrypoint, "main", fake_main)

    result = CliRunner().invoke(entrypoint.app, args)

    assert result.exit_code == 0, result.output
    assert received["backtest"] is expected


def test_backtest_without_positions_is_skipped_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        entrypoint,
        "print_backtest_report",
        lambda *args, **kwargs: pytest.fail("report must not run without positions"),
    )

    completed = entrypoint._print_backtest_if_positions(
        ManifestStub(root=tmp_path, position_days=[]), report_file="report.parquet", trades_file="trades.parquet"
    )

    assert completed is False
    assert "Backtest skipped" in caplog.text


def test_backtest_with_positions_calls_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(entrypoint, "print_backtest_report", lambda *args, **kwargs: calls.append((args, kwargs)))
    manifest = ManifestStub(root=tmp_path, position_days=[datetime(2026, 1, 1, tzinfo=UTC)])

    completed = entrypoint._print_backtest_if_positions(
        manifest, report_file="report.parquet", trades_file="trades.parquet", initial_cash=200
    )

    assert completed is True
    assert calls == [
        ((manifest,), {"report_file": "report.parquet", "trades_file": "trades.parquet", "initial_cash": 200})
    ]
