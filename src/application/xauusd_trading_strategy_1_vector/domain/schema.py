"""Pandera schemas for the vectorized XAUUSD trading strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
from pandera import Field
from pandera.pandas import DataFrameModel

from application.xauusd_trading_strategy_1.domain.models import XauPullbackWindowState
from domain.schemas.common.base_dataframe import TickMultiBrokerSymbolTimeseries
from domain.xau_usd.enums import XauDirection, XauExecutionStatus, XauOrderType
from domain.xau_usd.models import XauSignalCandidate
from helper.importer import pa, pt


@dataclass(frozen=True, slots=True)
class PullbackFeedback:
    """Execution snapshot applied before candidate evaluation on its tick."""

    zone_id: str
    direction: XauDirection
    daily_fills: int
    pending_active: bool
    filled: bool = False


# Type aliases for object columns that contain specific data structures
SignalCandidatesTuple = tuple[XauSignalCandidate, ...]
PullbackWindowsTuple = tuple[XauPullbackWindowState, ...]
TradingAction = dict[str, object]  # Action dict with trading details
OrderId = str  # | int
PositionId = str  # | int


class VectorizedTickInput(TickMultiBrokerSymbolTimeseries):
    """Input tick data for vectorized strategy.

    MultiIndex: (broker, symbol, date, datetime)
    Columns: bid, ask
    """

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


class PerTickBaseState(TickMultiBrokerSymbolTimeseries):
    """Base columns of per-tick intermediate state (fixed columns).

    MultiIndex: (broker, symbol, date, datetime)
    """

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

    action: pt.Series[TradingAction] = Field(nullable=True)
    breakout_signals: pt.Series[SignalCandidatesTuple]
    pullback_windows_opened: pt.Series[PullbackWindowsTuple]
    pullback_feedback: Optional[pt.Series[tuple[PullbackFeedback, ...]]]

    class Config:
        coerce = False
        strict = False
        multiindex_ordered = False


class PullbackResult(PerTickBaseState):
    pullback_signals: pt.Series[SignalCandidatesTuple]


class StrategyResult(TickMultiBrokerSymbolTimeseries):
    action: pt.Series[TradingAction] = Field(nullable=True)
    breakout_signals: pt.Series[SignalCandidatesTuple]
    pullback_windows_opened: pt.Series[PullbackWindowsTuple]
    reversal_signals: pt.Series[SignalCandidatesTuple]
    pullback_signals: pt.Series[SignalCandidatesTuple]
    actions: pt.Series[tuple[dict, ...]]
    execution_events: pt.Series[tuple[dict, ...]]
    orders: pt.Series[tuple[dict, ...]]
    positions: pt.Series[tuple[dict, ...]]
    execution_mode: pt.Series[str] = Field(isin=["replay", "signals_only"])

    class Config:
        multiindex_ordered = False


class OrderInput(TickMultiBrokerSymbolTimeseries):
    action: pt.Series[object] = Field(nullable=True)
    orders: pt.Series[tuple[dict, ...]] = Field(nullable=True, default=None)
    positions: pt.Series[tuple[dict, ...]] = Field(nullable=True, default=None)

    class Config:
        multiindex_ordered = False
        coerce = True
        add_missing_columns = True


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

    # order_id: pt.Series[OrderId] = Field(nullable=True)
    order_id: pt.Series[str] = Field(nullable=True)
    # order_type: pt.Series[XauOrderType] = Field(nullable=True)
    # order_direction: pt.Series[XauDirection] = Field(nullable=True)
    # order_status: pt.Series[XauExecutionStatus] = Field(nullable=True)
    order_type: pt.Series[pd.Int64Dtype] = pa.Field(
        nullable=True,
        isin=[member.value for member in XauOrderType],
    )
    order_direction: pt.Series[pd.Int64Dtype] = pa.Field(
        nullable=True,
        isin=[member.value for member in XauDirection],
    )
    order_status: pt.Series[pd.Int64Dtype] = pa.Field(
        nullable=True,
        isin=[member.value for member in XauExecutionStatus],
    )

    entry_price: pt.Series[float] = Field(nullable=True)
    stop_loss: pt.Series[float] = Field(nullable=True)
    take_profit: pt.Series[float] = Field(nullable=True)
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

    # position_id: pt.Series[PositionId] = Field(nullable=True)
    position_id: pt.Series[str] = Field(nullable=True)
    # position_direction: pt.Series[XauDirection] = Field(nullable=True)
    position_direction: pt.Series[pd.Int64Dtype] = pa.Field(
        nullable=True,
        isin=[member.value for member in XauDirection],
    )

    position_size: pt.Series[float] = Field(nullable=True)
    position_entry_price: pt.Series[float] = Field(nullable=True)
    position_current_price: pt.Series[float] = Field(nullable=True)
    position_unrealized_pnl: pt.Series[float] = Field(nullable=True)
    position_realized_pnl: pt.Series[float] = Field(nullable=True)
    # position_status: pt.Series[XauExecutionStatus] = Field(nullable=True)
    position_status: pt.Series[pd.Int64Dtype] = Field(
        nullable=True,
        isin=[member.value for member in XauExecutionStatus],
    )
    position_time: pt.Series[pd.DatetimeTZDtype(tz="UTC", unit="ns")] = Field(nullable=True)
    position_close_time: pt.Series[pd.DatetimeTZDtype(tz="UTC", unit="ns")] = Field(nullable=True)

    # class Config:
    #     coerce = False
    #     strict = False
    #     multiindex_ordered = False


class VectorbtBacktestInput(TickMultiBrokerSymbolTimeseries):
    """Schema for vectorbt backtest input.

    Only includes columns used by _extract_signals:
    - bid: close price for backtest
    - position_id: to detect new position openings
    - position_status: to check FILLED/CLOSED status
    """

    bid: pt.Series[float]
    position_id: pt.Series[str] = Field(nullable=True)
    position_status: pt.Series[pd.Int64Dtype] = pa.Field(
        nullable=True,
        isin=[member.value for member in XauExecutionStatus],
    )

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

    class Config:
        coerce = False


class ReversalInput(EngagementInput):
    trend: pt.Series[int]
    multi_zone_tick_gap: pt.Series[bool]


class ReversalResult(ReversalInput):
    reversal_signals: pt.Series[SignalCandidatesTuple] = Field(nullable=True)

    class Config:
        coerce = False


class ZoneDayInput(DataFrameModel):
    broker_day: pt.Series[str]
