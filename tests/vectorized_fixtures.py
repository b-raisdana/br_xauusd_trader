"""Synthetic preloaded candles for vector strategy tests."""


def candles_from_ticks(tick_frame):
    candle_ticks = tick_frame.reset_index(drop="bar_time" in tick_frame)
    if "bar_time" not in candle_ticks:
        candle_ticks["bar_time"] = candle_ticks["datetime"].dt.floor("15min")
    keys = [key for key in ("broker", "symbol", "bar_time") if key in candle_ticks]
    return (
        candle_ticks.groupby(keys, sort=False)
        .agg(open=("bid", "first"), high=("bid", "max"), low=("bid", "min"), close=("bid", "last"))
        .reset_index()
    )
