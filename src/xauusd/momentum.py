"""Strict Pullback momentum, pre-zone trigger, conflict, and TP contracts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from xauusd.signals import TradeDirection
from xauusd.trend import Candle, CandleDirection
from xauusd.zones import Zone, price

PRE_ZONE_TRIGGER_DISTANCE_USD = Decimal("1.00")


def strict_pullback_trend(
    *,
    direction: TradeDirection,
    closed_after_pullback: Iterable[Candle],
    current_open: Decimal | str | int | float,
    current_bid: Decimal | str | int | float,
    current_ask: Decimal | str | int | float,
) -> bool:
    """Evaluate closed candles plus the current candle only at a decision point."""
    required = (
        CandleDirection.BULLISH if direction is TradeDirection.BUY else CandleDirection.BEARISH
    )
    if any(candle.direction is not required for candle in closed_after_pullback):
        return False
    open_price = price(current_open)
    if direction is TradeDirection.BUY:
        return price(current_bid) > open_price
    return price(current_ask) < open_price


def pre_zone_trigger_price(direction: TradeDirection, target_zone: Zone) -> Decimal:
    if direction is TradeDirection.BUY:
        return target_zone.low - PRE_ZONE_TRIGGER_DISTANCE_USD
    return target_zone.high + PRE_ZONE_TRIGGER_DISTANCE_USD


class PreZoneTriggerTracker:
    """Latch only the first directional crossing for each position and target Zone."""

    def __init__(self) -> None:
        self._triggered: set[tuple[str, str]] = set()

    def crossed(
        self,
        *,
        position_id: str,
        direction: TradeDirection,
        target_zone: Zone,
        previous_price: Decimal | str | int | float,
        current_price: Decimal | str | int | float,
    ) -> bool:
        key = (position_id, target_zone.zone_id)
        if key in self._triggered:
            return False
        previous = price(previous_price)
        current = price(current_price)
        trigger = pre_zone_trigger_price(direction, target_zone)
        crossed = (
            previous < trigger <= current
            if direction is TradeDirection.BUY
            else previous > trigger >= current
        )
        if crossed:
            self._triggered.add(key)
        return crossed


def blocks_opposite_reversal(*, actual_zone_touch: bool, strict_trend_valid: bool) -> bool:
    return actual_zone_touch and strict_trend_valid


class TpActionType(StrEnum):
    NONE = "none"
    MODIFY = "modify"
    RESTORE = "restore"
    MARKET_CLOSE = "market_close"


@dataclass(frozen=True, slots=True)
class TpAction:
    action: TpActionType
    requested_tp: Decimal | None = None
    target_zone_id: str | None = None
    reason: str | None = None


@dataclass(slots=True)
class PullbackTpState:
    position_id: str
    direction: TradeDirection
    initial_target_zone_id: str
    initial_tp: Decimal
    current_target_zone_id: str
    current_tp: Decimal
    extended: bool = False

    @classmethod
    def create(
        cls,
        *,
        position_id: str,
        direction: TradeDirection,
        initial_target_zone: Zone,
    ) -> PullbackTpState:
        target = (
            initial_target_zone.low if direction is TradeDirection.BUY else initial_target_zone.high
        )
        return cls(
            position_id=position_id,
            direction=direction,
            initial_target_zone_id=initial_target_zone.zone_id,
            initial_tp=target,
            current_target_zone_id=initial_target_zone.zone_id,
            current_tp=target,
        )

    def propose_extension(
        self,
        *,
        approached_zone: Zone,
        next_zone: Zone | None,
        strict_trend_valid: bool,
    ) -> TpAction:
        if (
            self.extended
            or not strict_trend_valid
            or approached_zone.zone_id != self.initial_target_zone_id
        ):
            return TpAction(TpActionType.NONE)
        if next_zone is None:
            return TpAction(TpActionType.NONE, reason="no_next_zone")
        requested = next_zone.low if self.direction is TradeDirection.BUY else next_zone.high
        return TpAction(TpActionType.MODIFY, requested, next_zone.zone_id)

    def record_extension_result(self, action: TpAction, *, broker_accepted: bool) -> None:
        if action.action is not TpActionType.MODIFY:
            raise ValueError("Action is not a TP modification")
        if broker_accepted:
            assert action.requested_tp is not None
            assert action.target_zone_id is not None
            self.current_tp = action.requested_tp
            self.current_target_zone_id = action.target_zone_id
            self.extended = True

    def evaluate_strict_failure(
        self,
        *,
        strict_trend_valid: bool,
        current_bid: Decimal | str | int | float,
        current_ask: Decimal | str | int | float,
    ) -> TpAction:
        if strict_trend_valid or not self.extended:
            return TpAction(TpActionType.NONE)
        initial_crossed = (
            price(current_bid) >= self.initial_tp
            if self.direction is TradeDirection.BUY
            else price(current_ask) <= self.initial_tp
        )
        if initial_crossed:
            return TpAction(TpActionType.MARKET_CLOSE, reason="strict_failed_after_initial_tp")
        return TpAction(
            TpActionType.RESTORE,
            requested_tp=self.initial_tp,
            target_zone_id=self.initial_target_zone_id,
            reason="strict_failed_before_initial_tp",
        )

    def record_restore_result(self, *, broker_accepted: bool) -> None:
        if broker_accepted:
            self.current_tp = self.initial_tp
            self.current_target_zone_id = self.initial_target_zone_id
            self.extended = False
