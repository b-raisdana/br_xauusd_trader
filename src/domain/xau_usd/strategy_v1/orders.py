from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from numbers import Real
from typing import Literal

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.zones import StrategyZoneRows
from helper.importer import pt

from .config import StrategyV1Config
from .risk import stop_loss_distance_usd


@dataclass(frozen=True)
class OrderPrices:
    accepted: bool
    reason: str
    entry_reference: float
    stop_loss: float | None
    take_profit: float | None
    stop_loss_distance: float
    take_profit_distance_worst: float | None
    target_zone_id: str | None


@pandera_validate
def prepare_order_prices(
    zones: pt.DataFrame[StrategyZoneRows],
    signal_time: datetime,
    direction: Literal["buy", "sell"],
    entry_reference: float,
    signal_zone_lower: float,
    signal_zone_upper: float,
    config: StrategyV1Config,
) -> OrderPrices:
    if (
        signal_time.tzinfo is None
        or signal_time.utcoffset() is None
        or signal_time.utcoffset() != UTC.utcoffset(signal_time)
    ):
        raise ValueError("signal_time must be UTC-aware")
    values = (entry_reference, signal_zone_lower, signal_zone_upper)
    if any(not isinstance(value, Real) or not isfinite(value) for value in values):
        raise ValueError("entry reference and signal zone bounds must be numeric")
    if entry_reference <= 0.0 or signal_zone_lower <= 0.0 or signal_zone_upper < signal_zone_lower:
        raise ValueError("entry reference or signal zone bounds are invalid")

    sl_distance = stop_loss_distance_usd(signal_time, config)
    tolerance = config.entry_tolerance_pips * config.pip_size_usd
    worst_entry = entry_reference + tolerance if direction == "buy" else entry_reference - tolerance
    same_day = zones.index.get_level_values("date").date == signal_time.date()
    day_zones = zones.loc[same_day]
    if direction == "buy":
        targets = day_zones.loc[day_zones["lower"].gt(signal_zone_upper)].sort_values("lower")
        target_id = None if targets.empty else str(targets.index.get_level_values("zone_id")[0])
        take_profit = (
            entry_reference + config.fallback_tp_multiple * sl_distance
            if targets.empty
            else float(targets["lower"].iloc[0])
        )
        stop_loss = entry_reference - sl_distance
        tp_distance = take_profit - worst_entry
        passed = worst_entry >= take_profit
    else:
        targets = day_zones.loc[day_zones["upper"].lt(signal_zone_lower)].sort_values("upper", ascending=False)
        target_id = None if targets.empty else str(targets.index.get_level_values("zone_id")[0])
        take_profit = (
            entry_reference - config.fallback_tp_multiple * sl_distance
            if targets.empty
            else float(targets["upper"].iloc[0])
        )
        stop_loss = entry_reference + sl_distance
        tp_distance = worst_entry - take_profit
        passed = worst_entry <= take_profit

    if passed:
        return OrderPrices(
            False,
            "target_already_passed",
            entry_reference,
            stop_loss,
            take_profit,
            sl_distance,
            tp_distance,
            target_id,
        )
    if tp_distance <= sl_distance:
        return OrderPrices(
            False,
            "take_profit_distance_not_greater_than_stop",
            entry_reference,
            stop_loss,
            take_profit,
            sl_distance,
            tp_distance,
            target_id,
        )
    return OrderPrices(True, "accepted", entry_reference, stop_loss, take_profit, sl_distance, tp_distance, target_id)


def limit_price_is_ready(
    *,
    direction: Literal["buy", "sell"],
    bid: float,
    ask: float,
    entry_reference: float,
    config: StrategyV1Config,
) -> bool:
    values = (bid, ask, entry_reference)
    if any(not isinstance(value, Real) or not isfinite(value) for value in values):
        raise ValueError("bid, ask and entry reference must be numeric")
    if min(bid, ask, entry_reference) <= 0.0 or bid > ask:
        raise ValueError("bid/ask quote or entry reference is invalid")
    market_price = ask if direction == "buy" else bid
    tolerance = config.entry_tolerance_pips * config.pip_size_usd
    return entry_reference - tolerance <= market_price <= entry_reference + tolerance
