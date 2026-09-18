from pandera import typing as pt

from domain.schemas.common.base_dataframe import MultiTimeframe, Timeseries


class OHLC(Timeseries):
    open: pt.Series[float]
    close: pt.Series[float]
    high: pt.Series[float]
    low: pt.Series[float]


class MultiTimeframeOHLC(OHLC, MultiTimeframe):
    pass


class OHLCV(OHLC):
    volume: pt.Series[float]


class MultiTimeframeOHLCV(OHLCV, MultiTimeframe):
    pass
