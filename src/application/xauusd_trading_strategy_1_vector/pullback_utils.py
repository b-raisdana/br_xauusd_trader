from __future__ import annotations

from application.xauusd_trading_strategy_1_vector.domain.schema import XauPullbackWindowState
from domain.xau_usd.enums import XauDirection
from domain.xau_usd.models import XauZone


def create_pullback_window(
    window: XauPullbackWindowState,
    parent_breakout_id: str,
    zone: XauZone,
    direction: XauDirection,
) -> bool:
    if not parent_breakout_id or not zone.id or zone.low > zone.high:
        return False

    window.parent_breakout_id = parent_breakout_id
    window.zone = zone
    window.direction = direction
    window.bar_offset = 0
    window.active = True
    window.penetration_latched = False
    window.pending_active = False
    window.sequence = 0
    return True
