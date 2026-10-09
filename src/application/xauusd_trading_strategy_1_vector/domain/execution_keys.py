"""Shared primitive identity for persisted execution tables."""

from pandera import Field
from pandera.pandas import DataFrameModel
from pandera.typing import Series


class StreamKey(DataFrameModel):
    stream_id: Series[str]
    stream_tick: Series[int] = Field(ge=0)
