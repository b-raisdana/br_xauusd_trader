"""Input and output contracts for the compiled replay boundary."""

from typing import Annotated

import pandas as pd
import pandera.pandas as pa
from pandera.typing import DataFrame, Series

from .execution_schema import (
    CloseEvents,
    ExecutionEvents,
    FillEvents,
    OrderEvents,
    PositionSnapshots,
    RejectionEvents,
)


class StreamTimes(pa.DataFrameModel):
    """UTC timestamps used by economics and structural protection."""

    precise_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]


class CompletedCandles(pa.DataFrameModel):
    """Completed M15 prices, with bar_time in a column or named index level."""

    bar_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]] = pa.Field(nullable=True)
    high: Series[float]
    low: Series[float]

    @pa.dataframe_check
    def valid_bar_times(cls, frame) -> bool:
        if "bar_time" in frame.columns:
            return True
        if "bar_time" not in frame.index.names:
            return False
        times = frame.index.get_level_values("bar_time")
        return times.dtype == pd.DatetimeTZDtype("ns", "UTC") and not times.isna().any()


class ReplayWindows(pa.DataFrameModel):
    """Window openings; a columnless empty frame denotes no openings."""

    stream_tick: Series[int] = pa.Field(ge=0, nullable=True)
    parent_breakout_id: Series[str] = pa.Field(nullable=True)
    zone_id: Series[str] = pa.Field(nullable=True)
    direction: Series[int] = pa.Field(isin=[0, 1], nullable=True)
    breakout_bar_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]] = pa.Field(nullable=True)
    broker_day: Series[str] = pa.Field(nullable=True)

    @pa.dataframe_check
    def complete_nonempty_windows(cls, frame) -> bool:
        return frame.empty or set(cls.to_schema().columns).issubset(frame.columns)


type ReplayTables = tuple[
    DataFrame[OrderEvents],
    DataFrame[FillEvents],
    DataFrame[CloseEvents],
    DataFrame[PositionSnapshots],
    DataFrame[ExecutionEvents],
    DataFrame[RejectionEvents],
]
