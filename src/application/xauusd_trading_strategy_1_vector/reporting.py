from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from br_py_log_n_profile import log_e, log_exception

from application.xauusd_trading_strategy_1_vector.domain.columnar import NativeStrategyResult, SignalTickState
from application.xauusd_trading_strategy_1_vector.domain.schema import (
    PositionTrackingResult,
    PullbackFeedback,
    VectorizedTick,
)
from br_pre_commit import pandera_validate
from config import app_config
from domain.xau_usd.models import XauPullbackWindowState, XauSignalCandidate
from helper.importer import pt
from infrastructure.result_processing.io import ResultFilesManifest


def _json_default(
    value: XauSignalCandidate | XauPullbackWindowState | PullbackFeedback | datetime | date,
) -> str | dict[str, str | int | float | bool | datetime | None | dict[str, str | float | int]]:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    # log_w(NOT_TESTED)
    log_e(f"Unsupported result value: {type(value).__name__}")
    raise TypeError(f"Unsupported result value: {type(value).__name__}")


@pandera_validate
def _native_market_rows(
    ticks: pt.DataFrame[VectorizedTick], state: pt.DataFrame[SignalTickState]
) -> pt.DataFrame[NativeStrategyResult]:
    if ticks.index.equals(state.index):
        return pd.concat([ticks, state], axis=1)
    keys = list(ticks.index.names)
    left = ticks.reset_index()
    right = state.reset_index()
    left["_tick_occurrence"] = ticks.groupby(level=keys, sort=False).cumcount().array
    right["_tick_occurrence"] = state.groupby(level=keys, sort=False).cumcount().array
    return (
        left.merge(right, on=[*keys, "_tick_occurrence"], how="left", sort=False, validate="one_to_one")
        .drop(columns="_tick_occurrence")
        .set_index(keys)
    )


@pandera_validate
def save_results_to_file(
    manifest: ResultFilesManifest,
    output_file: Path | str,
) -> None:
    """Export primitive native tables, or separate legacy position artifacts."""
    if isinstance(output_file, str):
        output_file = Path(output_file)
    if not output_file.is_relative_to(app_config.path_of_data):
        if output_file.is_absolute():
            log_exception(
                f"Absolute path of {output_file} is not allowed; must be relative to {app_config.path_of_data}",
                ValueError,
            )
        else:
            output_file = app_config.path_of_data / output_file

    days = manifest.successful_days("signal_state")
    if days:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        result = pd.concat(
            [_native_market_rows(manifest.read_daily_ticks(day), manifest.read_daily_signal_state(day)) for day in days]
        )
        result.reset_index().to_parquet(output_file, index=False)
        pd.concat([manifest.read_daily_signals(day) for day in days]).reset_index().to_parquet(
            output_file.with_name(f"{output_file.stem}_signals.parquet"), index=False
        )
        pd.concat([manifest.read_daily_windows(day) for day in days]).reset_index().to_parquet(
            output_file.with_name(f"{output_file.stem}_windows.parquet"), index=False
        )
        print(f"Results saved to {output_file} (Parquet format)")
        return
    result = pd.concat([manifest.read_positions(day) for day in manifest.successful_days("positions")])
    result_reset = result.reset_index()
    for column in result_reset.select_dtypes(include="object", exclude="str"):
        result_reset[column] = result_reset[column].map(
            lambda value: (
                json.dumps(value, default=_json_default)
                if isinstance(value, (tuple, list, dict)) or is_dataclass(value)
                else value
            )
        )
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    result_reset.to_parquet(output_file, index=False)
    print(f"Results saved to {output_file} (Parquet format)")


def print_strategy_summary(manifest: ResultFilesManifest) -> None:
    days = manifest.successful_days("signal_state")
    for day in days:
        state = manifest.read_daily_signal_state(day)
        signals = manifest.read_daily_signals(day)
        print(f"Total ticks processed: {len(state)}")
        for family, name in enumerate(("Breakout", "Reversal", "Pullback")):
            print(f"{name} signals: {signals.family.eq(family).sum()}")
    if days:
        return
    for day in manifest.successful_days("positions"):
        _print_strategy_summary(manifest.read_positions(day))


@pandera_validate(allow_pandas_dataframe=True)
def _print_strategy_summary(result: pt.DataFrame[PositionTrackingResult]) -> None:
    """Internal: print summary from an already-loaded DataFrame."""
    print("\n=== Strategy Execution Summary ===")

    # Basic statistics
    print(f"Total ticks processed: {len(result)}")
    print(f"Total columns: {len(result.columns)}")

    # Action statistics
    if "action" in result.columns:
        action_count = result["action"].notna().sum()
        print(f"Total actions generated: {action_count}")

    # Order statistics
    if "order_id" in result.columns:
        order_count = result["order_id"].nunique()
        print(f"Total orders generated: {order_count}")

        # Order type breakdown
        if "order_type" in result.columns:
            order_types = result[result["order_id"].notna()]["order_type"].value_counts()
            print(f"Order types: {order_types.to_dict()}")

        # Order status breakdown
        if "order_status" in result.columns:
            order_statuses = result[result["order_id"].notna()]["order_status"].value_counts()
            print(f"Order statuses: {order_statuses.to_dict()}")

    # Position statistics
    if "position_id" in result.columns:
        position_count = result["position_id"].nunique()
        print(f"Total positions opened: {position_count}")

        # Position direction breakdown
        if "position_direction" in result.columns:
            position_directions = result[result["position_id"].notna()]["position_direction"].value_counts()
            print(f"Position directions: {position_directions.to_dict()}")

        # Position status breakdown
        if "position_status" in result.columns:
            position_statuses = result[result["position_id"].notna()]["position_status"].value_counts()
            print(f"Position statuses: {position_statuses.to_dict()}")

    # Trend statistics
    if "trend" in result.columns:
        trend_counts = result["trend"].value_counts()
        print(f"Trend distribution: {trend_counts.to_dict()}")

    # Zone engagement statistics
    if "buy_engaged" in result.columns:
        buy_engaged_count = result["buy_engaged"].sum()
        sell_engaged_count = result["sell_engaged"].sum()
        print(f"Zone engagement - BUY: {buy_engaged_count}, SELL: {sell_engaged_count}")

    # Signal statistics
    for family in ("breakout", "reversal", "pullback"):
        column = f"{family}_signals"
        if column in result:
            count = (
                result[column]
                .map(lambda value: len(value) if isinstance(value, (tuple, list)) else int(pd.notna(value)))
                .sum()
            )
            print(f"{family.title()} signals: {count}")

    # Pullback window statistics
    if "pullback_active" in result.columns:
        pullback_active_count = result["pullback_active"].sum()
        print(f"Active pullback windows: {pullback_active_count}")

    # Multi-zone tick gap statistics
    if "multi_zone_tick_gap" in result.columns:
        gap_count = result["multi_zone_tick_gap"].sum()
        print(f"Multi-zone tick gaps: {gap_count}")

    print("=== End Summary ===\n")
