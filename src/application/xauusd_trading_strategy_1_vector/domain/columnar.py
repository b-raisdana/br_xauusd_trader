"""Primitive signals-only output contracts."""

from dataclasses import dataclass, field
from typing import Annotated

import pandas as pd
from pandera import Field

from domain.schemas.common.base_dataframe import TickMultiBrokerSymbolTimeseries
from domain.xau_usd.models import XauDailyZoneSignalState
from helper.importer import pt

from .robust import RobustInputs
from .schema import FrameContract, PerCandleState, ProcessedBarsTicks, ReferenceTrendInfo


class SignalTickState(TickMultiBrokerSymbolTimeseries, ReferenceTrendInfo, ProcessedBarsTicks):
    class Config(ReferenceTrendInfo.Config, ProcessedBarsTicks.Config):
        coerce = False

    stream_tick: pt.Series[int] = Field(ge=0)
    trend: pt.Series[int] = Field(isin=[-1, 0, 1])
    buy_engaged: pt.Series[bool]
    sell_engaged: pt.Series[bool]
    multi_zone_tick_gap: pt.Series[bool]
    breakout_sequence: pt.Series[int] = Field(ge=0)
    pullback_active: pt.Series[bool]
    pullback_bar_offset: pt.Series[int] = Field(ge=0, le=10)
    pullback_penetration_latched: pt.Series[bool]


class SignalTable(TickMultiBrokerSymbolTimeseries, FrameContract):
    class Config(TickMultiBrokerSymbolTimeseries.Config, FrameContract.Config):
        coerce = False

    stream_tick: pt.Series[int] = Field(ge=0)
    candidate_id: pt.Series[str]
    parent_breakout_id: pt.Series[str]
    bar_id: pt.Series[str]
    zone_id: pt.Series[str]
    family: pt.Series[int] = Field(isin=[0, 1, 2])
    direction: pt.Series[int] = Field(isin=[0, 1])
    order_type: pt.Series[int] = Field(isin=[0, 1])
    signal_time: pt.Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    entry_price: pt.Series[float]


class WindowColumns(FrameContract):
    stream_tick: pt.Series[int] = Field(ge=0)
    parent_breakout_id: pt.Series[str]
    zone_id: pt.Series[str]
    zone_low: pt.Series[float]
    zone_high: pt.Series[float]
    priority: pt.Series[int]
    direction: pt.Series[int] = Field(isin=[0, 1])
    bar_offset: pt.Series[int] = Field(ge=0, le=10)
    active: pt.Series[bool]
    penetration_latched: pt.Series[bool]
    breakout_bar_time: pt.Series[Annotated[pd.DatetimeTZDtype, "ns", "UTC"]]
    broker_day: pt.Series[str]


class WindowTable(TickMultiBrokerSymbolTimeseries, WindowColumns):
    class Config(TickMultiBrokerSymbolTimeseries.Config, WindowColumns.Config):
        coerce = False


class ActiveWindows(WindowColumns):
    window_id: pt.Series[int]
    born_bar: pt.Series[int]
    expiry_bar: pt.Series[int]
    event_day: pt.Series[str]


@dataclass(frozen=True)
class ColumnarResult:
    ticks: pt.DataFrame[SignalTickState]
    candles: pt.DataFrame[PerCandleState]
    signals: pt.DataFrame[SignalTable]
    windows: pt.DataFrame[WindowTable]


@dataclass
class ColumnarMarket:
    inputs: RobustInputs = field(default_factory=RobustInputs)
    bar: pd.Timestamp | None = None
    broker_day: str = ""
    bar_number: int = -1
    bar_open: float = 0.0
    previous_bid: float = 0.0
    trend: int = 0
    breakout_sequence: int = 0
    processed_ticks: int = 0
    last_time: pd.Timestamp | None = None
    references: dict[str, float] = field(default_factory=dict)
    zones: list[XauDailyZoneSignalState] = field(default_factory=list)
    next_window_id: int = 0
    windows: pt.DataFrame[ActiveWindows] = field(default_factory=pd.DataFrame)
