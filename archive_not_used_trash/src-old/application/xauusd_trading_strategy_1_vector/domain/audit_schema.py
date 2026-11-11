"""Strict persisted account, action and feedback event contracts."""

from __future__ import annotations

from typing import Annotated

import pandas as pd
from pandera import Field
from pandera.typing import Series

from .execution_keys import StreamKey


class AccountSnapshots(StreamKey):
    account_balance: Series[float]
    daily_net_realized_pnl: Series[float]
    daily_gross_loss: Series[float] = Field(ge=0)
    open_risk: Series[float] = Field(ge=0)
    pending_risk: Series[float] = Field(ge=0)
    open_count: Series[float] = Field(ge=0)
    free_margin: Series[float]
    risk_used: Series[float] = Field(ge=0)
    risk_budget: Series[float] = Field(ge=0)
    time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    daily_loss_locked: Series[bool]
    operational_locked: Series[bool]
    daily_would_trigger_logged: Series[bool]
    attempted_bar: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]] = Field(nullable=True)

    class Config:
        strict = True
        coerce = True


class ActionEvents(StreamKey):
    action_ordinal: Series[int] = Field(ge=0)
    request_id: Series[str]
    candidate_id: Series[str]
    parent_breakout_id: Series[str]
    bar_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    accepted: Series[bool]
    phase: Series[int] = Field(ge=1, le=9)
    direction: Series[int] = Field(isin=[0, 1])
    order_type: Series[int] = Field(isin=[0, 1])
    entry_price: Series[float] = Field(gt=0)
    stop_loss: Series[float] = Field(gt=0)
    take_profit: Series[float] = Field(gt=0)
    volume: Series[float] = Field(gt=0)

    class Config:
        strict = True
        coerce = True


class FeedbackEvents(StreamKey):
    feedback_ordinal: Series[int] = Field(ge=0)
    zone_id: Series[str]
    direction: Series[int] = Field(isin=[0, 1])
    fill_count: Series[int] = Field(ge=0)
    pending_active: Series[bool]
    filled: Series[bool]

    class Config:
        strict = True
        coerce = True
