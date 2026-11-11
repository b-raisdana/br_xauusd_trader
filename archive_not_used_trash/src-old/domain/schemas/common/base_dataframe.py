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


class StreamId(pa.DataFrameModel):
    stream_id: pt.Index[str]

    class Config:
        multiindex_ordered = False


class EquityTimeseries(Timeseries, StreamId):
    """Equity curve with UTC nanosecond index and stream_id columns."""

    pass


class StatsDataFrame(pa.DataFrameModel):
    """Portfolio statistics per stream."""

    Start: pt.Series[pd.Timestamp]
    End: pt.Series[pd.Timestamp]
    Initial_cash: pt.Series[float]
    Final_value: pt.Series[float]
    Total_return_pct: pt.Series[float]
    Max_drawdown_pct: pt.Series[float]
    Annualized_return_pct: pt.Series[float]
    Sharpe_ratio: pt.Series[float] = pa.Field(nullable=True)
    Trades: pt.Series[int]
    Recorded_trade_PnL: pt.Series[float]

    class Config:
        coerce = True


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
EquityTimeseries_Type = TypeVar("EquityTimeseries_Type", bound=EquityTimeseries)
StatsDataFrame_Type = TypeVar("StatsDataFrame_Type", bound=StatsDataFrame)
