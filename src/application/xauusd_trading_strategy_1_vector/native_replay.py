"""Recorded callbacks using the same market, entry, risk and protection transitions."""

from collections.abc import Sequence
from copy import deepcopy
from datetime import datetime
from sys import float_info

from domain.xau_usd.enums import XauDirection, XauExecutionStatus, XauSignalFamily
from domain.xau_usd.models import XauSignalCandidate

from .domain.native import EA_MAGIC, NativeCalculationFailure, NativeDeal, NativePosition, NativeView, RecordedEconomics
from .domain.replay import ReplayConfig, ReplayOrder
from .domain.robust import reversal_limit
from .domain.schema import ReplayReason
from .replay import ExecutionReplay


def parse_native_comment(comment: str) -> tuple[str, str, str, bool] | None:
    parts = comment.split("|")
    if len(parts) < 4 or len(parts[1]) != 8:
        return None
    day = parts[1]
    return parts[0], f"{day[:4]}-{day[4:6]}-{day[6:]}", parts[2], parts[3] == "B"


class RecordedExecutionReplay(ExecutionReplay):
    """Accepted sends never imply deals; callers deliver each recorded callback explicitly."""

    def __init__(self, config: ReplayConfig, stream_id: str) -> None:
        if not isinstance(config.economics, RecordedEconomics):
            raise TypeError("Recorded replay requires RecordedEconomics")
        super().__init__(config, stream_id)
        self.native = config.economics
        self.risk_state_error = False
        self.update_view(self.native.view)

    def update_view(self, view: NativeView) -> None:
        self.native.view = view
        self.balance = view.balance
        pending = {o.ticket for o in view.pending if o.magic == EA_MAGIC}
        for request in self.requests:
            if request.status != XauExecutionStatus.REJECTED:
                request.status = (
                    XauExecutionStatus.SUBMITTED
                    if request.native_order_ticket in pending
                    else XauExecutionStatus.CANCELLED
                )
        for track in self.orders.values():
            if track.native_position_id is not None:
                track.costs = -self._history_total(track.native_position_id, costs_only=True)

    def _history_total(self, position_id: int, costs_only: bool = False) -> float:
        return sum(
            d.commission + d.swap + d.fee + (0.0 if costs_only else d.profit)
            for d in self.native.view.history
            if d.position_id == position_id and d.magic == EA_MAGIC
        )

    def _native_position(self, identifier: int | None) -> NativePosition | None:
        return next((p for p in self.native.view.positions if p.identifier == identifier and p.magic == EA_MAGIC), None)

    def _session_positions(self) -> list[ReplayOrder]:
        result = []
        for position in reversed(self.native.view.positions):
            if position.magic != EA_MAGIC:
                continue
            track = self._track(position.identifier)
            if track is None:
                parsed = parse_native_comment(position.comment)
                kind, day, zone, buy = parsed if parsed else ("", "", "", False)
                candidate = XauSignalCandidate(zone_id=zone, direction=XauDirection.BUY if buy else XauDirection.SELL)
                track = ReplayOrder(
                    f"UNTRACKED-{position.ticket}",
                    candidate,
                    position.volume,
                    position.sl,
                    position.tp,
                    "",
                    position.opened,
                    status=XauExecutionStatus.FILLED,
                    fill_price=position.entry,
                    fill_time=position.opened,
                    request_active=False,
                    broker_day=day,
                    native_position_id=position.identifier,
                    native_position_ticket=position.ticket,
                    native_trade_type=kind,
                )
            track.fill_time = position.opened
            result.append(track)
        return result

    def _session_pending(self) -> list[ReplayOrder]:
        result = []
        for pending in reversed(self.native.view.pending):
            if pending.magic != EA_MAGIC:
                continue
            request = next((r for r in self.requests if r.native_order_ticket == pending.ticket), None)
            if request is None:
                request = ReplayOrder(
                    f"UNTRACKED-ORDER-{pending.ticket}",
                    XauSignalCandidate(),
                    pending.volume,
                    pending.sl,
                    0,
                    "",
                    self.bar or datetime.min,
                    native_order_ticket=pending.ticket,
                )
            result.append(request)
        return result

    def _track(self, identifier: int) -> ReplayOrder | None:
        return next(
            (
                o
                for o in self.orders.values()
                if o.native_position_id == identifier and o.status == XauExecutionStatus.FILLED
            ),
            None,
        )

    def _selected_position(self, order: ReplayOrder) -> NativePosition | None:
        if order.native_position_ticket:
            return next((p for p in self.native.view.positions if p.ticket == order.native_position_ticket), None)
        return self._native_position(order.native_position_id)

    def _position_available(self, order: ReplayOrder) -> bool:
        position = self._selected_position(order)
        if position is None:
            return False
        order.stop_loss = position.sl
        return True

    def _cost_offset(self, order: ReplayOrder) -> float:
        if order.costs <= 0:
            return 0.0
        try:
            return super()._cost_offset(order)
        except NativeCalculationFailure:
            return 0.0

    def _manage(self, time: datetime, bid: float, ask: float, breakouts: Sequence[XauSignalCandidate]) -> None:
        super()._manage(time, bid, ask, breakouts)
        self.balance = self.native.view.balance
        for track in self.orders.values():
            if track.native_position_id is not None:
                self._position_available(track)

    def _new_cash_risk(self, direction: XauDirection, volume: float, entry: float, sl: float) -> float:
        return float_info.max if self.risk_state_error else self._cash_risk(direction, volume, entry, sl)

    def _fill(self, order: ReplayOrder, time: datetime, bid: float, ask: float) -> None:
        pass  # The source updates tracked fills only in DEAL_ADD callbacks.

    def _settle(self, time: datetime, bid: float, ask: float) -> None:
        self.update_view(self.native.view)

    def detect_restart(self, time: datetime, has_ea_deal_today: bool, bid: float, ask: float) -> None:
        exposed = any(p.magic == EA_MAGIC for p in self.native.view.positions) or any(
            p.magic == EA_MAGIC for p in self.native.view.pending
        )
        if not exposed and self.config.inputs.allow_same_day_fresh_start:
            return
        if exposed or has_ea_deal_today:
            self.restart_locked = True
            self._restart(time, bid, ask)

    def _restart(self, time: datetime, bid: float, ask: float) -> bool:
        if not self.restart_locked:
            return False
        for order in self._session_pending():
            self._cancel(order, time, "SESSION_OR_RESTART")
        for position in self._session_positions():
            self._close(position, time, bid, ask, "SESSION_OR_RESTART")
        return True

    def _send(self, order: ReplayOrder, time: datetime, bid: float, ask: float, is_pb: bool) -> bool:
        accepted = self.native.execute(
            "SUBMIT",
            order.comment,
            time,
            price=order.candidate.entry_price,
            sl=order.stop_loss,
            tp=order.take_profit,
            volume=order.volume,
        )
        result = self.native.last_operation
        if result is None:
            raise RuntimeError("Recorded submission did not consume an outcome")
        order.native_order_ticket = result.order_ticket
        self.balance = self.native.view.balance
        return accepted

    def _accept_modification(self, order: ReplayOrder, time: datetime) -> bool:
        position = self._selected_position(order)
        if position is None:
            return False
        return self.native.execute("MODIFY", str(position.ticket), time, sl=order.desired_sl, tp=position.tp)

    def _close(self, order: ReplayOrder, time: datetime, bid: float, ask: float, reason: ReplayReason) -> bool:
        position = self._native_position(order.native_position_id)
        ticket = order.native_position_ticket or (position.ticket if position else 0)
        accepted = self.native.accepts("CLOSE", str(ticket), time)
        self.balance = self.native.view.balance
        if not accepted:
            order.session_close_requested = False
            self._event(order, "CLOSE_REJECT", time, reason)
        return accepted

    def _cancel(self, order: ReplayOrder, time: datetime, reason: ReplayReason) -> None:
        accepted = self.native.accepts("CANCEL", str(order.native_order_ticket), time)
        if accepted:
            order.status = XauExecutionStatus.CANCELLED
            self._feedback(order)
        self.balance = self.native.view.balance
        self._event(order, "CANCEL" if accepted else "CANCEL_REJECT", time, reason)

    def _cash_risk(self, direction: XauDirection, volume: float, entry: float, sl: float) -> float:
        if volume <= 0 or entry <= 0 or sl <= 0:
            self.risk_state_error = True
            return float_info.max
        try:
            return max(0.0, -self.native.profit(direction, volume, entry, sl))
        except NativeCalculationFailure:
            self.risk_state_error = True
            return float_info.max

    def _live_positions_count(self, bid: float, ask: float) -> int:
        return sum(p.magic == EA_MAGIC for p in self.native.view.positions)

    def _risk(self, bid: float, ask: float) -> tuple[float, float, int, float]:
        self.risk_state_error = False
        opened = pending = 0.0
        positions = [p for p in self.native.view.positions if p.magic == EA_MAGIC]
        for position in positions:
            track = next(
                (
                    o
                    for o in self.orders.values()
                    if o.status == XauExecutionStatus.FILLED and o.native_position_ticket == position.ticket
                ),
                None,
            )
            sl = position.sl if position.sl > 0 else (track.initial_sl if track else 0.0)
            value = self._cash_risk(
                XauDirection.BUY if position.buy else XauDirection.SELL, position.volume, position.entry, sl
            )
            if value == float_info.max:
                opened = value
                break
            opened += value
        for order in self.native.view.pending:
            if order.magic == EA_MAGIC:
                value = self._cash_risk(
                    XauDirection.BUY if order.buy else XauDirection.SELL, order.volume, order.entry, order.sl
                )
                if value == float_info.max:
                    pending = value
                    break
                pending += value
        return opened, pending, len(positions), self.native.view.free_margin

    def on_deal(self, deal: NativeDeal, view: NativeView, bid: float, ask: float) -> None:
        self._begin_tick(bid, ask)
        self.update_view(view)
        if not deal.deal_add or not deal.ticket or not deal.history_selected or deal.magic != EA_MAGIC:
            return
        if not any(d.ticket == deal.ticket for d in view.history):
            raise ValueError("Selected deal is missing from the recorded history snapshot")
        if deal.entry in ("IN", "INOUT"):
            parsed = parse_native_comment(deal.comment or (deal.order_comment if deal.order_ticket else ""))
            if parsed is not None:
                self._entry_deal(deal, parsed, bid, ask)
        if deal.entry in ("OUT", "OUT_BY", "INOUT"):
            track = self._track(deal.position_id)
            if track is not None:
                self._exit_deal(track, deal, bid, ask)

    def _entry_deal(self, deal: NativeDeal, parsed: tuple[str, str, str, bool], bid: float, ask: float) -> None:
        kind, day, zone_id, buy = parsed
        comment = deal.comment or deal.order_comment
        request = next((r for r in reversed(self.requests) if r.request_active and r.comment == comment), None)
        if request is not None:
            request.request_active = False
        track = self._track(deal.position_id)
        if track is None:
            family = {"R": XauSignalFamily.REVERSAL, "B": XauSignalFamily.BREAKOUT}.get(kind, XauSignalFamily.PULLBACK)
            candidate = deepcopy(request.candidate) if request else XauSignalCandidate()
            candidate.family, candidate.zone_id = family, zone_id
            candidate.direction = XauDirection.BUY if buy else XauDirection.SELL
            position = self._native_position(deal.position_id)
            track = ReplayOrder(
                f"NATIVE-POS-{deal.position_id}-{len(self.orders)}",
                candidate,
                self.config.inputs.volume,
                request.initial_sl if request else 0.0,
                request.take_profit if request else 0.0,
                request.target_zone_id if request else "",
                deal.time,
                status=XauExecutionStatus.FILLED,
                fill_price=deal.price,
                fill_time=deal.time,
                request_active=False,
                broker_day=day,
                initial_sl=request.initial_sl if request else 0.0,
                r0=request.r0 if request else 0.0,
                reversal_ordinal=request.reversal_ordinal if request else 0,
                native_position_id=deal.position_id,
                native_position_ticket=position.ticket if position else 0,
                native_trade_type=kind,
                costs=-self._history_total(deal.position_id, costs_only=True),
            )
            track.stacked_pullback = kind == "P" and any(
                o.status == XauExecutionStatus.FILLED
                and o.native_trade_type == "P"
                and o.broker_day == day
                and o.candidate.zone_id == zone_id
                and o.direction == track.direction
                for o in self.orders.values()
            )
            self.orders[track.request_id] = track
            zone = (
                next((z for z in self.state.zones if z.zone.id == zone_id), None)
                if day == self.state.broker_day
                else None
            )
            if kind == "R" and zone is not None:
                zone.reversal_fill_count += 1
                zone.reversal_usage = 1
            if kind == "P":
                self._feedback(track, filled=True)
        self._event(track, "FILL", deal.time)
        if sum(p.magic == EA_MAGIC for p in self.native.view.positions) > self.config.inputs.max_positions:
            self._close(track, deal.time, bid, ask, "POSITION_CAP")
        if self._risk_used(bid, ask) > self._budget() + 0.05 and not self.risk_state_error:
            self._close(track, deal.time, bid, ask, "PORTFOLIO_RISK")

    def _enforce_pending_risk(self, time: datetime, bid: float, ask: float) -> None:
        if self.config.inputs.risk_mode == "off":
            return
        for window in reversed(self.state.pullbacks):
            used = self._risk_used(bid, ask)
            if self.risk_state_error or used <= self._budget() + 0.01:
                break
            if not window.active or not window.order_ticket:
                continue
            request = self.orders.get(window.order_ticket)
            if request is not None and any(p.ticket == request.native_order_ticket for p in self.native.view.pending):
                self._cancel(request, time, "PORTFOLIO_RISK")
                if request.status == XauExecutionStatus.SUBMITTED:
                    continue
            window.order_ticket = ""
            window.pending_active = window.waiting_logged = window.risk_waiting_logged = False

    def _exit_deal(self, track: ReplayOrder, deal: NativeDeal, bid: float, ask: float) -> None:
        net = self._history_total(deal.position_id)
        self.net_realized += net
        self.gross_loss += max(0.0, -net)
        if track.native_trade_type == "R" and track.broker_day == self.state.broker_day:
            zone = next((z for z in self.state.zones if z.zone.id == track.candidate.zone_id), None)
            if zone is not None:
                zone.reversal_usage = (
                    2 if zone.reversal_fill_count >= reversal_limit(zone.zone, self.config.inputs) else 0
                )
        track.status = XauExecutionStatus.CLOSED
        track.close_price, track.close_time, track.realized_pnl = deal.price, deal.time, net
        self._event(track, "CLOSE", deal.time)
        self._daily_guard(deal.time)
        self._enforce_pending_risk(deal.time, bid, ask)
