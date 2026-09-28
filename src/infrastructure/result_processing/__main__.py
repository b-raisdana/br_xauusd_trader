from __future__ import annotations

import pandas as pd
from br_py_log_n_profile import profile_it

from application.xauusd_trading_strategy_1_vector.domain.schema import (
    OrderManagementResult,
    PositionTrackingResult,
    StrategyResultWithCandles,
)
from infrastructure.result_processing.io import ResultFilesManifest


@profile_it
def merge_results_with_candles(manifest: ResultFilesManifest) -> ResultFilesManifest:
    for day in manifest.successful_days("per_tick_state"):
        state = manifest.read_daily_ticks_temp_state(day)
        ticks = manifest.read_daily_ticks(day)
        if not state.index.equals(ticks.index):
            ticks = ticks.sort_index(kind="stable")
        if not state.index.equals(ticks.index):
            raise ValueError("Tick and state artifacts must have identical row indexes")
        output = pd.concat([ticks, state], axis=1)
        candles = manifest.read_daily_candles(day).reset_index()
        candles = candles.loc[candles["timeframe"].eq("15min")]
        keys = ["broker", "symbol", "bar_time"]
        payload = [name for name in ("open", "high", "low", "close", "volume") if name in candles]
        candles = candles[keys + payload].rename(columns={name: f"candle_{name}" for name in payload})
        lookup = output.index.to_frame(index=False)
        lookup["bar_time"] = output["bar_time"].to_numpy() - pd.Timedelta(minutes=15)
        merged = lookup.merge(candles, on=keys, how="left", sort=False, validate="many_to_one")
        for name in ("open", "high", "low", "close", "volume"):
            column = f"candle_{name}"
            output[column] = merged[column].to_numpy(dtype=float) if column in merged else float("nan")
        manifest.save_results_with_columns(day, StrategyResultWithCandles.validate(output, lazy=True))
    return manifest


@profile_it
def generate_order_management_columns(manifest: ResultFilesManifest) -> ResultFilesManifest:
    for day in manifest.successful_days("results_with_columns"):
        output = _project_snapshots(
            manifest.read_results_with_columns(day),
            "orders",
            {
                "order_id": "str",
                "order_type": "Int64",
                "order_direction": "Int64",
                "order_status": "Int64",
                "entry_price": "float64",
                "stop_loss": "float64",
                "take_profit": "float64",
                "order_time": "datetime64[ns, UTC]",
            },
        )
        manifest.save_orders(day, OrderManagementResult.validate(output, lazy=True))
    return manifest


@profile_it
def generate_position_tracking_columns(manifest: ResultFilesManifest) -> ResultFilesManifest:
    for day in manifest.successful_days("orders"):
        output = _project_snapshots(
            manifest.read_orders(day),
            "positions",
            {
                "position_id": "str",
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
        )
        manifest.save_positions(day, PositionTrackingResult.validate(output, lazy=True))
    return manifest


def _project_snapshots(result: pd.DataFrame, source: str, dtypes: dict[str, str]) -> pd.DataFrame:
    snapshots = [items[-1] if items else {} for items in result[source]]
    payload = pd.DataFrame.from_records(snapshots, index=result.index, columns=list(dtypes))
    for column, dtype in dtypes.items():
        if dtype.startswith("datetime64"):
            payload[column] = pd.to_datetime(payload[column], utc=True).astype(dtype)
        else:
            payload[column] = payload[column].astype(dtype)
    output = result.copy()
    output[list(dtypes)] = payload
    return output
