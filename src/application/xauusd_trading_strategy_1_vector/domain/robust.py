from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from sys import float_info
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from domain.xau_usd.enums import XauDirection
from domain.xau_usd.models import XauDailyZoneSignalState, XauZone


class RobustInputs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    r_cap: float = Field(default=6.0, gt=0)
    target_r_multiplier: float = Field(default=1.0, gt=0)
    volume: float = Field(default=0.01, gt=0)
    explicit_controls: bool = True
    enable_reversal: bool = True
    enable_pullback: bool = True
    enable_direct_breakout: bool = False
    breakout_normal_only: bool = True
    reversal_high_only: bool = False
    normal_pullback: bool = True
    high_pullback: bool = True
    pullback_min_space: float = Field(default=12, ge=0)
    high_reversal_min_space: float = Field(default=12, ge=0)
    normal_pullback_max: int = Field(default=2, ge=0)
    high_pullback_max: int = Field(default=10, ge=0)
    high_reversal_max: int = Field(default=2, ge=1)
    high_reversal_sl_multiplier: float = Field(default=1.5, gt=0)
    breakout_buffer: float = Field(default=1, ge=0)
    penetration: float = Field(default=0.2, ge=0)
    window_bars: int = Field(default=5, ge=1, le=10)
    profit_protection: bool = True
    one_order_per_candle: bool = False
    session_safety_telemetry: bool = True
    session_mode: Literal["carry", "pullback", "all"] = "all"
    preclose_minutes: float = Field(default=5, ge=0)
    max_positions: int = Field(default=3, ge=1)
    risk_mode: Literal["off", "net", "gross"] = "gross"
    risk_percent: float = Field(default=30, gt=0, lt=100)
    daily_loss_override: bool = False
    daily_loss_percent: float = Field(default=20, gt=0)
    qa_discovery: bool = False
    qa_capital: float = Field(default=200, gt=0)
    allow_same_day_fresh_start: bool = False
    legacy_profile: int = Field(default=4, ge=0, le=4)
    digits: int = Field(default=2, ge=0, le=8)
    broker_timezone: str = "UTC"


def normalize_price(value: float, digits: int) -> float:
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def free_space(zones: Sequence[XauZone], index: int, buy: bool) -> float:
    if not 0 <= index < len(zones):
        return 0.0
    adjacent = index + (1 if buy else -1)
    if not 0 <= adjacent < len(zones):
        return float_info.max
    return max(0.0, zones[adjacent].low - zones[index].high if buy else zones[index].low - zones[adjacent].high)


def reversal_limit(zone: XauZone, inputs: RobustInputs) -> int:
    if inputs.explicit_controls:
        return inputs.high_reversal_max if zone.priority == 1 else int(not inputs.reversal_high_only)
    if inputs.legacy_profile:
        if zone.priority != 1 or inputs.legacy_profile == 1:
            return 0
        return 1 if inputs.legacy_profile == 2 else 2
    return inputs.high_reversal_max if zone.priority == 1 else 1


def pullback_allowed(zones: Sequence[XauZone], state: XauDailyZoneSignalState, buy: bool, inputs: RobustInputs) -> bool:
    index = next((i for i, zone in enumerate(zones) if zone.id == state.zone.id), -1)
    if index < 0:
        return False
    high = state.zone.priority == 1
    if inputs.explicit_controls:
        if not inputs.enable_pullback or not (inputs.high_pullback if high else inputs.normal_pullback):
            return False
        limit = inputs.high_pullback_max if high else inputs.normal_pullback_max
        if (not high or limit > 0) and state.pullback_fills >= limit:
            return False
        return free_space(zones, index, buy) >= inputs.pullback_min_space
    return not inputs.legacy_profile or ((high or state.pullback_fills < 1) and free_space(zones, index, buy) >= 15)


def reversal_allowed(zones: Sequence[XauZone], index: int, buy: bool, inputs: RobustInputs) -> bool:
    if not 0 <= index < len(zones):
        return False
    high = zones[index].priority == 1
    if inputs.explicit_controls:
        return (
            inputs.enable_reversal
            and (high or not inputs.reversal_high_only)
            and (not high or free_space(zones, index, buy) >= inputs.high_reversal_min_space)
        )
    return not inputs.legacy_profile or (
        inputs.legacy_profile != 1 and high and (inputs.legacy_profile != 4 or free_space(zones, index, buy) >= 15)
    )


def protection(
    zones: Sequence[XauZone],
    index: int,
    direction: XauDirection,
    entry: float,
    high_reversal: bool,
    inputs: RobustInputs,
) -> tuple[float, float, float, str] | None:
    buy = direction == XauDirection.BUY
    stop_index = index - 1 if buy else index + 1
    if not 0 <= index < len(zones) or not 0 <= stop_index < len(zones):
        return None
    stop = (
        max(zones[stop_index].high, entry - inputs.r_cap) if buy else min(zones[stop_index].low, entry + inputs.r_cap)
    )
    risk = entry - stop if buy else stop - entry
    if risk <= 0:
        return None
    if high_reversal:
        risk *= inputs.high_reversal_sl_multiplier
        stop = entry - risk if buy else entry + risk
    targets = range(index + 1, len(zones)) if buy else range(index - 1, -1, -1)
    for target_index in targets:
        target = zones[target_index].low if buy else zones[target_index].high
        distance = target - entry if buy else entry - target
        if distance >= inputs.target_r_multiplier * risk and target > 0:
            stop = normalize_price(stop, inputs.digits)
            return stop, normalize_price(target, inputs.digits), abs(entry - stop), zones[target_index].id
    return None
