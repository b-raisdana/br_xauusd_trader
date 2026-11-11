from pandera import typing as pt

from domain.schemas.common.base_dataframe import MultiTimeframe, Timeseries
from domain.schemas.common.ohlcv import OHLCV
from helper.importer import pa


class ATR(Timeseries):
    atr_255: pt.Series[float] = pa.Field(nullable=True)


class MultiTimeframeATR(ATR, MultiTimeframe):
    pass


class OHLCVA(ATR, OHLCV):
    pass


class MultiTimeframeOHLCVA(OHLCVA, MultiTimeframe):
    pass
