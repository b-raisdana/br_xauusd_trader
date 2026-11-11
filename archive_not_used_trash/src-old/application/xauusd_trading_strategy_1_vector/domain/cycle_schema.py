"""Persisted protection outcomes and pullback lifecycle state."""

from typing import Annotated

import pandas as pd
from pandera import Field
from pandera.pandas import DataFrameModel
from pandera.typing import Series


class ModificationEvents(DataFrameModel):
    """Stop-management requests and outcomes attributed to their source tick."""

    stream_id: Series[str]
    stream_tick: Series[int] = Field(ge=0)
    event_ordinal: Series[int] = Field(ge=0)
    request_id: Series[str]
    event: Series[str] = Field(isin=["MODIFY", "MODIFY_REJECT"])
    time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    accepted: Series[bool]
    previous_stop_loss: Series[float] = Field(ge=0)
    requested_stop_loss: Series[float] = Field(ge=0)
    resulting_stop_loss: Series[float] = Field(ge=0)
    take_profit: Series[float] = Field(ge=0)

    class Config:
        strict = True
        coerce = True


class PullbackCycleSnapshots(DataFrameModel):
    """Active and completed pullback-cycle state attributed to each source tick."""

    reason: Series[str]
    stream_id: Series[str]
    stream_tick: Series[int] = Field(ge=0)
    cycle_ordinal: Series[int] = Field(ge=0)
    cycle_id: Series[str]
    parent_breakout_id: Series[str]
    zone_id: Series[str]
    direction: Series[int] = Field(ge=0, le=1)
    bar_offset: Series[int] = Field(ge=0)
    active: Series[bool]
    penetration_latched: Series[bool]
    pending_active: Series[bool]
    sequence: Series[int] = Field(ge=0)
    breakout_bar_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    broker_day: Series[str]
    order_ticket: Series[str]
    waiting_logged: Series[bool]
    risk_waiting_logged: Series[bool]

    class Config:
        strict = True
        coerce = True
