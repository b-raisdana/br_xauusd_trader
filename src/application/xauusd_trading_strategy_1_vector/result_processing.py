from __future__ import annotations

import pandas as pd
from br_py_log_n_profile import profile_it

from application.xauusd_trading_strategy_1_vector.domain.schema import (
    OrderInput,
    OrderManagementResult,
    PositionInput,
    PositionTrackingResult,
    StrategyResult,
    StrategyResultWithCandles,
    VectorizedCandleInput,
)
from domain.xau_usd.enums import XauDirection, XauExecutionStatus
from helper.importer import pt
from helper.pandera import pandera_validate


@profile_it
@pandera_validate
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
    # log_w(NOT_TESTED)
    keys = [
        # "broker", "symbol",
        "bar_time"
    ]
    candles = candle_data.copy()
    if "bar_time" not in candles.columns:
        candles = candles.rename(columns={"datetime": "bar_time"})
    candles["bar_time"] = pd.to_datetime(candles["bar_time"], utc=True)
    if "timeframe" in candles.columns:
        candles = candles.loc[candles["timeframe"].eq("15min")].drop(columns="timeframe")
    payload = [column for column in candles if column not in keys]
    candles = candles.rename(columns={column: f"candle_{column}" for column in payload})
    ticks = result.index.to_frame(index=False)
    # A candle's final OHLC becomes available only at the next bar boundary.
    ticks["bar_time"] = ticks["datetime"].dt.floor("15min") - pd.Timedelta(minutes=15)
    merged = ticks.merge(candles, on=keys, how="left", sort=False, validate="many_to_one")
    output = result.copy()
    context = [f"candle_{column}" for column in payload]
    for column in context:
        output[column] = merged[column].to_numpy()
    if "candle_volume" not in output.columns:
        output["candle_volume"] = float("nan")

    return output


@profile_it
@pandera_validate
def generate_order_management_columns(
    result: pt.DataFrame[OrderInput],
) -> pt.DataFrame[OrderManagementResult]:
    """Project the latest visible order; the orders tuple preserves concurrent orders."""
    return _project_snapshots(
        result,
        "orders",
        {
            "order_id": "object",
            "order_type": "Int64",
            "order_direction": "Int64",
            "order_status": "Int64",
            "entry_price": "float64",
            "stop_loss": "float64",
            "take_profit": "float64",
            "order_time": "datetime64[ns, UTC]",
        },
        action_col="action",
        id_prefix="ORD",
    )


def _normalize_order_status(result):
    """Convert string order_status values to Int64 enum values."""
    if "order_status" in result.columns:
        statuses = result["order_status"]
        if statuses.dtype == object or str(statuses.dtype) == "str":
            status_map = {member.name: member.value for member in XauExecutionStatus}
            converted = statuses.map(lambda v: status_map.get(v, v) if pd.notna(v) else v)
            result = result.copy()
            result["order_status"] = pd.array(converted, dtype="Int64")
    return result


@profile_it
def generate_position_tracking_columns(
    result: pt.DataFrame[PositionInput],
) -> pt.DataFrame[PositionTrackingResult]:
    """Project the latest visible position; positions contains every concurrent snapshot."""
    result = _normalize_order_status(result)
    output = _project_snapshots(
        result,
        "positions",
        {
            "position_id": "object",
            "position_direction": "Int64",
            "position_size": "float64",
            "position_entry_price": "float64",
            "position_current_price": "float64",
            "position_unrealized_pnl": "float64",
            "position_realized_pnl": "float64",
            "position_status": "Int64",
            "position_time": "datetime64[ns, UTC]",
            "position_close_time": "datetime64[ns, UTC]",
        },
        id_prefix="POS",
        order_status_col="order_status",
    )
    return output


def _project_snapshots(result, source, dtypes, action_col=None, id_prefix=None, order_status_col=None):
    source_col = result[source] if source in result else [None] * len(result)
    snapshots = [items[-1] if pd.notna(items) and items else {} for items in source_col]
    payload = pd.DataFrame.from_records(snapshots, index=result.index, columns=list(dtypes))
    for column, dtype in dtypes.items():
        if dtype.startswith("datetime64"):
            payload[column] = pd.to_datetime(payload[column], utc=True).astype(dtype)
        elif dtype == "object":
            payload[column] = payload[column].astype(object).where(payload[column].notna(), None)
        else:
            payload[column] = payload[column].astype(dtype)

    if action_col and action_col in result.columns:
        actions = result[action_col]
        has_snapshot = pd.Series(
            [bool(items) if pd.notna(items) else False for items in source_col],
            index=result.index,
        )
        needs_synthetic = actions.notna() & ~has_snapshot
        if needs_synthetic.any():
            counter = 0
            action_vals = result[action_col].tolist()
            bid_vals = result["bid"].tolist() if "bid" in result.columns else [None] * len(result)
            ask_vals = result["ask"].tolist() if "ask" in result.columns else [None] * len(result)
            datetime_vals = (
                result.index.get_level_values("datetime").tolist()
                if isinstance(result.index, pd.MultiIndex)
                else list(result.index)
            )
            order_id_pos = payload.columns.get_loc("order_id")
            order_dir_pos = payload.columns.get_loc("order_direction")
            entry_price_pos = payload.columns.get_loc("entry_price")
            order_time_pos = payload.columns.get_loc("order_time")
            for i in range(len(result)):
                if not needs_synthetic.iloc[i]:
                    continue
                counter += 1
                payload.iloc[i, order_id_pos] = f"{id_prefix}-{counter:06d}"
                action = action_vals[i]
                if action == "BUY":
                    payload.iloc[i, order_dir_pos] = XauDirection.BUY
                    payload.iloc[i, entry_price_pos] = bid_vals[i]
                elif action == "SELL":
                    payload.iloc[i, order_dir_pos] = XauDirection.SELL
                    payload.iloc[i, entry_price_pos] = ask_vals[i]
                payload.iloc[i, order_time_pos] = datetime_vals[i]

    if order_status_col and order_status_col in result.columns and id_prefix:
        statuses = result[order_status_col].tolist()
        needs_synthetic = pd.Series(
            [
                s == "FILLED" or (pd.notna(s) and s == XauExecutionStatus.FILLED) if pd.notna(s) else False
                for s in statuses
            ],
            index=result.index,
        )
        if needs_synthetic.any():
            counter = 0
            bid_vals = result["bid"].tolist() if "bid" in result.columns else [None] * len(result)
            ask_vals = result["ask"].tolist() if "ask" in result.columns else [None] * len(result)
            datetime_vals = (
                result.index.get_level_values("datetime").tolist()
                if isinstance(result.index, pd.MultiIndex)
                else list(result.index)
            )
            order_dir_vals = (
                result["order_direction"].tolist() if "order_direction" in result.columns else [None] * len(result)
            )
            pos_id_pos = payload.columns.get_loc("position_id")
            pos_time_pos = payload.columns.get_loc("position_time")
            pos_price_pos = payload.columns.get_loc("position_current_price")
            for i in range(len(result)):
                if not needs_synthetic.iloc[i]:
                    continue
                counter += 1
                payload.iloc[i, pos_id_pos] = f"{id_prefix}-{counter:06d}"
                payload.iloc[i, pos_time_pos] = datetime_vals[i]
                order_direction = order_dir_vals[i]
                if order_direction == XauDirection.BUY:
                    payload.iloc[i, pos_price_pos] = bid_vals[i]
                elif order_direction == XauDirection.SELL:
                    payload.iloc[i, pos_price_pos] = ask_vals[i]

    output = result.copy()
    output[list(dtypes)] = payload
    return output
