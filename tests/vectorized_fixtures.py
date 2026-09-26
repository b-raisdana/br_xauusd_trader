"""Synthetic preloaded candles for vector strategy tests."""


def candles_from_ticks(tick_frame):
    candle_ticks = tick_frame.reset_index(drop="bar_time" in tick_frame)
    if "bar_time" not in candle_ticks:
        candle_ticks["bar_time"] = candle_ticks["precise_time"].dt.floor("15min")
    keys = [key for key in ("broker", "symbol", "bar_time") if key in candle_ticks]
    return (
        candle_ticks.groupby(keys, sort=False)
        .agg(
            open=("bid", "first"),
            high=("bid", "max"),
            low=("bid", "min"),
            close=("bid", "last"),
            volume=("bid", "size"),
        )
        .reset_index()
    )


def prepared_ticks(factory):
    from functools import wraps

    import numpy as np

    from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy

    @wraps(factory)
    def wrapped(*args, **kwargs):
        ticks = factory(*args, **kwargs)
        for name in ("date", "precise_time"):
            ticks.index = ticks.index.set_levels(
                ticks.index.levels[ticks.index.names.index(name)].as_unit("ns"), level=name
            )
        for name in ("broker", "symbol"):
            ticks.index = ticks.index.set_levels(
                ticks.index.levels[ticks.index.names.index(name)].astype("str"), level=name
            )
        ticks["last"] = ticks["bid"]
        ticks["volume"] = np.uint64(0)
        ticks["flags"] = np.uint32(0)
        ticks["volume_real"] = 0.0
        return VectorizedXauUsdStrategy.add_bar_time_n_broker_day(ticks)

    return wrapped
