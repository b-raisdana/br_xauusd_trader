import numpy as np
import pandas as pd
import pandera.pandas as pa
from pandera import typing as pt

from br_pre_commit import pandera_validate
from domain.schemas.common.base_dataframe import Timeseries


class M15TrendCandles(Timeseries):
    high: pt.Series[float]
    low: pt.Series[float]

    class Config:
        coerce = True

    @pa.dataframe_check
    @classmethod
    @pandera_validate(allow_pandas_dataframe=True)
    def has_valid_price_range(cls, frame: pd.DataFrame) -> bool:
        return (
            frame.size > 0
            and frame[["high", "low"]].isin([float("inf"), float("-inf")]).sum().sum() == 0
            and frame["high"].ge(frame["low"]).all()
        )


class M15TrendResult(Timeseries):
    trend: pt.Series[np.int8]
    eligible: pt.Series[bool]


class ZeroLagMacdResult(Timeseries):
    macd: pt.Series[float] = pa.Field(nullable=True)
    signal: pt.Series[float] = pa.Field(nullable=True)
    histogram: pt.Series[float] = pa.Field(nullable=True)
    histogram_previous: pt.Series[float] = pa.Field(nullable=True)
