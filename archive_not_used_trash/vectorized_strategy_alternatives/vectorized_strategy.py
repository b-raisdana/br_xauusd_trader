# from __future__ import annotations
#
# from typing import TYPE_CHECKING
#
# import numpy as np
# import pandas as pd
# from pandera import typing as pt
#
# from domain.schemas.zone import Zone
# from domain.xau_usd.enums import XauTrend
# from domain.xau_usd.models import XauZone
# from helper.pandera import pandera_validate
#
# from .actions import generate_actions
# from .engagement import update_zone_engagement
# from .signals import generate_pullback_signals, generate_reversal_signals
# from .trend import compute_bar_time, update_trend
#
# if TYPE_CHECKING:
#     from .zone_loader import ZoneCache
#
#
# class VectorizedXauUsdStrategy:
#     """Batch tick-state calculations; signal execution remains a research scaffold.
#
#     Python iteration is limited to broker/symbol/day partitions and zone metadata.
#     Inputs must be chronological within each broker/symbol; duplicate tick times
#     retain their supplied order. Only observed, closed bars enter trend history.
#     """
#
#     def __init__(self, zone_cache: ZoneCache):
#         self._temp_state: pd.DataFrame | None = None
#         self._zone_cache = zone_cache
#
#     def process_tick_data(self, tick_data: pd.DataFrame) -> pd.DataFrame:
#         self._temp_state = self._initialize_temp_state(tick_data)
#         if tick_data.empty:
#             return self._temp_state[["action"]].copy()
#
#         parts = []
#         for _, group in self._temp_state.groupby(level=["broker", "symbol"], sort=False):
#             times = group.index.get_level_values("datetime")
#             if not times.is_monotonic_increasing:
#                 raise ValueError("Ticks must be chronological within each broker/symbol")
#             for _, day in group.groupby("broker_day", sort=False):
#                 state = self._process_day_boundaries(day.copy())
#                 state = self._process_bar_boundaries(state)
#                 state = self._process_tick_operations(state)
#                 parts.append(generate_actions(state))
#
#         self._temp_state = pd.concat(parts).sort_index(kind="stable")
#         return self._temp_state[["action"]].copy()
#
#     def _initialize_temp_state(self, df: pd.DataFrame) -> pd.DataFrame:
#         """
#         Initialize the _temp_state DataFrame with all required columns.
#
#         This includes input columns, derived columns, state columns,
#         intermediate calculations, and final output columns.
#         """
#         state = df.copy()
#
#         # Derived time columns
#         state["bar_time"] = self._compute_bar_time(state.index.get_level_values("datetime"))
#         state["broker_day"] = state.index.get_level_values("datetime").strftime("%Y-%m-%d")
#
#         # Trend state columns
#         state["trend"] = XauTrend.NONE.value
#         state["trend_count"] = 0
#         state["trend_high_0"] = 0.0
#         state["trend_high_1"] = 0.0
#         state["trend_high_2"] = 0.0
#         state["trend_low_0"] = 0.0
#         state["trend_low_1"] = 0.0
#         state["trend_low_2"] = 0.0
#
#         # Bar state columns
#         state["bar_open"] = 0.0
#         state["last_bid"] = 0.0
#         state["last_ask"] = 0.0
#         state["bar_active"] = False
#         state["day_active"] = False
#
#         # Zone engagement state - flattened per zone
#         # We'll dynamically add zone-specific columns based on actual zones
#         state["buy_engaged"] = False
#         state["sell_engaged"] = False
#
#         # Signal generation state
#         state["breakout_sequence"] = 0
#         state["reversal_keys"] = ""
#         state["attempted_bars"] = ""
#
#         # Pullback window state - flattened per window
#         state["pullback_active"] = False
#         state["pullback_bar_offset"] = 0
#         state["pullback_penetration_latched"] = False
#         state["pullback_sequence"] = 0
#
#         # Intermediate calculations
#         state["reference_high"] = 0.0
#         state["reference_low"] = 0.0
#         state["multi_zone_tick_gap"] = False
#
#         # Output columns
#         state["action"] = None
#
#         return state
#
#     def _compute_bar_time(self, datetime_series):
#         return compute_bar_time(datetime_series)
#
#     def _process_day_boundaries(self, state: pd.DataFrame) -> pd.DataFrame:
#         # Each daily partition is initialized independently before processing.
#         state["day_active"] = True
#         return state
#
#     def _process_bar_boundaries(self, state: pd.DataFrame) -> pd.DataFrame:
#         """Broadcast prior closed-bar history to ticks without iterating over bars."""
#         if state.empty:
#             return state
#         day_changed = state["broker_day"].ne(state["broker_day"].shift())
#         bar_changed = day_changed | state["bar_time"].ne(state["bar_time"].shift())
#         bar_ids = bar_changed.cumsum().to_numpy() - 1
#         bars = state.groupby(bar_ids, sort=False).agg(
#             high=("bid", "max"), low=("bid", "min"), open=("bid", "first"), day=("broker_day", "first")
#         )
#         counts = bars.groupby("day", sort=False).cumcount().to_numpy()
#         available = np.minimum(counts, 3)
#         state["trend_count"] = available[bar_ids]
#
#         # Gather only preceding bars. Unavailable bootstrap slots remain zero.
#         slots = np.arange(3)
#         positions = np.arange(len(bars))[:, None] - available[:, None] + slots
#         valid = slots < available[:, None]
#         high = np.where(valid, bars["high"].to_numpy()[positions.clip(0, len(bars) - 1)], 0.0)
#         low = np.where(valid, bars["low"].to_numpy()[positions.clip(0, len(bars) - 1)], 0.0)
#         state[["trend_high_0", "trend_high_1", "trend_high_2"]] = high[bar_ids]
#         state[["trend_low_0", "trend_low_1", "trend_low_2"]] = low[bar_ids]
#         state["bar_open"] = bars["open"].to_numpy()[bar_ids]
#         state["bar_active"] = state["day_active"]
#         state["last_bid"] = np.where(bar_changed, state["bid"], state["bid"].shift())
#         state["last_ask"] = np.where(bar_changed, state["ask"], state["ask"].shift())
#         return state
#
#     def _process_tick_operations(self, state: pd.DataFrame) -> pd.DataFrame:
#         broker_day = state["broker_day"].iloc[0]
#         zones = [
#             XauZone(
#                 id=f"{broker_day}:R{number}",
#                 low=row.lower,
#                 high=row.upper,
#                 priority=int(row.priority == "high"),
#             )
#             for number, row in enumerate(self._get_zones_for_group(state).itertuples(), start=1)
#         ]
#         state = update_trend(state)
#         state = update_zone_engagement(state, zones)
#         state = generate_reversal_signals(state, zones)
#         state = generate_pullback_signals(state)
#         state["last_bid"] = state["bid"]
#         state["last_ask"] = state["ask"]
#         return state
#
#     def _update_trend(self, state: pd.DataFrame) -> pd.DataFrame:
#         return update_trend(state)
#
#     @pandera_validate(allow_pandas_dataframe=True)
#     def _get_zones_for_group(self, state: pd.DataFrame) -> pt.DataFrame[Zone]:
#         broker_day = state["broker_day"].iloc[0]
#         zones = self._zone_cache.get_zones_for_day(broker_day)
#         return zones.loc[zones["enabled"]].copy()
