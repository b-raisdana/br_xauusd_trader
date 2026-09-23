from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from br_py_log_n_profile import NOT_TESTED, log_e, log_w

from domain.schemas.xauusd_vector_strategy import PositionTrackingResult
from helper.importer import pt
from helper.pandera import pandera_validate


def _json_default(value):
    log_w(NOT_TESTED)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    log_e(f"Unsupported result value: {type(value).__name__}")
    raise TypeError(f"Unsupported result value: {type(value).__name__}")


@pandera_validate(allow_pandas_dataframe=True)
def save_results_to_file(
    result: pt.DataFrame[PositionTrackingResult],
    output_file: str,
) -> None:
    """
    Save strategy results to a file.

    Args:
        result: DataFrame with strategy results
        output_file: Path to output file
        format: Output format ('csv' or 'parquet')
    """
    log_w(NOT_TESTED)
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


@pandera_validate(allow_pandas_dataframe=True)
def print_strategy_summary(result: pd.DataFrame) -> None:
    """
    Print a comprehensive summary of the strategy execution results.

    This function provides detailed statistics about the strategy execution,
    including tick processing, signal generation, order management, and
    position tracking metrics.

    Args:
        result: DataFrame with strategy results
    """
    log_w(NOT_TESTED)
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
