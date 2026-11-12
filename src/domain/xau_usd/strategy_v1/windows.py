from datetime import UTC, datetime, timedelta
from typing import Literal

from .config import StrategyV1Config


def reversal_expires_at(entry_tick_time: datetime, config: StrategyV1Config) -> datetime:
    _require_utc(entry_tick_time)
    candle_minutes = config.m5_timeframe_minutes
    candle_open = entry_tick_time.replace(
        minute=entry_tick_time.minute - entry_tick_time.minute % candle_minutes,
        second=0,
        microsecond=0,
    )
    return candle_open + timedelta(minutes=config.confirmation_window_m5 * candle_minutes)


def pullback_return_expires_at(breakout_close_time: datetime, config: StrategyV1Config) -> datetime:
    _require_utc(breakout_close_time)
    return breakout_close_time + timedelta(
        minutes=(config.breakout_return_window_m5 + 1) * config.m5_timeframe_minutes,
    )


def pullback_confirmation_expires_at(return_tick_time: datetime, config: StrategyV1Config) -> datetime:
    return reversal_expires_at(return_tick_time, config)


def confirmation_is_in_window(confirmation_time: datetime, expires_at: datetime) -> bool:
    _require_utc(confirmation_time)
    _require_utc(expires_at)
    return confirmation_time < expires_at


def resolve_reversal_confirmation(
    *,
    exit_valid: bool,
    macd_confirmed: bool,
    confirmation_time: datetime,
    expires_at: datetime,
) -> Literal["exit", "confirmed", "pending", "expired"]:
    _require_utc(confirmation_time)
    _require_utc(expires_at)
    if exit_valid:
        return "exit"
    if macd_confirmed and confirmation_is_in_window(confirmation_time, expires_at):
        return "confirmed"
    if confirmation_time >= expires_at:
        return "expired"
    return "pending"


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("timestamp must be UTC-aware")
