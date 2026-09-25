from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import XauDirection, XauSignalFamily


@dataclass(slots=True)
class XauZone:
    id: str
    low: float
    high: float
    priority: int = 0


@dataclass(slots=True)
class XauSignalCandidate:
    candidate_id: str = ""
    parent_breakout_id: str = ""
    bar_id: str = ""
    zone_id: str = ""
    family: XauSignalFamily = XauSignalFamily.BREAKOUT
    direction: XauDirection = XauDirection.BUY
    order_type: int = 0
    signal_time: datetime | None = None
    entry_price: float = 0.0
