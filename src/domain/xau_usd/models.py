from __future__ import annotations

from dataclasses import dataclass


@dataclass
class XauOperationalSafety:
    locked: bool = False
    block_entries: bool = False
    cancel_pending: bool = False
    cancel_pullback_cycles: bool = False
    close_positions: bool = False


@dataclass
class XauZone:
    id: str
    low: float
    high: float
    priority: int  # 0=Normal, 1=High
