import numpy as np

from domain.schemas.tick import Tick


def test_from_ndarray_returns_validated_tick_frame() -> None:
    data = np.array(
        [(1_758_153_600_000, 2000.0, 2000.2, 2000.1, 1, 3, 1.0)],
        dtype=[
            ("time_msc", np.int64),
            ("bid", np.float64),
            ("ask", np.float64),
            ("last", np.float64),
            ("volume", np.uint64),
            ("flags", np.uint32),
            ("volume_real", np.float64),
        ],
    )

    ticks = Tick.from_ndarray(data, symbol="XAUUSD", broker="test")

    assert ticks.index.names == ["symbol", "broker", "date", "precise_time"]
    assert ticks.index.get_level_values("symbol").tolist() == ["XAUUSD"]
    assert ticks["bid"].tolist() == [2000.0]
    Tick.validate(ticks)
