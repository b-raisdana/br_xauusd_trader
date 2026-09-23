"""Pytest configuration for xauusd-mvp."""

import pytest
from br_py_log_n_profile import configure


def pytest_configure(config: pytest.Config) -> None:
    """Configure br-logging-and-profiling to disable breakpoints on NOT_TESTED during tests."""
    configure(break_on_not_tested=False)
