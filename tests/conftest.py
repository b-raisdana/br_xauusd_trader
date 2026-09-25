"""Pytest configuration for xauusd-mvp."""

import pytest
from br_py_log_n_profile import configure

from application.xauusd_trading_strategy_1_vector.config.core_vectors import core_vectors
from application.xauusd_trading_strategy_1_vector.config.strategy_config import strategy_config


def pytest_configure(config: pytest.Config) -> None:
    """Configure br-logging-and-profiling to disable breakpoints on NOT_TESTED during tests."""
    configure(break_on_not_tested=False)


@pytest.fixture(autouse=True)
def _bound_strategy_configs():
    with core_vectors.use(), strategy_config.use():
        yield
