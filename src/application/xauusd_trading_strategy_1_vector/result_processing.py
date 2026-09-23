from __future__ import annotations

import pandas as pd
from br_py_log_n_profile import NOT_TESTED, log_w

from domain.schemas.xauusd_vector_strategy import (
    OrderInput,
    OrderManagementResult,
    PositionInput,
    PositionTrackingResult,
    StrategyResult,
    StrategyResultWithCandles,
    VectorizedCandleInput,
)
from helper.importer import pt
from helper.pandera import pandera_validate


@pandera_validate(allow_pandas_dataframe=True)
def merge_results_with_candles(
    result: pt.DataFrame[StrategyResult],
    candle_data: pt.DataFrame[VectorizedCandleInput],
) -> pt.DataFrame[StrategyResultWithCandles]:
    """
    Merge strategy results with 15-minute candle data.

    This adds candle context to the tick-level results.

    Args:
        result: DataFrame with strategy results
        candle_data: DataFrame with 15-minute OHLCV data

    Returns:
        Merged DataFrame with additional candle columns
    """
    log_w(NOT_TESTED)
    keys = ["broker", "symbol", "bar_time"]
    candles = candle_data.copy()
    if "bar_time" not in candles.columns:
        candles = candles.rename(columns={"datetime": "bar_time"})
    candles["bar_time"] = pd.to_datetime(candles["bar_time"], utc=True)
    if "timeframe" in candles:
        candles = candles.loc[candles["timeframe"].eq("15min")].drop(columns="timeframe")
    payload = [column for column in candles if column not in keys]
    candles = candles.rename(columns={column: f"candle_{column}" for column in payload})
    ticks = result.index.to_frame(index=False)
    # A candle's final OHLC becomes available only at the next bar boundary.
    ticks["bar_time"] = ticks["datetime"].dt.floor("15min") - pd.Timedelta(minutes=15)
    merged = ticks.merge(candles, on=keys, how="left", sort=False, validate="many_to_one")
    output = result.copy()
    context = [f"candle_{column}" for column in payload]
    output[context] = merged[context].to_numpy()
    return output


@pandera_validate(allow_pandas_dataframe=True)
def generate_order_management_columns(
    result: pt.DataFrame[OrderInput],
) -> pt.DataFrame[OrderManagementResult]:
    """
    Generate order management columns for the strategy results.

    This adds columns for tracking order lifecycle:
    - order_id: Unique identifier for each order
    - order_type: Type of order (MARKET, PENDING_STOP, etc.)
    - order_direction: Direction of order (BUY, SELL)
    - order_status: Status of order (PENDING, FILLED, CANCELLED, etc.)
    - entry_price: Entry price for the order
    - stop_loss: Stop loss price
    - take_profit: Take profit price
    - order_time: Time when order was created

    Args:
        result: DataFrame with strategy results

    Returns:
        DataFrame with additional order management columns
    """
    log_w(NOT_TESTED)
    result = result.copy()

    # Initialize order management columns
    result["order_id"] = None
    result["order_type"] = None
    result["order_direction"] = None
    result["order_status"] = None
    result["entry_price"] = None
    result["stop_loss"] = None
    result["take_profit"] = None
    result["order_time"] = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns, UTC]")

    # Generate order IDs for rows with actions
    # This is a placeholder - in full implementation, this would
    # be based on actual signal generation logic
    action_mask = result["action"].notna()

    sequence = action_mask.cumsum().loc[action_mask].astype(str).str.zfill(6)
    result.loc[action_mask, "order_id"] = ("ORD-" + sequence).to_numpy()
    result.loc[action_mask, "order_time"] = result.index.get_level_values("datetime")[action_mask]

    return result


@pandera_validate(allow_pandas_dataframe=True)
def generate_position_tracking_columns(
    result: pt.DataFrame[PositionInput],
) -> pt.DataFrame[PositionTrackingResult]:
    """
    Generate position tracking columns for the strategy results.

    This adds columns for tracking position lifecycle:
    - position_id: Unique identifier for each position
    - position_direction: Direction of position (BUY=LONG, SELL=SHORT)
    - position_size: Size of position in lots
    - entry_price: Entry price for the position
    - current_price: Current market price
    - unrealized_pnl: Unrealized profit/loss
    - position_status: Status of position (OPEN, CLOSED, etc.)
    - position_time: Time when position was opened

    Args:
        result: DataFrame with strategy results

    Returns:
        DataFrame with additional position tracking columns
    """
    log_w(NOT_TESTED)
    result = result.copy()

    # Initialize position tracking columns
    result["position_id"] = None
    result["position_direction"] = None
    result["position_size"] = None
    result["position_entry_price"] = None
    result["position_current_price"] = None
    result["position_unrealized_pnl"] = None
    result["position_status"] = None
    result["position_time"] = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns, UTC]")

    # Generate position IDs for filled orders
    # This is a placeholder - in full implementation, this would
    # be based on actual order fill logic
    filled_mask = (
        (result["order_status"] == "FILLED")
        if "order_status" in result.columns
        else pd.Series([False] * len(result), index=result.index)
    )

    sequence = filled_mask.cumsum().loc[filled_mask].astype(str).str.zfill(6)
    result.loc[filled_mask, "position_id"] = ("POS-" + sequence).to_numpy()
    result.loc[filled_mask, "position_time"] = result.index.get_level_values("datetime")[filled_mask]
    result.loc[filled_mask, "position_current_price"] = result.loc[filled_mask, "bid"].to_numpy()

    return result
