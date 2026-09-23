import numpy as np
from pandera import typing as pt

from domain.schemas.common.base_dataframe import MultiTimeframe, Timeseries


class OHLC(Timeseries):
    open: pt.Series[float]
    close: pt.Series[float]
    high: pt.Series[float]
    low: pt.Series[float]


class TicksSpreadOHLC(OHLC):
    tick_volume: pt.Series[np.uint64]
    spread: pt.Series[np.int32]


class MultiTimeframeOHLC(OHLC, MultiTimeframe):
    pass


class MultiTimeframeTicksSpreadOHLC(TicksSpreadOHLC, MultiTimeframe):
    pass


class OHLCV(OHLC):
    volume: pt.Series[float]


class MultiTimeframeOHLCV(OHLCV, MultiTimeframe):
    pass
