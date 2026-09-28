"""Column contracts shared by calculation stages and persisted result artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, TypedDict

import pandas as pd
from pandera import Field
from pandera.pandas import DataFrameModel

from domain.schemas.common.base_dataframe import MultiBrokerSymbol, MultiTimeframe, TickMultiBrokerSymbolTimeseries
from domain.schemas.common.ohlcv import MultiTimeframeOHLC
from domain.schemas.tick import Tick
from domain.xau_usd.enums import XauDirection, XauExecutionStatus, XauOrderType, XauSignalFamily
from domain.xau_usd.models import XauPullbackWindowState, XauSignalCandidate
from helper.importer import pt


@dataclass(frozen=True, slots=True)
class PullbackFeedback:
    zone_id: str
    direction: XauDirection
    daily_fills: int
    pending_active: bool
    filled: bool = False


type ReplayEventKind = Literal[
    "SUBMIT", "REJECT", "FILL", "CLOSE", "CLOSE_REJECT", "CANCEL", "CANCEL_REJECT", "MODIFY", "MODIFY_REJECT"
]
type ReplayReason = Literal[
    "",
    "DAY_ROLLOVER",
    "WINDOW_EXPIRED",
    "SL",
    "TP",
    "STRICT_TREND_FAILED",
    "OPPOSITE_BREAKOUT",
    "SESSION_OR_RESTART",
    "DAILY_LOSS",
]


class CandidateSnapshot(TypedDict):
    candidate_id: str
    parent_breakout_id: str
    bar_id: str
    zone_id: str
    family: XauSignalFamily
    direction: XauDirection
    order_type: int
    signal_time: datetime | None
    entry_price: float


class OrderSnapshot(TypedDict):
    order_id: str
    order_type: int
    order_direction: int
    order_status: int
    entry_price: float
    stop_loss: float
    take_profit: float
    order_time: datetime
    fill_price: float
    close_price: float
    candidate_id: str
    parent_breakout_id: str


class PositionSnapshot(TypedDict):
    position_id: str | None
    position_direction: int
    position_size: float
    position_entry_price: float
    position_current_price: float
    position_unrealized_pnl: float
    position_realized_pnl: float
    position_status: int
    position_time: datetime | None
    position_close_time: datetime | None
    stop_loss: float
    take_profit: float


class ReplayEvent(OrderSnapshot):
    request_id: str
    event: ReplayEventKind
    time: datetime
    reason: ReplayReason


class ReplayAction(TypedDict):
    request_id: str
    candidate: CandidateSnapshot
    direction: int
    order_type: int
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    accepted: bool


class ReplaySnapshot(TypedDict):
    action: ReplayAction | None
    actions: tuple[ReplayAction, ...]
    execution_events: tuple[ReplayEvent, ...]
    orders: tuple[OrderSnapshot, ...]
    positions: tuple[PositionSnapshot, ...]
    pullback_signals: tuple[XauSignalCandidate, ...]
    pullback_feedback: tuple[PullbackFeedback, ...]
    attempted_bars: str
    entry_rejections: tuple[tuple[str, int], ...]
    daily_net_realized_pnl: float
    daily_gross_loss: float
    account_balance: float
    daily_loss_locked: bool
    operational_locked: bool


SignalCandidatesTuple = tuple[XauSignalCandidate, ...]
PullbackWindowsTuple = tuple[XauPullbackWindowState, ...]
TradingAction = ReplayAction
OrderId = str
PositionId = str


class FrameContract(DataFrameModel):
    class Config:
        coerce = False
        strict = False
        multiindex_ordered = False


class HasDay(FrameContract):
    broker_day: pt.Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]


class BarTime(FrameContract):
    bar_time: pt.Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]


class VectorizedTick(Tick, HasDay, BarTime):
    class Config(Tick.Config, FrameContract.Config):
        coerce = False


class StrategyCandles(MultiTimeframeOHLC, MultiBrokerSymbol, FrameContract):
    class Config(MultiTimeframeOHLC.Config, MultiTimeframe.Config, MultiBrokerSymbol.Config, FrameContract.Config):
        coerce = False

    bar_time: pt.Index[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]


class TrendInfo(FrameContract):
    class Config(FrameContract.Config):
        coerce = True

    trend_count: pt.Series[int] = Field(ge=0)
    trend_high_0: pt.Series[float] = Field(nullable=True)
    trend_high_1: pt.Series[float] = Field(nullable=True)
    trend_high_2: pt.Series[float] = Field(nullable=True)
    trend_low_0: pt.Series[float] = Field(nullable=True)
    trend_low_1: pt.Series[float] = Field(nullable=True)
    trend_low_2: pt.Series[float] = Field(nullable=True)


class ReferenceTrendInfo(TrendInfo):
    class Config(TrendInfo.Config):
        coerce = False

    reference_high: pt.Series[float] = Field(nullable=True)
    reference_low: pt.Series[float] = Field(nullable=True)


class ProcessBarBoundariesInPerTickState(FrameContract):
    day_active: pt.Series[bool]


class ProcessedBarsTicks(ProcessBarBoundariesInPerTickState, TrendInfo):
    class Config(TrendInfo.Config):
        coerce = False

    bar_open: pt.Series[float]
    bar_active: pt.Series[bool]


class ProcessBarBoundariesOutPerTickState(ProcessedBarsTicks):
    pass


class EngagementResult(FrameContract):
    buy_engaged: pt.Series[bool]
    sell_engaged: pt.Series[bool]
    multi_zone_tick_gap: pt.Series[bool]


class ReversalInfo(EngagementResult):
    trend: pt.Series[int] = Field(isin=[0, 1, 2])


class ReversalResult(ReversalInfo):
    reversal_signals: pt.Series[SignalCandidatesTuple]


class BreakoutSequence(FrameContract):
    breakout_sequence: pt.Series[int] = Field(ge=0)
    breakout_signals: pt.Series[SignalCandidatesTuple]
    pullback_windows_opened: pt.Series[PullbackWindowsTuple]


class PullbackGenerated(FrameContract):
    pullback_signals: pt.Series[SignalCandidatesTuple]
    pullback_penetration_latched: pt.Series[bool]
    pullback_sequence: pt.Series[int] = Field(ge=0)


class PullbackUpdated(FrameContract):
    pullback_active: pt.Series[bool]
    pullback_bar_offset: pt.Series[int] = Field(ge=0, le=5)


class OrderInfo(FrameContract):
    action: pt.Series[ReplayAction] = Field(nullable=True)
    orders: pt.Series[tuple[OrderSnapshot, ...]]
    positions: pt.Series[tuple[PositionSnapshot, ...]]


class Step(FrameContract):
    actions: pt.Series[tuple[ReplayAction, ...]]
    execution_events: pt.Series[tuple[ReplayEvent, ...]]
    execution_mode: pt.Series[str] = Field(isin=["replay", "signals_only"])
    pullback_feedback: pt.Series[tuple[PullbackFeedback, ...]]
    attempted_bars: pt.Series[str]
    entry_rejections: pt.Series[tuple[tuple[str, int], ...]]
    daily_net_realized_pnl: pt.Series[float] = Field(nullable=True)
    daily_gross_loss: pt.Series[float] = Field(nullable=True)
    account_balance: pt.Series[float] = Field(nullable=True)
    daily_loss_locked: pt.Series[bool]
    operational_locked: pt.Series[bool]


class PerTickState(
    TickMultiBrokerSymbolTimeseries,
    ReferenceTrendInfo,
    ProcessedBarsTicks,
    ReversalResult,
    BreakoutSequence,
    PullbackGenerated,
    PullbackUpdated,
    OrderInfo,
    Step,
):
    """Complete calculation state, excluding the separately stored market ticks."""

    class Config(
        TickMultiBrokerSymbolTimeseries.Config,
        MultiBrokerSymbol.Config,
        ReferenceTrendInfo.Config,
        ProcessedBarsTicks.Config,
    ):
        coerce = False


class PerCandleState(StrategyCandles, TrendInfo):
    class Config(StrategyCandles.Config, TrendInfo.Config):
        coerce = False


class StrategyResult(PerTickState, VectorizedTick):
    """Calculation state joined to its original market ticks."""

    class Config(PerTickState.Config, VectorizedTick.Config):
        coerce = False


class StrategyResultWithCandles(StrategyResult):
    candle_close: pt.Series[float] = Field(nullable=True)
    candle_high: pt.Series[float] = Field(nullable=True)
    candle_low: pt.Series[float] = Field(nullable=True)
    candle_open: pt.Series[float] = Field(nullable=True)
    candle_volume: pt.Series[float] = Field(nullable=True)


class OrderInput(StrategyResultWithCandles):
    pass


class OrderManagementResult(OrderInput):
    order_id: pt.Series[str] = Field(nullable=True)
    order_type: pt.Series[pd.Int64Dtype] = Field(nullable=True, isin=[m.value for m in XauOrderType])
    order_direction: pt.Series[pd.Int64Dtype] = Field(nullable=True, isin=[m.value for m in XauDirection])
    order_status: pt.Series[pd.Int64Dtype] = Field(nullable=True, isin=[m.value for m in XauExecutionStatus])
    entry_price: pt.Series[float] = Field(nullable=True)
    stop_loss: pt.Series[float] = Field(nullable=True)
    take_profit: pt.Series[float] = Field(nullable=True)
    order_time: pt.Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]] = Field(nullable=True)


# class PositionInput(OrderManagementResult):
#     pass


class VectorbtBacktestInput(Tick, FrameContract):
    class Config(Tick.Config, FrameContract.Config):
        coerce = False

    position_id: pt.Series[str] = Field(nullable=True)
    position_status: pt.Series[pd.Int64Dtype] = Field(nullable=True, isin=[m.value for m in XauExecutionStatus])


class PositionTrackingResult(OrderManagementResult, VectorbtBacktestInput):
    class Config(OrderManagementResult.Config, VectorbtBacktestInput.Config):
        coerce = False

    position_direction: pt.Series[pd.Int64Dtype] = Field(nullable=True, isin=[m.value for m in XauDirection])
    position_size: pt.Series[float] = Field(nullable=True)
    position_entry_price: pt.Series[float] = Field(nullable=True)
    position_current_price: pt.Series[float] = Field(nullable=True)
    position_unrealized_pnl: pt.Series[float] = Field(nullable=True)
    position_realized_pnl: pt.Series[float] = Field(nullable=True)
    position_time: pt.Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]] = Field(nullable=True)
    position_close_time: pt.Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]] = Field(nullable=True)


# Never Used!
# reversal_keys: obsolete; reversal deduplication uses the local seen_keys set.
