"""Causal structural-stop candidates from completed M15 candles."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from br_pre_commit import pandera_validate
from helper.importer import pt

from ..domain.batch_schema import CompletedCandles, StreamTimes


@pandera_validate(allow_pandas_dataframe=True)
def structural_stops(streams: pt.DataFrame[StreamTimes], candles: pd.DataFrame | None) -> NDArray[np.float64]:
    streams = StreamTimes.validate(streams).reset_index(drop=True)
    if candles is None:
        return np.full((len(streams), 2), np.nan)
    candles = CompletedCandles.validate(candles.reset_index()).reset_index(drop=True)
    if candles.empty:
        return np.zeros((len(streams), 2))
    if not np.isfinite(candles[["high", "low"]].to_numpy()).all() or candles.high.lt(candles.low).any():
        raise ValueError("Structural protection requires valid completed candle high/low values")
    close_times = (candles.bar_time + pd.Timedelta(minutes=15)).astype("int64").to_numpy()
    times = streams.precise_time.astype("int64").to_numpy()
    completed = np.searchsorted(close_times, times, side="right")
    values = np.zeros((len(streams), 2))
    for side, column in enumerate(("low", "high")):
        series = candles[column]
        strict = (
            series.lt(series.shift()) & series.lt(series.shift(-1))
            if side == 0
            else series.gt(series.shift()) & series.gt(series.shift(-1))
        )
        centers = np.flatnonzero(strict)
        if len(centers) < 2:
            continue
        mature = close_times[centers + 1]
        at = np.searchsorted(mature, times, side="right") - 1
        valid = at >= 1
        latest = centers[np.maximum(at, 0)]
        prior = centers[np.maximum(at - 1, 0)]
        valid &= prior >= completed - 100
        fresh = series.to_numpy()[latest]
        old = series.to_numpy()[prior]
        valid &= fresh > old if side == 0 else fresh < old
        values[:, side] = np.where(valid, fresh, 0.0)
    return values
