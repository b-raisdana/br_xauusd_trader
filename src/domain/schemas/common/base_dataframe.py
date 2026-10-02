from typing import TypeVar

import pandas as pd

from br_pre_commit import pandera_validate
from helper.importer import pa, pt


class Timeseries(pa.DataFrameModel):
    date: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]

    class Config:
        multiindex_ordered = False


class MultiBrokerSymbol(pa.DataFrameModel):
    symbol: pt.Index[str]
    broker: pt.Index[str]

    class Config:
        multiindex_ordered = False


class MultiBrokerSymbolTimeseries(Timeseries, MultiBrokerSymbol):
    pass


class PreciseTimeSeries(pa.DataFrameModel):
    precise_time: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]


class TickMultiBrokerSymbolTimeseries(PreciseTimeSeries, MultiBrokerSymbolTimeseries):
    pass


class MultiTimeframe(pa.DataFrameModel):
    timeframe: pt.Index[str]

    class Config:
        multiindex_ordered = False


class MultiTimeframeTimeseries(Timeseries, MultiTimeframe):
    pass


@pandera_validate(allow_pandas_dataframe=True)
def has_single_timeframe(data: pd.DataFrame) -> bool:
    return len(data.index.get_level_values("timeframe").unique()) == 1


class SingleTimeframeTimeseries(Timeseries, MultiTimeframe):
    @pa.dataframe_check
    def validates_single_timeframe(cls, data) -> bool:  # type: ignore[misc, no-untyped-def]
        return has_single_timeframe(data)


MultiTimeframe_Type = TypeVar("MultiTimeframe_Type", bound=MultiTimeframe)
Timeseries_Type = TypeVar("Timeseries_Type", bound=Timeseries)
MultiTimeframeTimeseries_Type = TypeVar("MultiTimeframeTimeseries_Type", bound=MultiTimeframeTimeseries)
