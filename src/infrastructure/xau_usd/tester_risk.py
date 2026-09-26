from __future__ import annotations

from datetime import datetime
from typing import Protocol

from archive_not_used_trash.xauusd_trading_strategy_1 import XauTesterRiskSnapshot

from domain.xau_usd.enums import XauDirection


class TesterRiskPort(Protocol):
    def realized_risk(
        self, magic: int, symbol: str, day_start: datetime, broker_now: datetime
    ) -> tuple[float, float] | None: ...
    def exposure_risk(self, magic: int, symbol: str) -> tuple[float, float, int, int] | None: ...
    def free_margin(self) -> float | None: ...
    def position_risk_free(
        self,
        symbol: str,
        magic: int,
        position_id: int,
        direction: XauDirection,
        entry: float,
        volume: float,
        broker_now: datetime,
    ) -> float | None: ...


def load_tester_risk_snapshot(
    enabled: bool,
    is_tester: bool,
    magic: int,
    symbol: str,
    day_start: datetime,
    broker_now: datetime,
    port: TesterRiskPort,
) -> XauTesterRiskSnapshot | None:
    if not enabled or not is_tester or magic <= 0 or not symbol or day_start is None or broker_now < day_start:
        return None

    realized = port.realized_risk(magic, symbol, day_start, broker_now)
    exposure = port.exposure_risk(magic, symbol)
    free_margin = port.free_margin()
    if realized is None or exposure is None or free_margin is None or free_margin < 0.0:
        return None

    net_realized, gross_loss = realized
    open_risk, pending_risk, open_positions, pending_orders = exposure
    return XauTesterRiskSnapshot(
        net_realized_pnl=net_realized,
        realized_gross_loss=gross_loss,
        open_position_risk=open_risk,
        pending_order_risk=pending_risk,
        free_margin=free_margin,
        open_positions=open_positions,
        pending_orders=pending_orders,
    )


def tester_position_risk_free(
    direction: XauDirection,
    entry: float,
    volume: float,
    native_cost: float,
    cash_per_unit: float,
) -> float | None:
    if entry <= 0.0 or volume <= 0.0 or abs(cash_per_unit) <= 0.0:
        return None
    offset = max(native_cost, 0.0) / abs(cash_per_unit)
    return entry + offset if direction == XauDirection.BUY else entry - offset
