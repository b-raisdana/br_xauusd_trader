import numpy as np
import pandas as pd
import pandera.pandas as pa
from pandera import typing as pt

from br_pre_commit import pandera_validate
from domain.schemas.common.base_dataframe import Timeseries
from domain.schemas.common.ohlcv import MultiTimeframeOHLC


class M15TrendCandles(Timeseries):
    high: pt.Series[float]
    low: pt.Series[float]

    class Config:
        coerce = True

    @pa.dataframe_check
    @classmethod
    @pandera_validate(allow_pandas_dataframe=True)
    def has_valid_price_range(cls, frame: pd.DataFrame) -> bool:
        return (
            frame.size > 0
            and frame[["high", "low"]].isin([float("inf"), float("-inf")]).sum().sum() == 0
            and frame["high"].ge(frame["low"]).all()
        )


class ClosedCandles(MultiTimeframeOHLC):
    class Config:
        coerce = True

    @pa.dataframe_check
    @classmethod
    @pandera_validate(allow_pandas_dataframe=True)
    def has_valid_ohlc_range(cls, frame: pd.DataFrame) -> bool:
        return (
            frame.size > 0
            and frame[["open", "close", "high", "low"]].isin([float("inf"), float("-inf")]).sum().sum() == 0
            and frame["high"].ge(frame[["open", "close", "low"]].max(axis=1)).all()
            and frame["low"].le(frame[["open", "close", "high"]].min(axis=1)).all()
        )


class M15TrendResult(Timeseries):
    trend: pt.Series[np.int8]
    eligible: pt.Series[bool]


class ZeroLagMacdResult(Timeseries):
    macd: pt.Series[float] = pa.Field(nullable=True)
    signal: pt.Series[float] = pa.Field(nullable=True)
    histogram: pt.Series[float] = pa.Field(nullable=True)
    histogram_previous: pt.Series[float] = pa.Field(nullable=True)


class IndicatorConfirmationResult(Timeseries):
    rsi_buy_ready: pt.Series[bool]
    rsi_sell_ready: pt.Series[bool]
    macd_buy_confirmed: pt.Series[bool]
    macd_sell_confirmed: pt.Series[bool]


class SignalCandidateRows(Timeseries):
    signal_id: pt.Series[str]
    setup_type: pt.Series[str] = pa.Field(isin=["reversal", "pullback"])
    direction: pt.Series[str] = pa.Field(isin=["buy", "sell"])
    zone_id: pt.Series[str]
    entry_reference: pt.Series[float]
    expires_at: pt.Series[pd.DatetimeTZDtype(tz="UTC", unit="ns")]


class RealizedTradeRows(Timeseries):
    net_pnl_usd: pt.Series[float]

    class Config:
        coerce = True

    @pa.dataframe_check
    @classmethod
    @pandera_validate(allow_pandas_dataframe=True)
    def has_finite_pnl(cls, frame: pd.DataFrame) -> bool:
        return not frame["net_pnl_usd"].isin([float("inf"), float("-inf")]).any()


class StrategyExecutionEvents(Timeseries):
    event_id: pt.Series[str]
    kind: pt.Series[str] = pa.Field(
        isin=[
            "limit_submitted",
            "limit_canceled",
            "filled",
            "close_requested",
            "close_rejected",
            "close_unknown",
            "closed",
        ],
    )
    order_id: pt.Series[str] = pa.Field(nullable=True)
    position_id: pt.Series[str] = pa.Field(nullable=True)
    direction: pt.Series[str] = pa.Field(nullable=True, isin=["buy", "sell"])
    entry_reference: pt.Series[float] = pa.Field(nullable=True)
    fill_price: pt.Series[float] = pa.Field(nullable=True)
    volume_lots: pt.Series[float] = pa.Field(nullable=True)
    stop_loss: pt.Series[float] = pa.Field(nullable=True)
    take_profit: pt.Series[float] = pa.Field(nullable=True)
    close_reason: pt.Series[str] = pa.Field(nullable=True)
    profit_before_charges_usd: pt.Series[float] = pa.Field(nullable=True)
    commission_cost_usd: pt.Series[float] = pa.Field(nullable=True)
    swap_pnl_usd: pt.Series[float] = pa.Field(nullable=True)
    fee_cost_usd: pt.Series[float] = pa.Field(nullable=True)
    spread_slippage_cost_usd: pt.Series[float] = pa.Field(nullable=True)

    class Config:
        coerce = True


class PositionStateRows(Timeseries):
    status: pt.Series[str]
    order_id: pt.Series[str] = pa.Field(nullable=True)
    position_id: pt.Series[str] = pa.Field(nullable=True)
    direction: pt.Series[str] = pa.Field(nullable=True)
    entry_reference: pt.Series[float] = pa.Field(nullable=True)
    fill_price: pt.Series[float] = pa.Field(nullable=True)
    volume_lots: pt.Series[float] = pa.Field(nullable=True)
    stop_loss: pt.Series[float] = pa.Field(nullable=True)
    take_profit: pt.Series[float] = pa.Field(nullable=True)
    opened_at: pt.Series[str] = pa.Field(nullable=True)
    close_reason: pt.Series[str] = pa.Field(nullable=True)
    close_retry_count: pt.Series[int]
    last_event_id: pt.Series[str] = pa.Field(nullable=True)
    last_realized_net_pnl_usd: pt.Series[float] = pa.Field(nullable=True)


class PositionSnapshotRows(PositionStateRows):
    action: pt.Series[str]


class BrokerCalendarRows(Timeseries):
    session_id: pt.Series[str]
    broker_open: pt.Series[bool]

    @pa.dataframe_check
    @classmethod
    @pandera_validate(allow_pandas_dataframe=True)
    def contains_one_market_close(cls, frame: pd.DataFrame) -> bool:
        return len(frame.index) == 1
