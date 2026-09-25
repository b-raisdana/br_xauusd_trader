from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
from br_py_log_n_profile import log_e, profile_it
from br_py_log_n_profile.do_log.log_it import NOT_TESTED, log_w

from application.xauusd_trading_strategy_1_vector.domain.schema import (
    BarInput,
    BarResult,
    PerTickBaseState,
    StrategyResult,
    VectorizedCandleInput,
    VectorizedTickInput,
    ZoneDayInput,
)
from domain.xau_usd.enums import XauTrend
from domain.xau_usd.models import XauZone
from helper.importer import pt
from helper.pandera import pandera_validate

from .actions import generate_actions
from .domain.replay import ReplayConfig
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
        tick_data: pt.DataFrame[VectorizedTickInput],
        candle_15min_df: pt.DataFrame[VectorizedCandleInput],
    ) -> pt.DataFrame[StrategyResult]:
        """Process supplied ticks using zones already held in memory."""
        self._per_tick_temp_state = self._initialize_per_tick_temp_state(tick_data)
        self._per_candle_temp_state = self._initialize_per_candle_temp_state(candle_15min_df)
        if tick_data.empty:
            return self._public_result()
        processed_tick_days = []
        processed_candle_days = []
        for _, the_broker_instrument_per_tick_temp_state in self._per_tick_temp_state.groupby(
            level=["broker", "symbol"], sort=False
        ):
            replay = (
                ExecutionReplay(self.execution, repr(the_broker_instrument_per_tick_temp_state.index[0][:2]))
                if self.execution
                else None
            )
            if not the_broker_instrument_per_tick_temp_state.index.get_level_values("datetime").is_monotonic_increasing:
                raise ValueError("Ticks must be chronological within each broker/symbol")
            for _, day_tick_state in the_broker_instrument_per_tick_temp_state.groupby("broker_day", sort=False):
                per_tick_state = self._process_day_boundaries(day_tick_state.copy())
                per_tick_state = self._process_bar_boundaries(per_tick_state, candle_15min_df)
                processed_candle_days.append(self._per_candle_temp_state)
                per_tick_state = self._process_tick_operations(per_tick_state)
                # processed_tick_days.append(self._generate_actions(per_tick_state))
                if self.execution is not None:
                    zones = self._zone_cache.get_zones_for_day(per_tick_state["broker_day"].iloc[0])
                    per_tick_state = generate_actions(per_tick_state, zones, self.execution, replay)
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
        return self._per_tick_temp_state[columns].copy()

    @profile_it
    @pandera_validate
    def _initialize_per_candle_temp_state(
        self, candle_df: pt.DataFrame[VectorizedCandleInput]
    ) -> pt.DataFrame[VectorizedCandleInput]:
        return candle_df.copy()

    @profile_it
    @pandera_validate(allow_pandas_dataframe=True)
    def _initialize_per_tick_temp_state(
        self, tick_df: pt.DataFrame[VectorizedTickInput]
    ) -> pt.DataFrame[PerTickBaseState]:
        """Initialize tick inputs, intermediate fields and output columns."""
        per_tick_state = tick_df.copy()

        # Derived time columns
        per_tick_state["bar_time"] = compute_bar_time(per_tick_state.index.get_level_values("datetime"))
        per_tick_state["broker_day"] = per_tick_state.index.get_level_values("datetime").strftime("%Y-%m-%d")

        # Trend state columns
        per_tick_state["trend"] = XauTrend.NONE.value
        per_tick_state["trend_count"] = 0
        per_tick_state["trend_high_0"] = 0.0
        per_tick_state["trend_high_1"] = 0.0
        per_tick_state["trend_high_2"] = 0.0
        per_tick_state["trend_low_0"] = 0.0
        per_tick_state["trend_low_1"] = 0.0
        per_tick_state["trend_low_2"] = 0.0

        # Bar state columns
        per_tick_state["bar_open"] = 0.0
        per_tick_state["bar_active"] = False
        per_tick_state["day_active"] = False

        # Zone engagement state - flattened per zone
        # We'll dynamically add zone-specific columns based on actual zones
        per_tick_state["buy_engaged"] = False
        per_tick_state["sell_engaged"] = False

        # Signal generation state
        per_tick_state["breakout_sequence"] = 0
        per_tick_state["reversal_keys"] = ""
        per_tick_state["attempted_bars"] = ""

        # Pullback window state - flattened per window
        per_tick_state["pullback_active"] = False
        per_tick_state["pullback_bar_offset"] = 0
        per_tick_state["pullback_penetration_latched"] = False
        per_tick_state["pullback_sequence"] = 0

        # Intermediate calculations
        per_tick_state["reference_high"] = 0.0
        per_tick_state["reference_low"] = 0.0
        per_tick_state["multi_zone_tick_gap"] = False

        # Output columns
        per_tick_state["action"] = None
        for column in (
            "reversal_signals",
            "pullback_signals",
            "actions",
            "execution_events",
            "orders",
            "positions",
            "pullback_feedback",
            "entry_rejections",
        ):
            per_tick_state[column] = pd.Series([()] * len(per_tick_state), index=per_tick_state.index, dtype=object)
        for column in ("daily_net_realized_pnl", "daily_gross_loss", "account_balance"):
            per_tick_state[column] = float("nan")
        per_tick_state["daily_loss_locked"] = False
        per_tick_state["operational_locked"] = False
        per_tick_state["execution_mode"] = "replay" if self.execution else "signals_only"
        per_tick_state["breakout_signals"] = pd.Series(
            [()] * len(per_tick_state), index=per_tick_state.index, dtype=object
        )
        per_tick_state["pullback_windows_opened"] = pd.Series(
            [()] * len(per_tick_state), index=per_tick_state.index, dtype=object
        )

        return per_tick_state

    @profile_it
    @pandera_validate(allow_pandas_dataframe=True)
    def _process_day_boundaries(self, per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PerTickBaseState]:
        # Each daily partition is initialized independently before processing.

        per_tick_state["day_active"] = True
        return per_tick_state

    @profile_it
    @pandera_validate(inplace=True)
    def _get_ticks_bar_ids(self, per_tick_state: pt.DataFrame[BarInput]) -> tuple[np.ndarray, np.ndarray]:
        day_changed = per_tick_state["broker_day"].ne(per_tick_state["broker_day"].shift())
        bar_changed = day_changed | per_tick_state["bar_time"].ne(per_tick_state["bar_time"].shift())
        bar_ids = bar_changed.cumsum().to_numpy() - 1

        return bar_ids, bar_changed

    @profile_it
    @pandera_validate(inplace=True)
    def _process_bar_boundaries(
        self,
        per_tick_state: pt.DataFrame[BarInput],
        candle_15min_df: pt.DataFrame[VectorizedCandleInput],
    ) -> pt.DataFrame[BarResult]:
        """Use observed bars only; completed ranges enter history at the next bar."""
        if per_tick_state.empty:
            return per_tick_state

        bar_ids, bar_changed = self._get_ticks_bar_ids(per_tick_state)

        candles = candle_15min_df
        if "timeframe" in candles:
            candles = candles.loc[candles["timeframe"].eq("15min")]
        for key in ("broker", "symbol"):
            if key in candles and key in per_tick_state.index.names:
                candles = candles.loc[candles[key].eq(per_tick_state.index.get_level_values(key)[0])]
        if candles["bar_time"].duplicated().any():
            raise ValueError("M15 candles must be unique per broker/symbol/bar_time")

        per_candle_state = candles.set_index("bar_time")[["open", "high", "low"]].reindex(
            per_tick_state.loc[bar_changed, "bar_time"]
        )
        if per_candle_state.isna().any().any():
            log_e("M15 candles must cover every observed tick bar")
            raise ValueError("M15 candles must cover every observed tick bar")
        per_candle_state["day"] = per_tick_state.loc[bar_changed, "broker_day"].to_numpy()
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

        per_candle_state[["trend_high_0", "trend_high_1", "trend_high_2"]] = high
        per_candle_state[["trend_low_0", "trend_low_1", "trend_low_2"]] = low
        instrument_keys = [key for key in ("broker", "symbol") if key in per_tick_state.index.names]
        candle_keys = per_tick_state.loc[bar_changed].index.to_frame(index=False)[instrument_keys]
        candle_keys["bar_time"] = per_tick_state.loc[bar_changed, "bar_time"].to_numpy()
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
        per_tick_state: pt.DataFrame[PerTickBaseState],
    ) -> pt.DataFrame[PerTickBaseState]:
        # zones = self._get_zones_for_group(per_tick_state)
        zones = self._zone_cache.get_zones_for_day(per_tick_state["broker_day"].iloc[0])
        per_tick_state = update_trend(per_tick_state)
        per_tick_state = update_zone_engagement(per_tick_state, zones)
        # per_tick_state = self._generate_breakout_signals(per_tick_state, zones)
        per_tick_state = generate_breakout_signals(per_tick_state, zones)
        per_tick_state = generate_reversal_signals(per_tick_state, zones)
        if self.execution is None:
            per_tick_state = generate_pullback_signals(per_tick_state)

        return per_tick_state

    # @profile_it
    # @pandera_validate(allow_pandas_dataframe=True)
    # def _update_trend(self, per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PerTickBaseState]:
    #     # log_w(NOT_TESTED)
    #     return update_trend(per_tick_state)

    @profile_it
    @pandera_validate(allow_pandas_dataframe=True)
    def _get_zones_for_group(self, per_tick_state: pt.DataFrame[ZoneDayInput]) -> List[XauZone]:
        log_w(NOT_TESTED)
        zones = self._zone_cache.get_zones_for_day(per_tick_state["broker_day"].iloc[0])
        return zones

    # @profile_it
    # @pandera_validate(allow_pandas_dataframe=True)
    # def _generate_actions(self, per_tick_state: pt.DataFrame[PerTickBaseState]) -> pt.DataFrame[PerTickBaseState]:
    #     log_w(NOT_TESTED)
    #     return generate_actions(per_tick_state)
