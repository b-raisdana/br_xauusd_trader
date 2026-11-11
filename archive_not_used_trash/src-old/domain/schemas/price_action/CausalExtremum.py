import pandera.pandas as pa
from pandera import typing as pt

from domain.schemas.common.base_dataframe import Timeseries


class CausalExtremumOHLC(pa.DataFrameModel):
    class Config:
        coerce = True

    high: pt.Series[float]
    low: pt.Series[float]


class CausalExtremumResult(Timeseries):
    true_peak_reach_minutes: pt.Series[float]
    true_valley_reach_minutes: pt.Series[float]
    extremum_sign: pt.Series[int]
    true_extremum_tf_minutes: pt.Series[float]
