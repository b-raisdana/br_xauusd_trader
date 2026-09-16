from __future__ import annotations

from domain.xau_usd.entry import maximum_positions

from .lifecycle import (
    OnInitResult,
    OnInitStatus,
    RuntimeEnvironment,
    SmokeResult,
    SmokeSuite,
)
from .settings import StrategySettings
from .smoke import run_core_vector_smoke


class DefaultSmokeSuite:
    def run_all(self) -> tuple[SmokeResult, ...]:
        return (run_core_vector_smoke(),)


def validate_initialization_settings(
    settings: StrategySettings,
    environment: RuntimeEnvironment,
) -> tuple[str, ...]:
    errors: list[str] = []
    if settings.enable_trading:
        errors.append("live trading is not implemented or approved")

    if settings.observe_native_outcomes and settings.strategy_magic <= 0:
        errors.append("native outcome observation requires a positive strategy magic")

    if settings.enable_tester_execution:
        if not environment.is_tester:
            errors.append("tester execution requires Strategy Tester")
        if settings.strategy_magic <= 0:
            errors.append("tester execution requires a positive strategy magic")
        if not settings.observe_native_outcomes:
            errors.append("tester execution requires native outcome observation")
        if maximum_positions(settings.strategy_capital) < 0:
            errors.append("tester execution requires a supported strategy capital profile")

    if settings.simulate_same_day_restart and not settings.enable_tester_execution:
        errors.append("same-day restart simulation requires guarded tester execution")

    return tuple(errors)


def on_init(
    settings: StrategySettings,
    environment: RuntimeEnvironment | None = None,
    smoke_suite: SmokeSuite | None = None,
) -> OnInitResult:
    if environment is None:
        environment = RuntimeEnvironment()
    errors = validate_initialization_settings(settings, environment)
    if errors:
        return OnInitResult(status=OnInitStatus.FAILED, errors=errors)

    results = smoke_suite.run_all() if smoke_suite is not None else DefaultSmokeSuite().run_all()
    smoke_errors = tuple(f"{result.name}: {result.error}" for result in results if not result.passed)
    if smoke_errors:
        return OnInitResult(status=OnInitStatus.FAILED, errors=smoke_errors, smoke_results=results)

    return OnInitResult(status=OnInitStatus.SUCCEEDED, smoke_results=results)


on_initialize = on_init

__all__ = ["DefaultSmokeSuite", "on_init", "on_initialize", "validate_initialization_settings"]
