"""Typed schemas for normalized execution entities.

These Pandera schemas define the primitive column structure for
vectorized execution replay. All execution artifacts are stored as
typed DataFrames with UTC nanosecond timestamps and stable identity keys.
"""

from __future__ import annotations

from typing import Annotated

import pandas as pd
from pandera import Field
from pandera.pandas import DataFrameModel
from pandera.typing import Series

from .audit_schema import AccountSnapshots as AccountSnapshots
from .audit_schema import ActionEvents as ActionEvents
from .audit_schema import FeedbackEvents as FeedbackEvents
from .cycle_schema import ModificationEvents as ModificationEvents
from .cycle_schema import PullbackCycleSnapshots as PullbackCycleSnapshots
from .execution_keys import StreamKey as StreamKey


class StreamEvents(DataFrameModel):
    """Tick-level stream input with stable identity.

    Key columns:
    - stream_id: broker/symbol identifier
    - stream_tick: monotonically increasing tick ordinal within stream
    - precise_time: UTC nanosecond timestamp
    - broker_day: trading day partition key
    - bar_time: M15 candle timestamp
    - bar_open: observed M15 open
    - bid, ask: market quotes
    """

    stream_id: Series[str]
    stream_tick: Series[int] = Field(ge=0)
    precise_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    broker_day: Series[str]
    bar_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    bar_open: Series[float] = Field(ge=0)
    bid: Series[float] = Field(ge=0)
    ask: Series[float] = Field(ge=0)

    class Config:
        strict = True
        coerce = True


class ZoneEvents(DataFrameModel):
    """Zone definitions per trading day.

    Key columns:
    - zone_id: stable zone identifier
    - broker_day: trading day partition key
    - high, low: zone boundaries
    - priority: 0=normal, 1=high
    """

    zone_id: Series[str]
    broker_day: Series[str]
    high: Series[float] = Field(ge=0)
    low: Series[float] = Field(ge=0)
    priority: Series[int] = Field(ge=0, le=1)

    class Config:
        strict = True
        coerce = True


class CandidateEvents(DataFrameModel):
    """Signal candidates emitted by strategy.

    Key columns:
    - stream_tick: source tick ordinal within the stream
    - candidate_id: stable candidate identifier
    - parent_breakout_id: for pullbacks, the originating breakout
    - bar_id: M15 candle timestamp as string
    - zone_id: associated zone
    - family: BREAKOUT, REVERSAL, or PULLBACK
    - direction: BUY or SELL
    - order_type: MARKET or PENDING_STOP
    - signal_time: UTC nanosecond timestamp
    - entry_price: requested entry level
    """

    stream_tick: Series[int] = Field(ge=0)
    candidate_id: Series[str]
    parent_breakout_id: Series[str] = Field(default="")
    bar_id: Series[str]
    zone_id: Series[str]
    family: Series[int] = Field(ge=0, le=2)  # XauSignalFamily enum
    direction: Series[int] = Field(ge=0, le=1)  # XauDirection enum
    order_type: Series[int] = Field(ge=0, le=1)  # XauOrderType enum
    signal_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    entry_price: Series[float] = Field(ge=0)

    class Config:
        strict = True
        coerce = True


class OrderEvents(StreamKey):
    """Order lifecycle events.

    Key columns:
    - request_id: stable order identifier
    - order_type: MARKET or PENDING_STOP
    - order_direction: BUY or SELL
    - order_status: SUBMITTED, FILLED, REJECTED, CLOSED, CANCELLED
    - entry_price: actual submitted entry level
    - stop_loss: stop level
    - take_profit: target level
    - order_time: submission timestamp
    - fill_price: fill level (0 if not filled)
    - close_price: close level (0 if not closed)
    - candidate_id: originating candidate
    - parent_breakout_id: for pullbacks
    """

    request_id: Series[str]
    order_type: Series[int] = Field(ge=0, le=1)
    order_direction: Series[int] = Field(ge=0, le=1)
    order_status: Series[int] = Field(ge=0, le=4)
    entry_price: Series[float] = Field(ge=0)
    stop_loss: Series[float] = Field(ge=0)
    take_profit: Series[float] = Field(ge=0)
    order_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    fill_price: Series[float] = Field(default=0.0, ge=0)
    close_price: Series[float] = Field(default=0.0, ge=0)
    candidate_id: Series[str]
    parent_breakout_id: Series[str] = Field(default="")

    class Config:
        strict = True
        coerce = True


class FillEvents(StreamKey):
    """Order fill events.

    Key columns:
    - request_id: order identifier
    - fill_time: UTC nanosecond timestamp
    - fill_price: actual fill level
    - fill_side: bid or ask side used
    - volume: position size
    - cost: commission/fees
    """

    event_ordinal: Series[int] = Field(ge=0)
    position_id: Series[str]
    position_direction: Series[int] = Field(ge=0, le=1)
    request_id: Series[str]
    fill_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    fill_price: Series[float] = Field(ge=0)
    fill_side: Series[str] = Field(isin=["bid", "ask"])
    volume: Series[float] = Field(gt=0)
    vectorbt_size: Series[float] = Field(gt=0)
    cost: Series[float] = Field(ge=0)

    class Config:
        strict = True
        coerce = True


class CloseEvents(StreamKey):
    """Position close events.

    Key columns:
    - request_id: order identifier
    - close_time: UTC nanosecond timestamp
    - close_price: actual close level
    - close_reason: SL, TP, SESSION_OR_RESTART, PORTFOLIO_RISK, etc.
    - realized_pnl: realized profit/loss
    - exit_cost: exit commission/fees
    """

    event_ordinal: Series[int] = Field(ge=0)
    position_id: Series[str]
    position_direction: Series[int] = Field(ge=0, le=1)
    request_id: Series[str]
    close_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    close_price: Series[float] = Field(ge=0)
    close_reason: Series[str]
    realized_pnl: Series[float]
    exit_cost: Series[float] = Field(ge=0)

    class Config:
        strict = True
        coerce = True


class PositionSnapshots(StreamKey):
    """Position state snapshots per tick.

    Key columns:
    - position_id: stable position identifier (derived from request_id)
    - position_direction: BUY or SELL
    - position_size: volume
    - position_entry_price: fill level
    - position_current_price: mark-to-market
    - position_unrealized_pnl: unrealized profit/loss
    - position_realized_pnl: realized profit/loss (0 if open)
    - position_status: FILLED or CLOSED
    - position_time: fill timestamp
    - position_close_time: close timestamp (NaT if open)
    - stop_loss: current stop level
    - take_profit: target level
    """

    position_id: Series[str]
    position_direction: Series[int] = Field(ge=0, le=1)
    position_size: Series[float] = Field(gt=0)
    position_entry_price: Series[float] = Field(ge=0)
    position_current_price: Series[float] = Field(ge=0)
    position_unrealized_pnl: Series[float]
    position_realized_pnl: Series[float]
    position_status: Series[int] = Field(ge=1, le=3)  # FILLED or CLOSED
    position_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    position_close_time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]] = Field(default=pd.NaT, nullable=True)
    stop_loss: Series[float] = Field(ge=0)
    take_profit: Series[float] = Field(ge=0)

    class Config:
        strict = True
        coerce = True


class ExecutionEvents(StreamKey):
    """All execution event timeline.

    Key columns:
    - request_id: order identifier
    - event: SUBMIT, FILL, CLOSE, CANCEL, MODIFY, REJECT, etc.
    - time: UTC nanosecond timestamp
    - reason: additional context for the event
    """

    event_ordinal: Series[int] = Field(ge=0)
    phase: Series[int] = Field(ge=1, le=9)
    request_id: Series[str]
    event: Series[str]
    time: Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    reason: Series[str] = Field(default="")

    class Config:
        strict = True
        coerce = True


class RejectionEvents(DataFrameModel):
    """Entry rejections attributed to their source tick and candidate."""

    stream_id: Series[str]
    stream_tick: Series[int] = Field(ge=0)
    rejection_ordinal: Series[int] = Field(ge=0)
    candidate_id: Series[str]
    rejection_code: Series[int] = Field(ge=1, le=8)

    class Config:
        strict = True
        coerce = True
