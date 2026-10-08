from datetime import UTC, datetime

import pytest

from application.xauusd_trading_strategy_1_vector import __main__ as entrypoint


class ManifestStub:
    def __init__(self, position_days):
        self.position_days = position_days

    def successful_days(self, category):
        assert category == "positions"
        return self.position_days


def test_requested_backtest_calls_report_for_position_manifest(monkeypatch):
    manifest = ManifestStub([datetime(2026, 7, 29, tzinfo=UTC)])
    called = []
    monkeypatch.setattr(entrypoint, "print_backtest_report", lambda value: called.append(value))

    entrypoint._run_backtest_report(manifest, requested=True)

    assert called == [manifest]


def test_requested_backtest_rejects_signals_only_manifest(monkeypatch):
    manifest = ManifestStub([])
    monkeypatch.setattr(entrypoint, "print_backtest_report", lambda _: pytest.fail("must not report"))

    with pytest.raises(ValueError, match="signals-only run produced none"):
        entrypoint._run_backtest_report(manifest, requested=True)


def test_backtest_not_requested_does_not_call_report(monkeypatch):
    manifest = ManifestStub([])
    monkeypatch.setattr(entrypoint, "print_backtest_report", lambda _: pytest.fail("must not report"))

    entrypoint._run_backtest_report(manifest, requested=False)
