"""Deterministic causal replay over normalized Broker-Day bars and ticks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from xauusd.audit import AuditEvent, AuditJournal
from xauusd.market_state import MarketState
from xauusd.orchestration import MarketAuditProjector
from xauusd.pullback import PullbackExpiry
from xauusd.trend import Candle
from xauusd.zones import Zone, price


@dataclass(frozen=True, slots=True)
class ReplayTick:
    broker_time: datetime
    bid: Decimal

    @classmethod
    def from_values(cls, *, broker_time: datetime, bid: Decimal | str | int | float) -> ReplayTick:
        return cls(broker_time=broker_time, bid=price(bid))


@dataclass(frozen=True, slots=True)
class ReplayBar:
    bar_id: str
    open_time: datetime
    close_time: datetime
    open_bid: Decimal
    candle: Candle
    ticks: tuple[ReplayTick, ...]

    @classmethod
    def from_values(
        cls,
        *,
        bar_id: str,
        open_time: datetime,
        close_time: datetime,
        open_bid: Decimal | str | int | float,
        candle: Candle,
        ticks: tuple[ReplayTick, ...],
    ) -> ReplayBar:
        return cls(bar_id, open_time, close_time, price(open_bid), candle, ticks)


@dataclass(frozen=True, slots=True)
class ReplayDay:
    broker_day: date
    zones: tuple[Zone, ...]
    seed_candles: tuple[Candle, ...]
    bars: tuple[ReplayBar, ...]


@dataclass(frozen=True, slots=True)
class ReplayResult:
    events: tuple[AuditEvent, ...]
    pullback_expiries: tuple[PullbackExpiry, ...]


def build_replay_days(
    bars: Iterable[ReplayBar],
    zones_by_day: Mapping[date, tuple[Zone, ...]],
    *,
    seed_candles_by_day: Mapping[date, tuple[Candle, ...]] | None = None,
) -> tuple[ReplayDay, ...]:
    """Attach normalized bars to required daily Zone inputs without inventing days."""
    grouped: dict[date, list[ReplayBar]] = defaultdict(list)
    for bar in bars:
        broker_day = bar.candle.broker_day
        if bar.open_time.date() != broker_day or bar.close_time.date() != broker_day:
            raise ValueError("Replay bar time and Candle must share one Broker Day")
        grouped[broker_day].append(bar)

    seeds = seed_candles_by_day or {}
    missing = sorted(set(grouped) - set(zones_by_day))
    if missing:
        rendered = ", ".join(day.isoformat() for day in missing)
        raise ValueError(f"Missing daily Zone input for Broker Day: {rendered}")

    return tuple(
        ReplayDay(
            broker_day=broker_day,
            zones=zones_by_day[broker_day],
            seed_candles=seeds.get(broker_day, ()),
            bars=tuple(sorted(grouped[broker_day], key=lambda bar: bar.open_time)),
        )
        for broker_day in sorted(grouped)
    )


class ReplayRunner:
    def __init__(self, state: MarketState, journal: AuditJournal) -> None:
        self.state = state
        self.journal = journal
        self.projector = MarketAuditProjector(journal)

    def run_day(self, replay: ReplayDay) -> ReplayResult:
        self._validate_day(replay)
        event_start = len(self.journal.events)
        expiries = list(self.state.begin_day(replay.broker_day, replay.zones))
        self.projector.begin_day(replay.broker_day)
        for candle in replay.seed_candles:
            self.state.record_closed_candle(candle)

        for bar in replay.bars:
            expiries.extend(self.state.begin_bar(bar.open_bid, bar_id=bar.bar_id))
            previous_bid = bar.open_bid
            for tick in bar.ticks:
                update = self.state.process_tick(previous_bid=previous_bid, bid=tick.bid)
                self.projector.record_tick(update, broker_time=tick.broker_time)
                previous_bid = tick.bid
            close = self.state.close_bar(bar.candle)
            self.projector.record_bar_close(close, broker_time=bar.close_time)

        return ReplayResult(
            events=self.journal.events[event_start:], pullback_expiries=tuple(expiries)
        )

    @staticmethod
    def _validate_day(replay: ReplayDay) -> None:
        if any(zone.broker_day != replay.broker_day for zone in replay.zones):
            raise ValueError("Replay Zone belongs to a different Broker Day")
        if any(candle.broker_day != replay.broker_day for candle in replay.seed_candles):
            raise ValueError("Seed candle belongs to a different Broker Day")
        previous_close: datetime | None = None
        seen_bar_ids: set[str] = set()
        for bar in replay.bars:
            if not bar.bar_id.strip():
                raise ValueError("Replay Bar ID is required")
            if bar.bar_id in seen_bar_ids:
                raise ValueError("Replay Bar IDs must be unique within a Broker Day")
            seen_bar_ids.add(bar.bar_id)
            if bar.candle.broker_day != replay.broker_day:
                raise ValueError("Replay bar belongs to a different Broker Day")
            if (
                bar.open_time.date() != replay.broker_day
                or bar.close_time.date() != replay.broker_day
            ):
                raise ValueError("Replay bar time belongs to a different Broker Day")
            if bar.close_time <= bar.open_time:
                raise ValueError("Replay bar close must follow its open")
            if bar.open_bid != bar.candle.open:
                raise ValueError("Replay open Bid does not match Candle Open")
            if previous_close is not None and bar.open_time < previous_close:
                raise ValueError("Replay bars overlap or are out of order")
            previous_close = bar.close_time
            last_time = bar.open_time
            for tick in bar.ticks:
                if tick.broker_time < last_time or tick.broker_time > bar.close_time:
                    raise ValueError("Replay ticks must be chronological and inside the bar")
                if not bar.candle.low <= tick.bid <= bar.candle.high:
                    raise ValueError("Replay tick Bid is outside Candle range")
                last_time = tick.broker_time
            final_bid = bar.ticks[-1].bid if bar.ticks else bar.open_bid
            if final_bid != bar.candle.close:
                raise ValueError("Replay final Bid does not match Candle Close")
