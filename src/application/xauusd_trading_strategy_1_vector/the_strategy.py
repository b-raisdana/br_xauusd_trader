from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
from br_py_log_n_profile import log_e, profile_it
from br_py_log_n_profile.do_log.log_it import NOT_TESTED, log_w

from application.xauusd_trading_strategy_1_vector.domain.schema import (
    BarInfo,
    PerTickState,
    StrategyResult,
    VectorizedTick,
    ZoneDayInput,
)
from domain.schemas.tick import Tick
from domain.xau_usd.enums import XauTrend
from domain.xau_usd.models import XauZone
from helper.importer import pt
from helper.pandera import pandera_validate

from .actions import generate_actions
from .domain.replay import ReplayConfig
from .domain.schema import VectorizedCandleInput
from .engagement import update_zone_engagement
from .replay import ExecutionReplay
from .signals import generate_breakout_signals, generate_pullback_signals, generate_reversal_signals
from .trend import compute_bar_time, update_trend
from .zone_cache import ZoneCache


class VectorizedXauUsdStrategy:
    """Batch M15 breakout candidates; execution still requires risk approval.

    Each call is an independent batch. Only a later bar in the same day confirms
    a close; the final observed bar remains open. Candidate rows are availability
    ticks, while candidate signal_time identifies the new observed bar boundary.
    """

    def __init__(self, zone_cache: ZoneCache, execution: ReplayConfig | None = None):
        self._per_tick_temp_state: Optional[pd.DataFrame] = None
        self._per_candle_temp_state: Optional[pd.DataFrame] = None
        self._zone_cache = zone_cache
        self.execution = execution

    @profile_it
    @pandera_validate
    def process_tick_data(
        self,
        tick_df: pt.DataFrame[VectorizedTick],
        candle_15min_df: pt.DataFrame[VectorizedCandleInput],
    ) -> pt.DataFrame[StrategyResult]:
        """Process supplied ticks using zones already held in memory."""
        if tick_df.empty:
            self._per_tick_temp_state = self._initialize_per_tick_temp_state(tick_df)
            self._per_candle_temp_state = pd.DataFrame()
            return self._public_result()

        processed_tick_days = []
        processed_candle_days = []
        for _, instrument_ticks in tick_df.groupby(level=["broker", "symbol"], sort=False):
            replay = ExecutionReplay(self.execution, repr(instrument_ticks.index[0][:2])) if self.execution else None
            if not instrument_ticks.index.get_level_values("precise_time").is_monotonic_increasing:
                raise ValueError("Ticks must be chronological within each broker/symbol")
            for day, day_tick_df in instrument_ticks.groupby("broker_day", sort=False):
                per_tick_state = self._process_day_boundaries(self._initialize_per_tick_temp_state(day_tick_df))
                per_tick_state = self._process_bar_boundaries(day_tick_df, per_tick_state, candle_15min_df)

                processed_candle_days.append(self._per_candle_temp_state)

                per_tick_state = self._process_tick_operations(day_tick_df, per_tick_state)
                # processed_tick_days.append(self._generate_actions(per_tick_state))
                if self.execution is not None:
                    zones = self._zone_cache.get_zones_for_day(day)
                    per_tick_state = generate_actions(day_tick_df, per_tick_state, zones, self.execution, replay)
                processed_tick_days.append(per_tick_state)
        self._per_candle_temp_state = pd.concat(processed_candle_days)
        self._per_tick_temp_state = pd.concat(processed_tick_days).sort_index(kind="stable")
        return self._public_result()

    def _public_result(self):
        columns = [
            "action",
            "breakout_signals",
            "reversal_signals",
            "pullback_signals",
            "pullback_windows_opened",
            "actions",
            "execution_events",
            "orders",
            "positions",
            "pullback_feedback",
            "attempted_bars",
            "entry_rejections",
            "daily_net_realized_pnl",
            "daily_gross_loss",
            "account_balance",
            "daily_loss_locked",
            "operational_locked",
            "execution_mode",
        ]
        return self._per_tick_temp_state[columns]  # .copy()

    @staticmethod
    @profile_it
    @pandera_validate
    def add_bar_time_n_broker_day(tick_df: pt.DataFrame[Tick]) -> pt.DataFrame[VectorizedTick]:
        datetime_index = tick_df.index.get_level_values("precise_time")

        tick_df["bar_time"] = compute_bar_time(datetime_index)
        tick_df["broker_day"] = datetime_index.normalize()

        return tick_df

    @profile_it
    @pandera_validate
    def _initialize_per_tick_temp_state(self, tick_df: pt.DataFrame[VectorizedTick]) -> pt.DataFrame[PerTickState]:
        """Initialize tick inputs, intermediate fields and output columns."""
        index = tick_df.index
        n = tick_df.shape[0]

        object_values = np.empty(n, dtype=object)
        empty_tuple = ()
        object_values.fill(empty_tuple)

        # Keep the exact intended output-column order.
        new_columns: dict[str, object] = {
            # # Derived time columns
            # "bar_time":  compute_bar_time(datetime_index),
            # "broker_day": datetime_index.normalize(), #, #datetime_index.strftime("%Y-%m-%d"),
            # Trend state columns
            "trend": XauTrend.NONE.value,
            "trend_count": 0,
            "trend_high_0": 0.0,
            "trend_high_1": 0.0,
            "trend_high_2": 0.0,
            "trend_low_0": 0.0,
            "trend_low_1": 0.0,
            "trend_low_2": 0.0,
            # Bar state columns
            "bar_open": 0.0,
            "bar_active": False,
            "day_active": False,
            # Zone engagement state
            "buy_engaged": False,
            "sell_engaged": False,
            # Signal generation state
            "breakout_sequence": 0,
            "reversal_keys": "",
            "attempted_bars": "",
            # Pullback window state
            "pullback_active": False,
            "pullback_bar_offset": 0,
            "pullback_penetration_latched": False,
            "pullback_sequence": 0,
            # Intermediate calculations
            "reference_high": 0.0,
            "reference_low": 0.0,
            "multi_zone_tick_gap": False,
            # Output
            "action": None,
            # Daily/account state
            "daily_net_realized_pnl": float("nan"),
            "daily_gross_loss": float("nan"),
            "account_balance": float("nan"),
            "daily_loss_locked": False,
            "operational_locked": False,
            "execution_mode": "replay" if self.execution else "signals_only",
            "reversal_signals": object_values,
            "pullback_signals": object_values,
            "actions": object_values,
            "execution_events": object_values,
            "orders": object_values,
            "positions": object_values,
            "pullback_feedback": object_values,
            "entry_rejections": object_values,
            "pullback_windows_opened": object_values,
            "breakout_signals": object_values,
        }

        initialized = pd.DataFrame(new_columns, index=index)
        return initialized  # pd.concat([per_tick_state, initialized])

    @profile_it
    @pandera_validate(allow_pandas_dataframe=True)
    def _process_day_boundaries(self, per_tick_state: pt.DataFrame[PerTickState]) -> pt.DataFrame[PerTickState]:
        # Each daily partition is initialized independently before processing.

        per_tick_state["day_active"] = True
        return per_tick_state

    @profile_it
    @pandera_validate(inplace=True)
    def _get_ticks_bar_ids(self, ticks: pt.DataFrame[VectorizedTick]) -> tuple[np.ndarray, np.ndarray]:
        day_changed = ticks["broker_day"].ne(ticks["broker_day"].shift())
        bar_changed = day_changed | ticks["bar_time"].ne(ticks["bar_time"].shift())
        bar_ids = bar_changed.cumsum().to_numpy() - 1

        return bar_ids, bar_changed

    @profile_it
    @pandera_validate(inplace=True)
    def _process_bar_boundaries(
        self,
        ticks: pt.DataFrame[VectorizedTick],
        per_tick_state: pt.DataFrame[PerTickState],
        candle_15min_df: pt.DataFrame[VectorizedCandleInput],
    ) -> pt.DataFrame[BarInfo]:
        """Use observed bars only; completed ranges enter history at the next bar."""
        if ticks.empty:
            return per_tick_state

        bar_ids, bar_changed = self._get_ticks_bar_ids(ticks)

        candles = candle_15min_df
        if "timeframe" in candles:
            candles = candles.loc[candles["timeframe"].eq("15min")]
        for key in ("broker", "symbol"):
            if key in candles and key in ticks.index.names:
                candles = candles.loc[candles[key].eq(ticks.index.get_level_values(key)[0])]
        if candles["bar_time"].duplicated().any():
            raise ValueError("M15 candles must be unique per broker/symbol/bar_time")

        per_candle_state = candles.set_index("bar_time")[["open", "high", "low"]].reindex(
            ticks.loc[bar_changed, "bar_time"]
        )
        if per_candle_state.isna().any().any():
            log_e("M15 candles must cover every observed tick bar")
            raise ValueError("M15 candles must cover every observed tick bar")
        per_candle_state["day"] = ticks.loc[bar_changed, "broker_day"].to_numpy()
        counts = per_candle_state.groupby("day", sort=False).cumcount().to_numpy()
        available = np.minimum(counts, 3)
        per_candle_state["trend_count"] = available
        per_tick_state["trend_count"] = available[bar_ids]

        # Gather only preceding bars. Unavailable bootstrap slots remain zero.
        slots = np.arange(3)
        positions = np.arange(len(per_candle_state))[:, None] - available[:, None] + slots
        valid = slots < available[:, None]

        # Pull high/low for valid slots, zero-pad missing
        high = np.where(valid, per_candle_state["high"].to_numpy()[positions.clip(0, len(per_candle_state) - 1)], 0.0)
        low = np.where(valid, per_candle_state["low"].to_numpy()[positions.clip(0, len(per_candle_state) - 1)], 0.0)
        # todo: parameterize number of extrema used for trend
        per_candle_state[["trend_high_0", "trend_high_1", "trend_high_2"]] = high
        per_candle_state[["trend_low_0", "trend_low_1", "trend_low_2"]] = low
        instrument_keys = [key for key in ("broker", "symbol") if key in per_tick_state.index.names]
        candle_keys = per_tick_state.loc[bar_changed].index.to_frame(index=False)[instrument_keys]
        candle_keys["bar_time"] = ticks.loc[bar_changed, "bar_time"].to_numpy()
        per_candle_state.index = pd.MultiIndex.from_frame(candle_keys)
        self._per_candle_temp_state = per_candle_state

        # Broadcast back to original tick rows via bar_ids
        per_tick_state[["trend_high_0", "trend_high_1", "trend_high_2"]] = high[bar_ids]
        per_tick_state[["trend_low_0", "trend_low_1", "trend_low_2"]] = low[bar_ids]
        per_tick_state["bar_open"] = per_candle_state["open"].to_numpy()[bar_ids]
        per_tick_state["bar_active"] = per_tick_state["day_active"]
        return per_tick_state

    # @pandera_validate()
    # def _generate_breakout_signals(
    #     self, per_tick_state: pt.DataFrame[PerTickBaseState], zones: List[XauZone]
    # ) -> pt.DataFrame[PerTickBaseState]:
    #     log_w(NOT_TESTED)
    #     return generate_breakout_signals(per_tick_state, zones)

    @profile_it
    @pandera_validate()
    def _process_tick_operations(
        self,
        ticks: pt.DataFrame[VectorizedTick],
        per_tick_state: pt.DataFrame[PerTickState],
    ) -> pt.DataFrame[PerTickState]:
        # zones = self._get_zones_for_group(per_tick_state)
        zones = self._zone_cache.get_zones_for_day(ticks["broker_day"].iloc[0])
        per_tick_state = update_trend(ticks, per_tick_state)
        per_tick_state = update_zone_engagement(ticks, per_tick_state, zones)
        # per_tick_state = self._generate_breakout_signals(per_tick_state, zones)
        per_tick_state = generate_breakout_signals(ticks, per_tick_state, zones)
        per_tick_state = generate_reversal_signals(ticks, per_tick_state, zones)
        if self.execution is None:
            per_tick_state = generate_pullback_signals(ticks, per_tick_state)

        return per_tick_state

    # @profile_it
    # @pandera_validate(allow_pandas_dataframe=True)
    # def _update_trend(self, per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PerTickBaseState]:
    #     # log_w(NOT_TESTED)
    #     return update_trend(ticks, per_tick_state)

    @profile_it
    @pandera_validate(allow_pandas_dataframe=True)
    def _get_zones_for_group(self, ticks: pt.DataFrame[ZoneDayInput]) -> List[XauZone]:
        log_w(NOT_TESTED)
        zones = self._zone_cache.get_zones_for_day(ticks["broker_day"].iloc[0])
        return zones

    # @profile_it
    # @pandera_validate(allow_pandas_dataframe=True)
    # def _generate_actions(self, per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PerTickBaseState]:
    #     log_w(NOT_TESTED)
    #     return generate_actions(per_tick_state)
