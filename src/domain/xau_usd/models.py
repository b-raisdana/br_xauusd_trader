from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.xau_usd.enums import (
    XauDirection,
    XauEntryRejection,
    XauExecutionEvent,
    XauExecutionStatus,
    XauOrderType,
    XauSignalFamily,
    XauTrend,
)


@dataclass(slots=True)
class XauZone:
    id: str = ""
    low: float = 0.0
    high: float = 0.0
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


@dataclass(slots=True)
class XauPullbackWindowState:
    parent_breakout_id: str = ""
    zone: XauZone = field(default_factory=XauZone)
    direction: XauDirection = XauDirection.BUY
    bar_offset: int = 0
    active: bool = False
    penetration_latched: bool = False
    pending_active: bool = False
    sequence: int = 0
    breakout_bar_time: datetime | None = None
    broker_day: str = ""
    order_ticket: str = ""
    waiting_logged: bool = False
    risk_waiting_logged: bool = False


@dataclass(slots=True)
class XauPreZoneTriggerState:
    position_id: str = ""
    target_zone_id: str = ""
    triggered: bool = False


@dataclass(slots=True)
class XauPullbackTpState:
    position_id: str = ""
    direction: XauDirection = XauDirection.BUY
    initial_target_zone_id: str = ""
    initial_tp: float = 0.0
    current_target_zone_id: str = ""
    current_tp: float = 0.0
    extended: bool = False


@dataclass(slots=True)
class XauOperationalSafety:
    locked: bool = False
    block_entries: bool = False
    cancel_pending: bool = False
    cancel_pullback_cycles: bool = False
    close_positions: bool = False


@dataclass(slots=True)
class XauExecutionProjection:
    request_id: str = ""
    status: XauExecutionStatus = XauExecutionStatus.SUBMITTED
    order_type: XauOrderType = XauOrderType.MARKET
    direction: XauDirection = XauDirection.BUY
    order_entry: float = 0.0
    fill_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    close_price: float = 0.0
    transition_time: datetime | None = None


@dataclass(slots=True)
class XauExecutionBinding:
    request_id: str = ""
    order_ticket: int = 0
    position_id: int = 0


@dataclass(slots=True)
class XauRuntimeRequest:
    request_id: str = ""
    candidate: XauSignalCandidate | None = None
    target_zone_id: str = ""
    trigger_state: XauPreZoneTriggerState = field(default_factory=XauPreZoneTriggerState)
    tp_state: XauPullbackTpState = field(default_factory=XauPullbackTpState)
    tp_initialized: bool = False


@dataclass(slots=True)
class XauOrderAuditEvent:
    event_id: str = ""
    request_id: str = ""
    zone_id: str = ""
    rule_ids: str = ""
    direction: XauDirection = XauDirection.BUY
    order_type: XauOrderType = XauOrderType.MARKET
    broker_time: datetime | None = None
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0


@dataclass(slots=True)
class XauNativeSymbol:
    digits: int = 0
    point: float = 0.0
    volume_min: float = 0.0
    volume_max: float = 0.0
    volume_step: float = 0.0


@dataclass(slots=True)
class XauNativeDealOutcome:
    deal_ticket: int = 0
    order_ticket: int = 0
    position_id: int = 0
    event_kind: XauExecutionEvent = XauExecutionEvent.REJECT
    price: float = 0.0
    broker_time: datetime | None = None


@dataclass(slots=True)
class XauTrendReferenceState:
    """Rolling extrema of the closed bars of the current day, oldest first."""

    trend: XauTrend = XauTrend.NONE
    count: int = 0
    highs: list[float] = field(default_factory=list)
    lows: list[float] = field(default_factory=list)


@dataclass(slots=True)
class XauDailyZoneSignalState:
    zone: XauZone = field(default_factory=XauZone)
    buy_engaged: bool = False
    sell_engaged: bool = False
    reversal_usage: int = 0
    pullback_fills: int = 0
    reversal_fill_count: int = 0
    last_reversal_buy_signal_bar: datetime | None = None
    last_reversal_sell_signal_bar: datetime | None = None


@dataclass(slots=True)
class XauMarketCoordinator:
    broker_day: str = ""
    bar_id: str = ""
    day_active: bool = False
    bar_active: bool = False
    bar_open: float = 0.0
    last_bid: float = 0.0
    last_ask: float = 0.0
    breakout_sequence: int = 0
    trend: XauTrendReferenceState = field(default_factory=XauTrendReferenceState)
    zones: list[XauDailyZoneSignalState] = field(default_factory=list)
    pullbacks: list[XauPullbackWindowState] = field(default_factory=list)
    reversal_keys: list[str] = field(default_factory=list)
    attempted_bars: list[str] = field(default_factory=list)


@dataclass(slots=True)
class XauPreparedEntry:
    candidate: XauSignalCandidate = field(default_factory=XauSignalCandidate)
    decision: XauEntryRejection = XauEntryRejection.ALLOWED
    volume_lots: float = 0.01
    stop_loss: float = 0.0
    take_profit: float = 0.0
    stop_zone_id: str = ""
    target_zone_id: str = ""


@dataclass(slots=True)
class XauTesterSubmission:
    attempted: bool = False
    accepted: bool = False
    order_ticket: int = 0
    deal_ticket: int = 0
    retcode: int = 0


@dataclass(slots=True)
class XauTesterRiskSnapshot:
    net_realized_pnl: float = 0.0
    realized_gross_loss: float = 0.0
    open_position_risk: float = 0.0
    pending_order_risk: float = 0.0
    free_margin: float = 0.0
    open_positions: int = 0
    pending_orders: int = 0


@dataclass(slots=True)
class XauVisualMarker:
    event_id: str = ""
    zone_id: str = ""
    label: str = ""
    broker_time: datetime | None = None
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    zone_priority: int = 0
