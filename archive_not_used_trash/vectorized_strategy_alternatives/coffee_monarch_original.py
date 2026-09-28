from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from domain.xau_usd.constants import (
    BREAKOUT_BUFFER_USD,
)
from domain.xau_usd.enums import XauTrend
from domain.xau_usd.models import XauZone

from .zone_loader import ZoneLoader


class VectorizedXauUsdStrategy:
    """
    Vectorized implementation of the XAUUSD trading strategy.

    Processes pandas DataFrames with MultiIndex (broker, symbol, datetime, date)
    and generates trading signals using vectorized pandas operations.

    The implementation follows the MT5 source of truth (mt5/XAUUSD_MVP.mq5)
    and uses 15-minute bars for all bar-based calculations.
    """

    def __init__(self, zone_loader: Optional[ZoneLoader] = None):
        """
        Initialize the vectorized strategy.

        Args:
            zone_loader: Optional ZoneLoader instance for loading zone data.
                        If None, creates a default ZoneLoader.
        """
        self._temp_state: Optional[pd.DataFrame] = None
        # self._zone_loader = zone_loader or ZoneLoader()

    def process_tick_data(
        self,
        tick_data: pd.DataFrame,
        preload_days: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Process tick data and generate trading signals.

        Args:
            tick_data: DataFrame with MultiIndex (broker, symbol, datetime, date)
                      and columns (bid, ask)
            preload_days: Optional list of broker_day strings to preload zones for
                        If None, zones are loaded on-demand

        Returns:
            DataFrame with same MultiIndex and an additional 'action' column
        """
        # Preload zones if specified
        if preload_days:
            self._zone_loader.preload_zones(preload_days)

        # Create a copy to avoid modifying input
        df = tick_data.copy()

        # Initialize _temp_state with required columns
        self._temp_state = self._initialize_temp_state(df)

        # Process each (broker, symbol) group independently
        result_dfs = []
        for (broker, symbol), group_df in df.groupby(level=["broker", "symbol"]):
            processed_group = self._process_group(group_df, broker, symbol)
            result_dfs.append(processed_group)

        # Combine results
        result = pd.concat(result_dfs)

        # Ensure output matches input structure
        result = result.sort_index()

        return result

    def _initialize_temp_state(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Initialize the _temp_state DataFrame with all required columns.

        This includes input columns, derived columns, state columns,
        intermediate calculations, and final output columns.
        """
        state = df.copy()

        # Derived time columns
        state["bar_time"] = self._compute_bar_time(state.index.get_level_values("datetime"))
        state["broker_day"] = state.index.get_level_values("datetime").strftime("%Y-%m-%d")

        # Trend state columns
        state["trend"] = XauTrend.NONE.value
        state["trend_count"] = 0
        state["trend_high_0"] = 0.0
        state["trend_high_1"] = 0.0
        state["trend_high_2"] = 0.0
        state["trend_low_0"] = 0.0
        state["trend_low_1"] = 0.0
        state["trend_low_2"] = 0.0

        # Bar state columns
        state["bar_open"] = 0.0
        state["last_bid"] = 0.0
        state["last_ask"] = 0.0
        state["bar_active"] = False
        state["day_active"] = False

        # Zone engagement state - flattened per zone
        # We'll dynamically add zone-specific columns based on actual zones
        state["buy_engaged"] = False
        state["sell_engaged"] = False

        # Signal generation state
        state["breakout_sequence"] = 0
        state["reversal_keys"] = ""
        state["attempted_bars"] = ""

        # Pullback window state - flattened per window
        state["pullback_active"] = False
        state["pullback_bar_offset"] = 0
        state["pullback_penetration_latched"] = False
        state["pullback_sequence"] = 0

        # Intermediate calculations
        state["reference_high"] = 0.0
        state["reference_low"] = 0.0
        state["multi_zone_tick_gap"] = False

        # Output columns
        state["action"] = None

        return state

    def _compute_bar_time(self, datetime_series: pd.Series) -> pd.Series:
        """
        Compute 15-minute bar time from datetime.

        Floors datetime to 15-minute intervals (PERIOD_M15 as in MT5).
        """
        # Convert to datetime if needed
        if not isinstance(datetime_series, pd.DatetimeIndex):
            datetime_series = pd.to_datetime(datetime_series)

        # Floor to 15-minute intervals
        bar_time = datetime_series.dt.floor("15min")

        return bar_time

    def _process_group(
        self,
        group_df: pd.DataFrame,
        broker: str,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Process a single (broker, symbol) group.

        This is where the main vectorized processing happens.
        Zones are loaded on-demand using the zone_loader based on broker_day.
        """
        # Get the state for this group
        group_state = self._temp_state.loc[(broker, symbol)].copy()

        # Process day boundaries (reinitialize state on day change)
        group_state = self._process_day_boundaries(group_state)

        # Process bar boundaries (close previous bar, begin new bar)
        group_state = self._process_bar_boundaries(group_state)

        # Process tick-level operations (trend, engagement, signals)
        group_state = self._process_tick_operations(group_state)

        # Generate final actions
        group_state = self._generate_actions(group_state)

        # Return only the action column with original index
        result = group_state[["action"]].copy()

        return result

    def _process_day_boundaries(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Process day boundaries and initialize state for new days.

        When broker_day changes, reinitialize all state.
        Uses vectorized operations for efficiency.
        """
        # Detect day changes
        day_changed = state["broker_day"] != state["broker_day"].shift(1)
        day_changed.iloc[0] = True  # First row is always a day change

        # Create day groups for vectorized processing
        state["day_group"] = day_changed.cumsum()

        # For each day group, initialize state
        for _day_group_id, day_group in state.groupby("day_group"):
            day_group["broker_day"].iloc[0]

            # Reset trend state at day start
            day_group.loc[day_group.index[0], "trend"] = XauTrend.NONE.value
            day_group.loc[day_group.index[0], "trend_count"] = 0
            day_group.loc[day_group.index[0], "trend_high_0"] = 0.0
            day_group.loc[day_group.index[0], "trend_high_1"] = 0.0
            day_group.loc[day_group.index[0], "trend_high_2"] = 0.0
            day_group.loc[day_group.index[0], "trend_low_0"] = 0.0
            day_group.loc[day_group.index[0], "trend_low_1"] = 0.0
            day_group.loc[day_group.index[0], "trend_low_2"] = 0.0

            # Reset bar state at day start
            day_group.loc[day_group.index[0], "bar_active"] = False
            day_group.loc[day_group.index[0], "day_active"] = True
            day_group.loc[day_group.index[0], "bar_open"] = 0.0
            day_group.loc[day_group.index[0], "last_bid"] = 0.0
            day_group.loc[day_group.index[0], "last_ask"] = 0.0

            # Reset signal state at day start
            day_group.loc[day_group.index[0], "breakout_sequence"] = 0
            day_group.loc[day_group.index[0], "reversal_keys"] = ""
            day_group.loc[day_group.index[0], "attempted_bars"] = ""

            # Reset pullback state at day start
            day_group.loc[day_group.index[0], "pullback_active"] = False
            day_group.loc[day_group.index[0], "pullback_bar_offset"] = 0
            day_group.loc[day_group.index[0], "pullback_penetration_latched"] = False
            day_group.loc[day_group.index[0], "pullback_sequence"] = 0

            # Reset engagement at day start
            day_group.loc[day_group.index[0], "buy_engaged"] = False
            day_group.loc[day_group.index[0], "sell_engaged"] = False

            # Update the main state dataframe
            state.loc[day_group.index] = day_group

        # Drop the temporary day_group column
        state = state.drop(columns=["day_group"])

        return state

    def _process_bar_boundaries(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Process 15-minute bar boundaries.

        When bar_time changes, close previous bar and begin new bar.
        Uses vectorized operations for efficiency.
        """
        # Detect bar changes
        bar_changed = state["bar_time"] != state["bar_time"].shift(1)
        bar_changed.iloc[0] = True  # First row is always a bar change

        # Create bar groups for vectorized processing
        state["bar_group"] = bar_changed.cumsum()

        # For each bar group, process bar close and begin new bar
        for _bar_group_id, bar_group in state.groupby("bar_group"):
            if not bar_group["day_active"].iloc[0]:
                continue

            # Close previous bar (generate breakout signals)
            bar_group = self._close_bar(bar_group)

            # Begin new bar
            bar_group = self._begin_bar(bar_group)

            # Update the main state dataframe
            state.loc[bar_group.index] = bar_group

        # Drop the temporary bar_group column
        state = state.drop(columns=["bar_group"])

        return state

    def _close_bar(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Close the previous bar and generate breakout signals.

        This corresponds to CloseCoordinatorBar in the Python implementation.
        Uses vectorized operations where possible.
        """
        if len(state) == 0:
            return state

        # Get bar close price (last bid of the bar)
        close_bid = state.iloc[-1]["bid"]

        # Set bar_active to False
        state.iloc[-1, state.columns.get_loc("bar_active")] = False

        # Record trend candle (update trend history)
        # Use the bid range as a proxy for bar high/low
        bar_high = state["bid"].max()
        bar_low = state["bid"].min()

        # Update trend count and rolling arrays
        last_count = state.iloc[-1]["trend_count"]
        if last_count < 3:
            # Still in initialization phase
            state.iloc[-1, state.columns.get_loc("trend_count")] = last_count + 1
            if last_count == 0:
                state.iloc[-1, state.columns.get_loc("trend_high_0")] = bar_high
                state.iloc[-1, state.columns.get_loc("trend_low_0")] = bar_low
            elif last_count == 1:
                state.iloc[-1, state.columns.get_loc("trend_high_1")] = bar_high
                state.iloc[-1, state.columns.get_loc("trend_low_1")] = bar_low
            else:  # last_count == 2
                state.iloc[-1, state.columns.get_loc("trend_high_2")] = bar_high
                state.iloc[-1, state.columns.get_loc("trend_low_2")] = bar_low
        else:
            # Rolling window phase - shift and add new
            state.iloc[-1, state.columns.get_loc("trend_high_0")] = state.iloc[-2]["trend_high_1"]
            state.iloc[-1, state.columns.get_loc("trend_high_1")] = state.iloc[-2]["trend_high_2"]
            state.iloc[-1, state.columns.get_loc("trend_high_2")] = bar_high
            state.iloc[-1, state.columns.get_loc("trend_low_0")] = state.iloc[-2]["trend_low_1"]
            state.iloc[-1, state.columns.get_loc("trend_low_1")] = state.iloc[-2]["trend_low_2"]
            state.iloc[-1, state.columns.get_loc("trend_low_2")] = bar_low

        # Generate breakout signals
        state = self._generate_breakout_signals(state, close_bid, bar_high, bar_low)

        return state

    def _generate_breakout_signals(
        self,
        state: pd.DataFrame,
        close_bid: float,
        bar_high: float,
        bar_low: float,
    ) -> pd.DataFrame:
        """
        Generate breakout signals at bar close.

        This implements the logic from CloseCoordinatorBar in coordinator.py.
        Uses vectorized operations to detect valid breakouts.

        Breakout conditions:
        - Zone must be engaged (buy_engaged for BUY, sell_engaged for SELL)
        - Trend must match direction (UP for BUY, DOWN for SELL)
        - Close price must break through zone boundary with buffer
        """
        # Get zones for the current group
        zones = self._get_zones_for_group(state)

        if not zones:
            return state

        # Get current trend
        current_trend = state.iloc[-1]["trend"]

        # Get engagement states
        buy_engaged = state.iloc[-1]["buy_engaged"]
        sell_engaged = state.iloc[-1]["sell_engaged"]

        # Check breakout conditions for each zone and direction
        for zone in zones:
            # BUY breakout: engaged, trend == UP, close > zone.high + BREAKOUT_BUFFER_USD
            (buy_engaged and current_trend == XauTrend.UP.value and close_bid > zone.high + BREAKOUT_BUFFER_USD)

            # SELL breakout: engaged, trend == DOWN, close < zone.low - BREAKOUT_BUFFER_USD
            (sell_engaged and current_trend == XauTrend.DOWN.value and close_bid < zone.low - BREAKOUT_BUFFER_USD)

            # Generate breakout signals
            # This would create pullback windows and update breakout_sequence
            # For now, this is a placeholder

        return state

    def _begin_bar(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Begin a new bar.

        This corresponds to BeginCoordinatorBar in the Python implementation.
        Uses vectorized operations for efficiency.
        """
        if len(state) == 0:
            return state

        # Set bar_open to current bid (first tick of the bar)
        state.iloc[0, state.columns.get_loc("bar_open")] = state.iloc[0]["bid"]

        # Set last_bid and last_ask
        state.iloc[0, state.columns.get_loc("last_bid")] = state.iloc[0]["bid"]
        state.iloc[0, state.columns.get_loc("last_ask")] = state.iloc[0]["ask"]

        # Reset engagement based on bar open
        state.iloc[0, state.columns.get_loc("buy_engaged")] = False
        state.iloc[0, state.columns.get_loc("sell_engaged")] = False

        # Set bar_active to True
        state.iloc[0, state.columns.get_loc("bar_active")] = True

        # Advance pullback window offsets
        # This would need proper pullback window state management

        return state

    def _process_tick_operations(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Process tick-level operations.

        This includes trend updates, zone engagement updates,
        and signal generation (reversal, pullback).
        Uses vectorized operations for efficiency.
        """
        # Update trend based on current bid
        state = self._update_trend(state)

        # Update zone engagement
        state = self._update_zone_engagement(state)

        # Generate reversal signals
        state = self._generate_reversal_signals(state)

        # Generate pullback signals
        state = self._generate_pullback_signals(state)

        # Update last_bid and last_ask
        state["last_bid"] = state["bid"]
        state["last_ask"] = state["ask"]

        return state

    def _update_trend(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Update trend based on current bid and reference levels.

        Uses vectorized operations to compute trend updates.
        This implements the logic from process_trend_tick in state.py.
        """
        # Compute reference high and low from trend history
        # Use the available trend data based on count

        # Vectorized reference calculation
        def compute_reference_high(row):
            count = int(row["trend_count"])
            if count == 0:
                return 0.0
            elif count == 1:
                return row["trend_high_0"]
            elif count == 2:
                return max(row["trend_high_0"], row["trend_high_1"])
            else:  # count >= 3
                return max(row["trend_high_0"], row["trend_high_1"], row["trend_high_2"])

        def compute_reference_low(row):
            count = int(row["trend_count"])
            if count == 0:
                return 0.0
            elif count == 1:
                return row["trend_low_0"]
            elif count == 2:
                return min(row["trend_low_0"], row["trend_low_1"])
            else:  # count >= 3
                return min(row["trend_low_0"], row["trend_low_1"], row["trend_low_2"])

        state["reference_high"] = state.apply(compute_reference_high, axis=1)
        state["reference_low"] = state.apply(compute_reference_low, axis=1)

        # Update trend based on bid vs reference levels
        # If bid > reference_high: trend = UP
        # If bid < reference_low: trend = DOWN
        # Else: trend unchanged

        # Only update trend when we have valid references (count > 0)
        has_reference = state["trend_count"] > 0

        state.loc[has_reference, "trend"] = np.where(
            state.loc[has_reference, "bid"] > state.loc[has_reference, "reference_high"],
            XauTrend.UP.value,
            np.where(
                state.loc[has_reference, "bid"] < state.loc[has_reference, "reference_low"],
                XauTrend.DOWN.value,
                state.loc[has_reference, "trend"],  # Keep previous trend
            ),
        )

        return state

    def _update_zone_engagement(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Update zone engagement based on bid movement.

        Uses vectorized operations to detect zone boundary crosses.
        This implements the logic from update_zone_engagement in state.py.
        """
        # Get previous bid (shifted)
        previous_bid = state["last_bid"].shift(1)
        previous_bid.iloc[0] = state.iloc[0]["bar_open"]  # First row uses bar open

        # Get current bid
        current_bid = state["bid"]

        # Get zones for the current broker_day
        # For simplicity, we'll use a single zone set for the entire group
        # In a full implementation, this would be per-broker_day
        zones = self._get_zones_for_group(state)

        if not zones:
            # No zones available, skip engagement update
            return state

        # Count directional zone crosses
        # This implements count_directional_crosses from zone.py
        crosses = self._count_directional_crosses_vectorized(zones, previous_bid, current_bid)

        # Detect multi-zone tick gaps
        state["multi_zone_tick_gap"] = crosses > 1

        # Update engagement based on boundary crosses
        # This implements the logic from update_zone_engagement in state.py

        # For multi-zone tick gaps, set engagement based on current position
        multi_zone_gap = state["multi_zone_tick_gap"]

        for zone in zones:
            # Check if current bid is inside zone
            inside_zone = (current_bid >= zone.low) & (current_bid <= zone.high)

            # For multi-zone gaps, set engagement based on current position
            state.loc[multi_zone_gap & inside_zone, "buy_engaged"] = True
            state.loc[multi_zone_gap & inside_zone, "sell_engaged"] = True

            # For single crosses, update engagement incrementally
            # BUY engagement: previous_bid < zone.low <= current_bid
            buy_cross = (~state["buy_engaged"]) & (previous_bid < zone.low) & (current_bid >= zone.low)
            state.loc[buy_cross, "buy_engaged"] = True

            # SELL engagement: previous_bid > zone.high >= current_bid
            sell_cross = (~state["sell_engaged"]) & (previous_bid > zone.high) & (current_bid <= zone.high)
            state.loc[sell_cross, "sell_engaged"] = True

        return state

    def _get_zones_for_group(self, state: pd.DataFrame) -> list[XauZone]:
        """
        Get zones for the current group.

        This loads zones based on broker_day using the zone_loader.
        Implements zone loading logic similar to LoadGeneratedRawZones in MT5.
        """
        # Get the broker_day for this group
        broker_day = state["broker_day"].iloc[0]

        # Load zones using the zone_loader
        zones = self._zone_loader.load_zones_for_day(broker_day)

        return zones

    def _count_directional_crosses_vectorized(
        self,
        zones: List[XauZone],
        previous_bid: pd.Series,
        current_bid: pd.Series,
    ) -> pd.Series:
        """
        Count directional zone crosses using vectorized operations.

        This implements count_directional_crosses from zone.py.
        """
        crosses = pd.Series(0, index=previous_bid.index)

        for zone in zones:
            # Count upward crosses: previous_bid < zone.low <= current_bid
            upward_cross = (previous_bid < zone.low) & (current_bid >= zone.low)
            crosses += upward_cross.astype(int)

            # Count downward crosses: previous_bid > zone.high >= current_bid
            downward_cross = (previous_bid > zone.high) & (current_bid <= zone.high)
            crosses += downward_cross.astype(int)

        return crosses

    def _generate_reversal_signals(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Generate reversal signals on zone touches against trend.

        Uses vectorized operations to detect valid reversal touches.
        This implements the logic from reversal_directional_touch in zone.py
        and ProcessCoordinatorTick in coordinator.py.
        """
        # Get zones for the current group
        zones = self._get_zones_for_group(state)

        if not zones:
            return state

        # Get previous bid
        previous_bid = state["last_bid"].shift(1)
        previous_bid.iloc[0] = state.iloc[0]["bar_open"]

        # Get current bid
        current_bid = state["bid"]

        # Get current trend
        current_trend = state["trend"]

        # Check multi-zone tick gap
        multi_zone_gap = state["multi_zone_tick_gap"]

        # Get bar_id for reversal key generation
        # This would need proper bar_id tracking based on bar_time
        bar_id = state["bar_time"].astype(str)

        # Initialize reversal_signals column if not exists
        if "reversal_signals" not in state.columns:
            state["reversal_signals"] = None

        # For each zone and direction, check for reversal touches
        for zone in zones:
            # SELL reversal: trend == UP and previous_bid < zone.low and current_bid >= zone.low
            (
                (current_trend == XauTrend.UP.value)
                & (~multi_zone_gap)
                & (previous_bid < zone.low)
                & (current_bid >= zone.low)
            )

            # BUY reversal: trend == DOWN and previous_bid > zone.high and current_bid <= zone.high
            (
                (current_trend == XauTrend.DOWN.value)
                & (~multi_zone_gap)
                & (previous_bid > zone.high)
                & (current_bid <= zone.high)
            )

            # Generate reversal keys for uniqueness tracking
            # Key format: "bar_id:R:zone_id:side" where side is 0 for BUY, 1 for SELL
            bar_id + ":R:" + zone.id + ":1"
            bar_id + ":R:" + zone.id + ":0"

            # Track reversal keys to ensure uniqueness per bar
            # This would need proper reversal_keys column management

        return state

    def _generate_pullback_signals(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Generate pullback signals from active pullback windows.

        Uses vectorized operations to evaluate pullback conditions.
        This implements the logic from evaluate_pullback_price in state.py
        and ProcessCoordinatorTick in coordinator.py.
        """
        # This is a placeholder - full implementation would:
        # 1. Check each active pullback window
        # 2. Evaluate penetration conditions
        # 3. Check usage allowances
        # 4. Generate signals with proper sequencing

        # Pullback conditions:
        # Window must be active (1 <= bar_offset <= 5)
        # Price must penetrate zone (bid <= zone.high - PULLBACK_PENETRATION_USD for BUY)
        # Usage must be allowed based on zone priority and daily fills

        # Initialize pullback_signals column if not exists
        if "pullback_signals" not in state.columns:
            state["pullback_signals"] = None

        # Check if there are active pullback windows
        # This would need proper pullback window state management
        pullback_active = state["pullback_active"]

        if not pullback_active.any():
            return state

        # Get current bid
        state["bid"]

        # Check penetration conditions for active windows
        # BUY pullback: bid <= zone.high - PULLBACK_PENETRATION_USD
        # SELL pullback: bid >= zone.low + PULLBACK_PENETRATION_USD

        # This would need per-window zone information
        # For now, this is a placeholder

        return state

    def _generate_actions(self, state: pd.DataFrame) -> pd.DataFrame:
        """
        Generate final action column from signal candidates.

        Maps signal candidates to action values that match MT5 semantics.
        This corresponds to the signal generation and processing in the MT5 implementation.
        """
        # Initialize action column
        state["action"] = None

        # Collect signal candidates from breakout, reversal, and pullback signals
        # This would need proper signal candidate management

        # For now, implement basic action generation based on available signals
        # In a full implementation, this would:
        # 1. Collect breakout signals from bar close
        # 2. Collect reversal signals from coordinator tick
        # 3. Collect pullback signals from active windows
        # 4. Apply risk management filters (portfolio risk, concurrency, margin)
        # 5. Generate final action values

        # Action values in MT5 implementation:
        # - Market orders for breakouts and reversals
        # - Pending stop orders for pullbacks
        # - Action includes direction (BUY/SELL), order type, entry price, SL, TP

        # For now, set action to None (no action) as placeholder
        # The actual action generation would depend on signal candidates
        # and risk management decisions

        return state
