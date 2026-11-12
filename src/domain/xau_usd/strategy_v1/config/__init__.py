from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrategyV1Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    m5_timeframe_minutes: Literal[5] = 5
    m15_timeframe_minutes: Literal[15] = 15
    trend_reference_candles: Literal[3] = 3
    minimum_closed_m15_candles: int = Field(default=3, ge=3)
    rsi_period: int = Field(default=14, gt=0)
    rsi_buy_max: float = Field(default=30.0, ge=0.0, le=100.0)
    rsi_sell_min: float = Field(default=70.0, ge=0.0, le=100.0)
    zero_lag_macd_fast_period: int = Field(default=12, gt=0)
    zero_lag_macd_slow_period: int = Field(default=26, gt=0)
    zero_lag_macd_signal_period: int = Field(default=9, gt=0)
    zero_lag_macd_buy_signal_max: float = -2.0
    zero_lag_macd_sell_signal_min: float = 2.0
    zero_lag_macd_buy_histogram_min: float = -0.5
    zero_lag_macd_sell_histogram_max: float = 0.5
    breakout_lookback_m15: int = Field(default=5, gt=0)
    breakout_buffer_usd: float = Field(default=1.0, ge=0.0)
    breakout_return_window_m5: int = Field(default=5, gt=0)
    confirmation_window_m5: int = Field(default=5, gt=0)
    rsi_confirmation_candles: int = Field(default=3, gt=0)
    reversal_exit_buffer_usd: float = Field(default=1.0, ge=0.0)
    high_importance_threshold: float = Field(default=0.7, gt=0.0, le=1.0)
    fallback_importance_threshold: float = Field(default=0.5, gt=0.0, le=1.0)
    entry_tolerance_pips: int = Field(default=10, gt=0)
    pip_size_usd: float = Field(default=0.01, gt=0.0)
    opo_worst_commission_per_lot_per_side_usd: float = Field(default=6.0, ge=0.0)
    opo_xauusd_average_spread_points: float = Field(default=20.0, ge=0.0)
    opo_worst_negative_swap_points: float = Field(default=50.544, ge=0.0)
    cost_stress_slippage_points_per_execution: float = Field(default=20.0, ge=0.0)
    cost_stress_triple_swap_multiplier: int = Field(default=3, ge=1)
    london_session_start_hour: int = Field(default=8, ge=0, le=23)
    london_session_end_hour: int = Field(default=17, ge=1, le=24)
    new_york_session_start_hour: int = Field(default=8, ge=0, le=23)
    new_york_session_end_hour: int = Field(default=17, ge=1, le=24)
    sl_distance_usd_outside_session_overlap: float = Field(default=6.0, gt=0.0)
    sl_distance_usd_inside_session_overlap: float = Field(default=10.0, gt=0.0)
    fallback_tp_multiple: float = Field(default=5.0, gt=0.0)
    max_position_duration_minutes: int = Field(default=360, gt=0)
    market_close_entry_cutoff_seconds: int = Field(default=10, gt=0)

    @model_validator(mode="after")
    def validate_thresholds(self) -> StrategyV1Config:
        if self.rsi_buy_max >= self.rsi_sell_min:
            raise ValueError("RSI buy threshold must be below sell threshold")
        if self.zero_lag_macd_fast_period >= self.zero_lag_macd_slow_period:
            raise ValueError("fast MACD period must be below slow period")
        if self.high_importance_threshold < self.fallback_importance_threshold:
            raise ValueError("high importance threshold must not be below fallback threshold")
        if self.london_session_start_hour >= self.london_session_end_hour:
            raise ValueError("London session start must be before end")
        if self.new_york_session_start_hour >= self.new_york_session_end_hour:
            raise ValueError("New York session start must be before end")
        return self
