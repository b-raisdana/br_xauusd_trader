import numba


def test_vectorbt_and_numba_are_active():
    @numba.njit
    def increment(value):
        return value + 1

    assert increment(1) == 2

    import vectorbt as vbt

    assert vbt.__version__
