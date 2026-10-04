"""Pytest configuration for xauusd-mvp.

TEST TIER REGISTRY
------------------
This table is the classification authority. Every test module is listed exactly
once, so `python scripts/dev.py inspect` and any reviewer can audit the whole
tiering from one place. Adding a module without classifying it fails the run
below rather than silently landing in the default selection.

Evidence classes are deliberately distinct and must not be conflated:

* ``unit``        - deterministic in-process regression. Proves behavior.
* ``integration`` - filesystem, subprocess, packaging or optional-tooling
                    boundaries. Proves wiring.
* ``parity``      - comparison against a recorded or synthetic reference.
                    Proves equivalence only for the inputs it carries.
* ``native``      - requires MetaTrader5 / broker / tester. Currently empty:
                    native evidence comes from the MT5 toolchain, not pytest.
                    An empty selection is a legitimate BLOCKED prerequisite,
                    and `dev.py test --tier native` fails loudly on it.
* ``perf``        - timing/memory measurement. Never part of a correctness gate.
"""

import pytest
from br_py_log_n_profile import configure

from application.xauusd_trading_strategy_1_vector.config.core_vectors import core_vectors
from application.xauusd_trading_strategy_1_vector.config.strategy_config import strategy_config

TIER_BY_MODULE: dict[str, str] = {
    # unit: pure computation, no external boundary
    "test_backtest_signals.py": "unit",
    "test_datetime_schemas.py": "unit",
    "test_mt5_input_validation.py": "unit",
    "test_mt5_zone_loader.py": "unit",
    "test_vectorized_breakouts.py": "unit",
    "test_vectorized_cache.py": "unit",
    "test_vectorized_execution.py": "unit",
    "test_vectorized_pipeline.py": "unit",
    "test_vectorized_pullbacks.py": "unit",
    "test_vectorized_reversal.py": "unit",
    "test_vectorized_state.py": "unit",
    "test_vectorized_tick_separation.py": "unit",
    "test_vectorized_validation.py": "unit",
    "test_vectorized_where.py": "unit",
    # parity: comparison evidence, not plain regression
    "test_recorded_native_replay.py": "parity",
    "test_robust_mt5_parity.py": "parity",
    # integration: external boundaries
    "test_backtest_import_isolation.py": "integration",
    "test_optional_dependencies.py": "integration",
    "test_result_manifest.py": "integration",
}

KNOWN_TIERS = ("unit", "integration", "parity", "native", "perf")


def pytest_configure(config: pytest.Config) -> None:
    """Disable breakpoint escalation and register every declared marker."""
    configure(break_on_not_tested=False)
    for tier in KNOWN_TIERS:
        config.addinivalue_line("markers", f"{tier}: see tests/conftest.py TEST TIER REGISTRY")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the registry tier and fail loudly on an unclassified module."""
    unknown: dict[str, list[str]] = {}
    for item in items:
        module_name = item.path.name if hasattr(item, "path") and item.path else "<unknown>"
        tier = TIER_BY_MODULE.get(module_name)
        if tier is None:
            unknown.setdefault(module_name, []).append(item.name)
            continue
        item.add_marker(getattr(pytest.mark, tier))
    if unknown:
        listed = "\n".join(f"  {name}: {len(names)} test(s)" for name, names in sorted(unknown.items()))
        raise pytest.UsageError(
            "Unclassified test module(s) in tests/conftest.py TIER_BY_MODULE; "
            "tiers must never fall through silently:\n" + listed
        )


@pytest.fixture(autouse=True)
def _bound_strategy_configs():
    with core_vectors.use(), strategy_config.use():
        yield
