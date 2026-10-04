"""Optional analysis tooling must be importable and functional.

These libraries are lazily imported by the strategy, so a broken install would
only surface when a report is requested. This module makes the failure explicit
at the integration boundary instead.

Part of the `integration` tier: it validates installed environment state, not
repository behavior.
"""

import numba
import vectorbt as vbt


def test_numba_jit_executes():
    @numba.njit
    def increment(value: int) -> int:
        return value + 1

    assert increment(1) == 2


def test_vectorbt_exposes_a_version():
    assert vbt.__version__
