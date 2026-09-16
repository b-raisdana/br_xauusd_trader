import numba
import vectorbt as vbt


def test_vectorbt_and_numba_are_active():
    @numba.njit
    def increment(value):
        return value + 1

    assert increment(1) == 2
    assert vbt.__version__
