"""Deterministic causal replay over normalized Broker-Day bars and ticks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from xauusd.audit import AuditEvent, AuditJournal, SignalFamily
from xauusd.execution import ExecutionLedger, ExecutionRequest, ExecutionStatus
from xauusd.market_state import MarketState
from xauusd.orchestration import MarketAuditProjector
from xauusd.pullback import PullbackExpiry, PullbackOrderCandidate
from xauusd.risk import build_initial_risk
from xauusd.signals import ReversalCandidate
from xauusd.trend import Candle
from xauusd.zones import Zone, price


@dataclass(frozen=True, slots=True)
class ReplayExecutionOutcome:
    candidate_id: str
    broker_time: datetime
    accepted: bool
    fill_price: Decimal | None = None
    rejection_reason: str | None = None

    @classmethod
    def from_values(
        cls,
        *,
        candidate_id: str,
        broker_time: datetime,
        accepted: bool,
        fill_price: Decimal | str | int | float | None = None,
        rejection_reason: str | None = None,
    ) -> ReplayExecutionOutcome:
        if not candidate_id.strip():
            raise ValueError("Replay outcome Candidate ID is required")
        if accepted and rejection_reason is not None:
            raise ValueError("Accepted replay outcome cannot have a rejection reason")
        if not accepted and (fill_price is not None or not rejection_reason):
            raise ValueError("Rejected replay outcome requires only a rejection reason")
        return cls(
            candidate_id=candidate_id,
            broker_time=broker_time,
            accepted=accepted,
            fill_price=price(fill_price) if fill_price is not None else None,
            rejection_reason=rejection_reason,
        )


@dataclass(frozen=True, slots=True)
class ReplayCloseOutcome:
    request_id: str
    broker_time: datetime
    close_price: Decimal
    rule_ids: tuple[str, ...]
    reason: str

    @classmethod
    def from_values(
        cls,
        *,
        request_id: str,
        broker_time: datetime,
        close_price: Decimal | str | int | float,
        rule_ids: tuple[str, ...],
        reason: str,
    ) -> ReplayCloseOutcome:
        if not request_id.strip():
            raise ValueError("Replay Close Request ID is required")
        if not rule_ids or any(not rule_id.strip() for rule_id in rule_ids):
            raise ValueError("Replay Close Rule IDs are required")
        if not reason.strip():
            raise ValueError("Replay Close reason is required")
        return cls(request_id, broker_time, price(close_price), rule_ids, reason)


@dataclass(frozen=True, slots=True)
class ReplayModifyOutcome:
    request_id: str
    broker_time: datetime
    accepted: bool
    rule_ids: tuple[str, ...]
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    rejection_reason: str | None = None

    @classmethod
    def from_values(
        cls,
        *,
        request_id: str,
        broker_time: datetime,
        accepted: bool,
        rule_ids: tuple[str, ...],
        stop_loss: Decimal | str | int | float | None = None,
        take_profit: Decimal | str | int | float | None = None,
        rejection_reason: str | None = None,
    ) -> ReplayModifyOutcome:
        if not request_id.strip() or not rule_ids:
            raise ValueError("Replay Modify requires Request ID and Rule IDs")
        if stop_loss is None and take_profit is None:
            raise ValueError("Replay Modify requires SL or TP")
        if accepted == (rejection_reason is not None):
            raise ValueError("Replay Modify rejection reason does not match acceptance")
        return cls(
            request_id,
            broker_time,
            accepted,
            rule_ids,
            price(stop_loss) if stop_loss is not None else None,
            price(take_profit) if take_profit is not None else None,
            rejection_reason,
        )


@dataclass(frozen=True, slots=True)
class ReplayCancelOutcome:
    request_id: str
    broker_time: datetime
    accepted: bool
    rule_ids: tuple[str, ...]
    reason: str

    @classmethod
    def from_values(
        cls,
        *,
        request_id: str,
        broker_time: datetime,
        accepted: bool,
        rule_ids: tuple[str, ...],
        reason: str,
    ) -> ReplayCancelOutcome:
        if not request_id.strip() or not rule_ids:
            raise ValueError("Replay Cancel requires Request ID and Rule IDs")
        if not reason.strip():
            raise ValueError("Replay Cancel reason is required")
        return cls(request_id, broker_time, accepted, rule_ids, reason)


@dataclass(frozen=True, slots=True)
class ReplayTick:
    broker_time: datetime
    bid: Decimal
    execution_outcomes: tuple[ReplayExecutionOutcome, ...] = ()
    close_outcomes: tuple[ReplayCloseOutcome, ...] = ()
    modify_outcomes: tuple[ReplayModifyOutcome, ...] = ()
    cancel_outcomes: tuple[ReplayCancelOutcome, ...] = ()

    @classmethod
    def from_values(
        cls,
        *,
        broker_time: datetime,
        bid: Decimal | str | int | float,
        execution_outcomes: tuple[ReplayExecutionOutcome, ...] = (),
        close_outcomes: tuple[ReplayCloseOutcome, ...] = (),
        modify_outcomes: tuple[ReplayModifyOutcome, ...] = (),
        cancel_outcomes: tuple[ReplayCancelOutcome, ...] = (),
    ) -> ReplayTick:
        return cls(
            broker_time=broker_time,
            bid=price(bid),
            execution_outcomes=execution_outcomes,
            close_outcomes=close_outcomes,
            modify_outcomes=modify_outcomes,
            cancel_outcomes=cancel_outcomes,
        )


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
        self.execution = ExecutionLedger(journal)
        self._pending_candidates: dict[str, PullbackOrderCandidate] = {}

    def run_day(self, replay: ReplayDay) -> ReplayResult:
        self._validate_day(replay)
        event_start = len(self.journal.events)
        expiries = list(self.state.begin_day(replay.broker_day, replay.zones))
        self.projector.begin_day(replay.broker_day)
        self.execution.begin_day(replay.broker_day)
        self._pending_candidates.clear()
        for candle in replay.seed_candles:
            self.state.record_closed_candle(candle)

        for bar in replay.bars:
            expiries.extend(self.state.begin_bar(bar.open_bid, bar_id=bar.bar_id))
            previous_bid = bar.open_bid
            for tick in bar.ticks:
                update = self.state.process_tick(previous_bid=previous_bid, bid=tick.bid)
                matched = self._match_outcomes(
                    update.reversal_candidates, update.pullback_candidates, tick
                )
                self._validate_lifecycle_outcomes(tick)
                self.projector.record_tick(update, broker_time=tick.broker_time)
                for candidate, outcome in matched:
                    self._apply_outcome(candidate, outcome, replay.zones, tick.broker_time)
                for close_outcome in tick.close_outcomes:
                    self.execution.close(
                        close_outcome.request_id,
                        broker_time=close_outcome.broker_time,
                        close_price=close_outcome.close_price,
                        rule_ids=close_outcome.rule_ids,
                        reason=close_outcome.reason,
                    )
                for modify in tick.modify_outcomes:
                    self.execution.modify(
                        modify.request_id,
                        broker_time=modify.broker_time,
                        broker_accepted=modify.accepted,
                        stop_loss=modify.stop_loss,
                        take_profit=modify.take_profit,
                        rule_ids=modify.rule_ids,
                        rejection_reason=modify.rejection_reason,
                    )
                for cancel in tick.cancel_outcomes:
                    self.execution.cancel_pending(
                        cancel.request_id,
                        broker_time=cancel.broker_time,
                        broker_accepted=cancel.accepted,
                        rule_ids=cancel.rule_ids,
                        reason=cancel.reason,
                    )
                    if cancel.accepted:
                        candidate = self._pending_candidates.pop(cancel.request_id)
                        if not self.state.pullbacks.record_pending_removed(candidate):
                            raise RuntimeError("Cancelled Pending could not update signal state")
                previous_bid = tick.bid
            close = self.state.close_bar(bar.candle)
            self.projector.record_bar_close(close, broker_time=bar.close_time)

        return ReplayResult(
            events=self.journal.events[event_start:], pullback_expiries=tuple(expiries)
        )

    def _match_outcomes(
        self,
        reversals: tuple[ReversalCandidate, ...],
        pullbacks: tuple[PullbackOrderCandidate, ...],
        tick: ReplayTick,
    ) -> tuple[tuple[ReversalCandidate | PullbackOrderCandidate, ReplayExecutionOutcome], ...]:
        candidates: dict[str, ReversalCandidate | PullbackOrderCandidate] = {}
        for reversal in reversals:
            candidates[reversal.candidate_id] = reversal
        for pullback in pullbacks:
            candidates[pullback.candidate_id] = pullback
        outcome_ids = [outcome.candidate_id for outcome in tick.execution_outcomes]
        if len(outcome_ids) != len(set(outcome_ids)):
            raise ValueError("Replay Tick contains duplicate execution outcomes")
        unknown = set(outcome_ids) - set(candidates)
        if unknown:
            raise ValueError(f"Replay outcome has no candidate on this Tick: {sorted(unknown)[0]}")
        return tuple(
            (candidates[outcome.candidate_id], outcome) for outcome in tick.execution_outcomes
        )

    def _validate_lifecycle_outcomes(self, tick: ReplayTick) -> None:
        outcomes: tuple[ReplayCloseOutcome | ReplayModifyOutcome | ReplayCancelOutcome, ...] = (
            *tick.close_outcomes,
            *tick.modify_outcomes,
            *tick.cancel_outcomes,
        )
        request_ids = [outcome.request_id for outcome in outcomes]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("Replay Tick contains duplicate lifecycle outcomes")
        for outcome in outcomes:
            if outcome.broker_time < tick.broker_time:
                raise ValueError("Replay lifecycle outcome precedes Tick")
            record = self.execution.record(outcome.request_id)
            if isinstance(outcome, (ReplayCloseOutcome, ReplayModifyOutcome)) and (
                record.status is not ExecutionStatus.FILLED
            ):
                raise ValueError(f"Replay Close has no open filled position: {outcome.request_id}")
            if isinstance(outcome, ReplayCancelOutcome):
                if (
                    record.status is not ExecutionStatus.SUBMITTED
                    or outcome.request_id not in self._pending_candidates
                ):
                    raise ValueError(
                        f"Replay Cancel has no active Pending order: {outcome.request_id}"
                    )

    def _apply_outcome(
        self,
        candidate: ReversalCandidate | PullbackOrderCandidate,
        outcome: ReplayExecutionOutcome,
        zones: tuple[Zone, ...],
        signal_time: datetime,
    ) -> None:
        entry = (
            candidate.touch_price
            if isinstance(candidate, ReversalCandidate)
            else candidate.entry_price
        )
        initial = build_initial_risk(direction=candidate.direction, entry=entry, zones=zones)
        if initial is None:
            raise ValueError(
                f"Replay execution Candidate has no valid initial risk: {candidate.candidate_id}"
            )
        if outcome.broker_time < signal_time:
            raise ValueError("Replay execution outcome precedes Signal")
        if (
            isinstance(candidate, ReversalCandidate)
            and outcome.accepted
            and outcome.fill_price is None
        ):
            raise ValueError("Accepted Market replay outcome requires a fill price")
        if isinstance(candidate, ReversalCandidate):
            attempt = self.state.reversals.record_market_order_attempt(
                candidate, broker_accepted=outcome.accepted
            )
            rule_ids = ("REVERSAL_DIRECTIONAL_TOUCH",)
            parent = None
        else:
            attempt = self.state.pullbacks.record_pending_order_attempt(
                candidate, broker_accepted=outcome.accepted
            )
            rule_ids = ("PULLBACK_CONSERVATIVE_ENTRY",)
            parent = candidate.parent_breakout_id
        if not attempt.sent:
            raise ValueError(f"Replay execution attempt was blocked: {attempt.rejection_reason}")

        request = ExecutionRequest.from_values(
            request_id=candidate.candidate_id,
            broker_time=signal_time,
            zone_id=candidate.zone_id,
            signal_family=(
                SignalFamily.REVERSAL
                if isinstance(candidate, ReversalCandidate)
                else SignalFamily.PULLBACK
            ),
            direction=candidate.direction,
            order_type=candidate.order_type,
            entry=initial.entry,
            stop_loss=initial.stop_loss,
            take_profit=initial.take_profit,
            rule_ids=rule_ids,
            parent_breakout_id=parent,
        )
        self.execution.submit(request)
        if not outcome.accepted:
            assert outcome.rejection_reason is not None
            self.execution.reject(
                request.request_id,
                broker_time=outcome.broker_time,
                reason=outcome.rejection_reason,
            )
        elif outcome.fill_price is not None:
            self.execution.fill(
                request.request_id,
                broker_time=outcome.broker_time,
                fill_price=outcome.fill_price,
            )
            if isinstance(candidate, PullbackOrderCandidate):
                if not self.state.pullbacks.record_fill(candidate):
                    raise RuntimeError("Accepted Pullback fill could not update signal state")
        elif isinstance(candidate, PullbackOrderCandidate):
            self._pending_candidates[request.request_id] = candidate

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
                outcomes: tuple[
                    ReplayExecutionOutcome
                    | ReplayCloseOutcome
                    | ReplayModifyOutcome
                    | ReplayCancelOutcome,
                    ...,
                ] = (
                    *tick.execution_outcomes,
                    *tick.close_outcomes,
                    *tick.modify_outcomes,
                    *tick.cancel_outcomes,
                )
                if any(
                    outcome.broker_time < tick.broker_time or outcome.broker_time > bar.close_time
                    for outcome in outcomes
                ):
                    raise ValueError("Replay outcome must follow its Tick inside the bar")
                last_time = tick.broker_time
            final_bid = bar.ticks[-1].bid if bar.ticks else bar.open_bid
            if final_bid != bar.candle.close:
                raise ValueError("Replay final Bid does not match Candle Close")
