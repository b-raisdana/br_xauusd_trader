"""Projection of causal market-state outputs into the immutable audit stream."""

from __future__ import annotations

from datetime import date, datetime

from xauusd.audit import AuditEvent, AuditEventKind, AuditJournal, SignalFamily
from xauusd.market_state import MarketBarCloseUpdate, MarketTickUpdate


class MarketAuditProjector:
    """Deduplicate active-day signal outputs without changing strategy state."""

    def __init__(self, journal: AuditJournal) -> None:
        self.journal = journal
        self._broker_day: date | None = None
        self._seen: set[tuple[str, ...]] = set()

    def begin_day(self, broker_day: date) -> None:
        if broker_day != self._broker_day:
            self._broker_day = broker_day
            self._seen.clear()
        self.journal.begin_day(broker_day)

    def record_tick(
        self, update: MarketTickUpdate, *, broker_time: datetime
    ) -> tuple[AuditEvent, ...]:
        events: list[AuditEvent] = []
        for reversal in update.reversal_candidates:
            key: tuple[str, ...] = (
                "reversal",
                reversal.bar_id,
                reversal.zone_id,
                reversal.direction.value,
            )
            if key in self._seen:
                continue
            event = self.journal.record(
                rule_ids=("REVERSAL_DIRECTIONAL_TOUCH",),
                kind=AuditEventKind.SIGNAL,
                broker_time=broker_time,
                zone_id=reversal.zone_id,
                signal_family=SignalFamily.REVERSAL,
                direction=reversal.direction,
                entry=reversal.touch_price,
                order_type=reversal.order_type,
            )
            self._seen.add(key)
            events.append(event)

        for pullback in update.pullback_candidates:
            key = ("pullback", pullback.candidate_id)
            if key in self._seen:
                continue
            event = self.journal.record(
                rule_ids=("PULLBACK_CONSERVATIVE_ENTRY",),
                kind=AuditEventKind.SIGNAL,
                broker_time=broker_time,
                zone_id=pullback.zone_id,
                signal_family=SignalFamily.PULLBACK,
                direction=pullback.direction,
                entry=pullback.entry_price,
                order_type=pullback.order_type,
                parent_breakout_id=pullback.parent_breakout_id,
            )
            self._seen.add(key)
            events.append(event)
        return tuple(events)

    def record_bar_close(
        self, update: MarketBarCloseUpdate, *, broker_time: datetime
    ) -> tuple[AuditEvent, ...]:
        events: list[AuditEvent] = []
        for breakout in update.breakouts:
            key = ("breakout", breakout.breakout_id)
            if key in self._seen:
                continue
            event = self.journal.record(
                rule_ids=("BREAKOUT_VALIDATION", "ZONE_ENGAGEMENT"),
                kind=AuditEventKind.SIGNAL,
                broker_time=broker_time,
                zone_id=breakout.zone_id,
                signal_family=SignalFamily.BREAKOUT,
                direction=breakout.direction,
                entry=breakout.close,
            )
            self._seen.add(key)
            events.append(event)
        return tuple(events)
