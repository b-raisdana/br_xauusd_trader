"""Pandera schemas for the vectorized XAUUSD trading strategy."""

from __future__ import annotations

import pandas as pd
from pandera import Field
from pandera.pandas import DataFrameModel

from helper.importer import pt


class VectorizedTickInput(DataFrameModel):
    """Input tick data for vectorized strategy.

    MultiIndex: (broker, symbol, date, datetime)
    Columns: bid, ask
    """

    symbol: pt.Index[str]
    broker: pt.Index[str]
    date: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    datetime: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    bid: pt.Series[float]
    ask: pt.Series[float]

    class Config:
        coerce = True
        strict = False
        multiindex_ordered = False


class VectorizedCandleInput(DataFrameModel):
    bar_time: pt.Series[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    open: pt.Series[float]
    high: pt.Series[float]
    low: pt.Series[float]

    class Config:
        coerce = True


class PerCandleState(DataFrameModel):
    broker: pt.Index[str]
    symbol: pt.Index[str]
    bar_time: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    open: pt.Series[float]
    high: pt.Series[float]
    low: pt.Series[float]
    trend_count: pt.Series[int] = Field(ge=0, le=3)
    trend_high_0: pt.Series[float]
    trend_high_1: pt.Series[float]
    trend_high_2: pt.Series[float]
    trend_low_0: pt.Series[float]
    trend_low_1: pt.Series[float]
    trend_low_2: pt.Series[float]


class PerTickBaseState(DataFrameModel):
    """Base columns of per-tick intermediate state (fixed columns).

    MultiIndex: (broker, symbol, date, datetime)
    """

    symbol: pt.Index[str]
    broker: pt.Index[str]
    date: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    datetime: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    bid: pt.Series[float]
    ask: pt.Series[float]
    bar_time: pt.Series[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    broker_day: pt.Series[str]

    trend: pt.Series[int] = Field(isin=[0, 1, 2])
    trend_count: pt.Series[int] = Field(ge=0, le=3)
    trend_high_0: pt.Series[float] = Field(ge=0.0)
    trend_high_1: pt.Series[float] = Field(ge=0.0)
    trend_high_2: pt.Series[float] = Field(ge=0.0)
    trend_low_0: pt.Series[float] = Field(ge=0.0)
    trend_low_1: pt.Series[float] = Field(ge=0.0)
    trend_low_2: pt.Series[float] = Field(ge=0.0)

    bar_open: pt.Series[float] = Field(ge=0.0)
    last_bid: pt.Series[float] = Field(ge=0.0)
    last_ask: pt.Series[float] = Field(ge=0.0)
    bar_active: pt.Series[bool]
    day_active: pt.Series[bool]

    buy_engaged: pt.Series[bool]
    sell_engaged: pt.Series[bool]

    breakout_sequence: pt.Series[int] = Field(ge=0)
    reversal_keys: pt.Series[str]
    attempted_bars: pt.Series[str]

    pullback_active: pt.Series[bool]
    pullback_bar_offset: pt.Series[int] = Field(ge=0, le=5)
    pullback_penetration_latched: pt.Series[bool]
    pullback_sequence: pt.Series[int] = Field(ge=0)

    reference_high: pt.Series[float] = Field(ge=0.0)
    reference_low: pt.Series[float] = Field(ge=0.0)
    multi_zone_tick_gap: pt.Series[bool]

    action: pt.Series[object] = Field(nullable=True)
    breakout_signals: pt.Series[object]
    pullback_windows_opened: pt.Series[object]

    class Config:
        coerce = False
        strict = False
        multiindex_ordered = False


class StrategyResult(DataFrameModel):
    broker: pt.Index[str]
    symbol: pt.Index[str]
    date: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    datetime: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    action: pt.Series[object] = Field(nullable=True)
    breakout_signals: pt.Series[object]
    pullback_windows_opened: pt.Series[object]

    class Config:
        multiindex_ordered = False


class OrderInput(DataFrameModel):
    broker: pt.Index[str]
    symbol: pt.Index[str]
    date: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    datetime: pt.Index[pd.DatetimeTZDtype(tz="UTC", unit="ns")]
    action: pt.Series[object] = Field(nullable=True)

    class Config:
        multiindex_ordered = False
        coerce = True


class StrategyResultWithCandles(StrategyResult):
    """Strategy result merged with candle context."""

    candle_open: pt.Series[float] = Field(nullable=True)
    candle_high: pt.Series[float] = Field(nullable=True)
    candle_low: pt.Series[float] = Field(nullable=True)
    candle_close: pt.Series[float] = Field(nullable=True)
    candle_volume: pt.Series[float] = Field(nullable=True)

    class Config:
        coerce = False
        strict = False
        multiindex_ordered = False


class OrderManagementResult(OrderInput):
    """Strategy result with order management columns."""

    order_id: pt.Series[object] = Field(nullable=True)
    order_type: pt.Series[object] = Field(nullable=True)
    order_direction: pt.Series[object] = Field(nullable=True)
    order_status: pt.Series[object] = Field(nullable=True)
    entry_price: pt.Series[object] = Field(nullable=True)
    stop_loss: pt.Series[object] = Field(nullable=True)
    take_profit: pt.Series[object] = Field(nullable=True)
    order_time: pt.Series[pd.DatetimeTZDtype(tz="UTC", unit="ns")] = Field(nullable=True)

    class Config:
        coerce = False
        strict = False
        multiindex_ordered = False


class PositionInput(OrderManagementResult):
    bid: pt.Series[float]

    class Config:
        coerce = True
        multiindex_ordered = False


class PositionTrackingResult(OrderManagementResult):
    """Strategy result with position tracking columns."""

    position_id: pt.Series[object] = Field(nullable=True)
    position_direction: pt.Series[object] = Field(nullable=True)
    position_size: pt.Series[object] = Field(nullable=True)
    position_entry_price: pt.Series[object] = Field(nullable=True)
    position_current_price: pt.Series[object] = Field(nullable=True)
    position_unrealized_pnl: pt.Series[object] = Field(nullable=True)
    position_status: pt.Series[object] = Field(nullable=True)
    position_time: pt.Series[pd.DatetimeTZDtype(tz="UTC", unit="ns")] = Field(nullable=True)

    class Config:
        coerce = False
        strict = False
        multiindex_ordered = False


class ReferenceInput(DataFrameModel):
    trend_count: pt.Series[int] = Field(ge=0)
    trend_high_0: pt.Series[float] = Field(nullable=True)
    trend_high_1: pt.Series[float] = Field(nullable=True)
    trend_high_2: pt.Series[float] = Field(nullable=True)
    trend_low_0: pt.Series[float] = Field(nullable=True)
    trend_low_1: pt.Series[float] = Field(nullable=True)
    trend_low_2: pt.Series[float] = Field(nullable=True)

    class Config:
        coerce = True


class ReferenceResult(ReferenceInput):
    reference_high: pt.Series[float] = Field(nullable=True)
    reference_low: pt.Series[float] = Field(nullable=True)

    class Config:
        coerce = False


class EngagementInput(DataFrameModel):
    bid: pt.Series[float] = Field(nullable=True)
    bar_time: pt.Series[pd.DatetimeTZDtype(tz="UTC", unit="ns")]

    class Config:
        coerce = True


class EngagementResult(EngagementInput):
    buy_engaged: pt.Series[bool]
    sell_engaged: pt.Series[bool]
    multi_zone_tick_gap: pt.Series[bool]

    class Config:
        coerce = False


class BarInput(EngagementInput):
    ask: pt.Series[float] = Field(nullable=True)
    broker_day: pt.Series[str]
    day_active: pt.Series[bool]


class BarResult(BarInput, ReferenceInput):
    bar_open: pt.Series[float]
    bar_active: pt.Series[bool]
    last_bid: pt.Series[float] = Field(nullable=True)
    last_ask: pt.Series[float] = Field(nullable=True)

    class Config:
        coerce = False


class ReversalInput(EngagementInput):
    trend: pt.Series[int]
    multi_zone_tick_gap: pt.Series[bool]


class ReversalResult(ReversalInput):
    class Config:
        coerce = False


class ZoneDayInput(DataFrameModel):
    broker_day: pt.Series[str]
