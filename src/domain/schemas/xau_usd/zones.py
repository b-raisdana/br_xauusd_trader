import pandas as pd
import pandera.pandas as pa
from pandera import typing as pt

from br_pre_commit import pandera_validate


class StrategyZoneRows(pa.DataFrameModel):
    date: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    zone_id: pt.Index[str]
    lower: pt.Series[float]
    upper: pt.Series[float]
    importance_class: pt.Series[str] = pa.Field(isin=["low", "normal", "high"])
    direction: pt.Series[int] = pa.Field(isin=[0])
    note: pt.Series[str] = pa.Field(nullable=True)

    class Config:
        multiindex_ordered = False

    @pa.dataframe_check
    @classmethod
    @pandera_validate(allow_pandas_dataframe=True)
    def has_valid_zone_bounds(cls, frame: pd.DataFrame) -> bool:
        return (
            frame["lower"].gt(0.0).all()
            and frame["lower"].le(frame["upper"]).all()
            and frame["lower"]
            .groupby(level="date", sort=False)
            .apply(
                lambda values: values.is_monotonic_increasing,
            )
            .all()
            and frame[["lower", "upper"]].isin([float("inf"), float("-inf")]).sum().sum() == 0
        )
