"""Pytest configuration for xauusd-mvp."""

import pytest
from br_py_log_n_profile import configure

from application.xauusd_trading_strategy_1_vector.config.core_vectors import core_vectors
from application.xauusd_trading_strategy_1_vector.config.strategy_config import strategy_config


def pytest_configure(config: pytest.Config) -> None:
    """Configure br-logging-and-profiling to disable breakpoints on NOT_TESTED during tests."""
    configure(break_on_not_tested=False)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Default every unmarked test to the 'unit' marker for the '-m unit' gate."""
    for item in items:
        if not list(item.iter_markers()):
            item.add_marker(pytest.mark.unit)


@pytest.fixture(autouse=True)
def _bound_strategy_configs():
    with core_vectors.use(), strategy_config.use():
        yield
