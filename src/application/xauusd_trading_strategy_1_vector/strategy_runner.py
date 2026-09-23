from __future__ import annotations

from typing import List, Optional

import pandas as pd
from br_py_log_n_profile import NOT_TESTED, log_w

from domain.schemas.xauusd_vector_strategy import (
    PositionTrackingResult,
    VectorizedCandleInput,
    VectorizedTickInput,
)
from helper.importer import pt
from helper.pandera import pandera_validate

from .result_processing import (
    generate_order_management_columns,
    generate_position_tracking_columns,
    merge_results_with_candles,
)
from .vectorized_strategy import VectorizedXauUsdStrategy
from .zone_cache import ZoneCache


@pandera_validate
def run_vectorized_strategy(
    tick_df: pt.DataFrame[VectorizedTickInput],
    candle_df: pt.DataFrame[VectorizedCandleInput],
    zones_df: pd.DataFrame,
    preload_days: Optional[List[str]] = None,
    *,
    debug: bool = False,
) -> pt.DataFrame[PositionTrackingResult]:
    """
    Run the complete vectorized strategy flow.

    This function orchestrates the entire vectorized strategy execution:
    1. Initialize zone loader with zone data
    2. Initialize vectorized strategy
    3. Process tick data through the strategy
    4. Generate signals, orders, and positions

    Args:
        tick_df: DataFrame with MultiIndex (broker, symbol, datetime, date) and columns (bid, ask)
        candle_df: DataFrame with 15-minute OHLCV data
        zones_df: Zone DataFrame indexed by timeframe and date, with lower,
            upper, priority, and enabled columns.
        preload_days: Retained for compatibility; all supplied zones are already in memory.

    Returns:
        DataFrame with same MultiIndex as input and additional columns for signals, orders, positions
    """
    print("=== Vectorized XAUUSD Strategy Execution ===")
    print(f"Processing {len(tick_df)} ticks")
    print(f"Processing {len(candle_df)} 15-minute candles")
    print(f"Loading {len(zones_df)} zones")

    # Step 1: Initialize zone loader
    print("\n[Step 1] Initializing zone loader...")
    zone_cache = ZoneCache(zones_df)
    print(f"Zone cache initialized with {len(zones_df)} zones")

    # Step 2: Initialize vectorized strategy
    print("\n[Step 2] Initializing vectorized strategy...")
    strategy = VectorizedXauUsdStrategy(zone_cache=zone_cache)
    print("Vectorized strategy initialized")
    # Step 4: Process tick data through the strategy
    print("\n[Step 4] Processing tick data...")
    result = strategy.process_tick_data(tick_df, candle_df)
    if debug:
        result = strategy._per_tick_temp_state.copy()
    result[["bid", "ask"]] = tick_df.sort_index(kind="stable")[["bid", "ask"]].to_numpy()
    print(f"Tick data processed, generated {len(result)} result rows")
    log_w(NOT_TESTED)
    # Step 5: Merge with candle data for additional context
    print("\n[Step 5] Merging with candle data...")
    result_with_candles = merge_results_with_candles(result, candle_df)
    print("Results merged with candle data")

    # Step 6: Generate order management columns
    print("\n[Step 6] Generating order management columns...")
    result_with_orders = generate_order_management_columns(result_with_candles)
    print("Order management columns generated")

    # Step 7: Generate position tracking columns
    print("\n[Step 7] Generating position tracking columns...")
    final_result = generate_position_tracking_columns(result_with_orders)
    print("Position tracking columns generated")

    print("\n=== Strategy Execution Complete ===")
    print(f"Final result has {len(final_result)} rows and {len(final_result.columns)} columns")

    return final_result


@pandera_validate(allow_pandas_dataframe=True)
def get_strategy_internal_state(strategy: VectorizedXauUsdStrategy) -> Optional[pd.DataFrame]:
    """
    Get the internal _per_tick_temp_state DataFrame from the strategy.

    This is useful for debugging and inspection of the strategy's
    internal state during processing.

    Args:
        strategy: VectorizedXauUsdStrategy instance

    Returns:
        Internal _per_tick_temp_state DataFrame or None if not available
    """
    log_w(NOT_TESTED)
    return strategy._per_tick_temp_state
