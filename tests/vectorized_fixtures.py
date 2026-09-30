"""Synthetic preloaded candles for vector strategy tests."""


def candles_from_ticks(tick_frame):
    candle_ticks = tick_frame.reset_index()
    if "bar_time" not in candle_ticks:
        candle_ticks["bar_time"] = candle_ticks["precise_time"].dt.floor("15min")
    keys = [key for key in ("broker", "symbol", "bar_time") if key in candle_ticks]
    df = (
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
    df["date"] = df["bar_time"].dt.normalize()
    df["timeframe"] = "15min"
    df = df.set_index(["date", "timeframe", "broker", "symbol", "bar_time"])
    return df


def with_native_bootstrap(candles):
    import pandas as pd

    parts = [candles]
    for _, stream in candles.groupby(level=["broker", "symbol"], sort=False):
        first = stream.sort_index(level="bar_time").iloc[:1].reset_index()
        price = float(first.open.iloc[0])
        for offset in (3, 2, 1):
            prior = first.copy()
            prior["bar_time"] -= pd.Timedelta(minutes=15 * offset)
            prior["date"] = prior.bar_time.dt.normalize()
            for column in ("open", "high", "low", "close"):
                prior[column] = price
            parts.append(prior.set_index(candles.index.names))
    return pd.concat(parts).sort_index()


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


def calculate_manifest(strategy, ticks, candles):
    from pathlib import Path
    from tempfile import TemporaryDirectory

    import pandas as pd

    from application.xauusd_trading_strategy_1_vector.domain.schema import PerTickState
    from infrastructure.result_processing.io import ResultFilesManifest

    candles = with_native_bootstrap(candles)
    with TemporaryDirectory() as folder:
        manifest = ResultFilesManifest(root=Path(folder))
        try:
            for day, daily in ticks.groupby("broker_day", sort=False):
                manifest.save_daily_ticks(day, daily)
                manifest.save_daily_candles(
                    day, candles.loc[candles.index.get_level_values("bar_time") <= daily.bar_time.max()]
                )
            strategy.process_tick_data(manifest)
            states = [manifest.read_daily_ticks_temp_state(day) for day in manifest.successful_days("per_tick_state")]
            candle_states = [
                manifest.read_daily_candles_temp_state(day) for day in manifest.successful_days("per_candle_states")
            ]
            state = (
                pd.concat(states).sort_index(kind="stable")
                if states
                else strategy._initialize_per_tick_temp_state(ticks)
            )
            candle_state = pd.concat(candle_states) if candle_states else candles.iloc[:0]
            PerTickState.validate(state, lazy=True)
            return state, candle_state
        finally:
            manifest.close()


def complete_tick_state(partial):
    import numpy as np
    import pandas as pd

    from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy

    times = (
        pd.DatetimeIndex(partial.index)
        if isinstance(partial.index, pd.DatetimeIndex)
        else pd.DatetimeIndex(partial.bar_time)
    )
    times = times.as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [
            pd.Index(["test"] * len(times), dtype="str"),
            pd.Index(["XAUUSD"] * len(times), dtype="str"),
            times.normalize(),
            times,
        ],
        names=["broker", "symbol", "date", "precise_time"],
    )
    ticks = pd.DataFrame(
        {
            "bid": partial.bid.to_numpy(dtype=float),
            "ask": partial.bid.to_numpy(dtype=float) + 0.2,
            "last": partial.bid.to_numpy(dtype=float),
            "volume": np.uint64(0),
            "flags": np.uint32(0),
            "volume_real": 0.0,
        },
        index=index,
    )
    # Build valid ticks before injecting invalid values in negative tests.
    ticks = VectorizedXauUsdStrategy.add_bar_time_n_broker_day(ticks)
    state = VectorizedXauUsdStrategy(None)._initialize_per_tick_temp_state(ticks)
    combined = pd.concat([ticks, state], axis=1)
    for column in partial:
        combined[column] = partial[column].array
    return combined
