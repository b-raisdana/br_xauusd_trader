from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from datetime import datetime, timedelta
from math import isfinite
from zoneinfo import ZoneInfo

import pandas as pd
from br_py_log_n_profile import profile_it

from application.xauusd_trading_strategy_1_vector.domain.replay import ReplayConfig, ReplayEconomics, ReplayOrder
from application.xauusd_trading_strategy_1_vector.domain.schema import (
    CandidateSnapshot,
    OrderSnapshot,
    PositionSnapshot,
    PullbackFeedback,
    ReplayAction,
    ReplayEvent,
    ReplayEventKind,
    ReplayReason,
    ReplaySnapshot,
)
from domain.xau_usd.enums import (
    XauDirection,
    XauEntryRejection,
    XauExecutionStatus,
    XauOrderType,
    XauSignalFamily,
)
from domain.xau_usd.models import (
    XauDailyZoneSignalState,
    XauMarketCoordinator,
    XauPullbackWindowState,
    XauSignalCandidate,
    XauZone,
)

from .domain.robust import normalize_price, protection, pullback_allowed, reversal_allowed, reversal_limit


class ExecutionReplay:
    """Causal execution state for one broker/symbol; no terminal I/O."""

    @profile_it
    def __init__(self, config: ReplayConfig, stream_id: str) -> None:
        self.config: ReplayConfig = config
        self.economics: ReplayEconomics = config.economics
        self.stream_id: str = stream_id
        self.state: XauMarketCoordinator = XauMarketCoordinator()
        self.orders: dict[str, ReplayOrder] = {}
        self.requests: list[ReplayOrder] = []
        self.sequence: int = 0
        self.balance: float = config.initial_balance
        self.net_realized: float = 0.0
        self.gross_loss: float = 0.0
        self.daily_locked: bool = False
        self.operational_locked: bool = False
        self.bar: datetime | None = None
        self.previous_bid: float = 0.0
        self.previous_ask: float = 0.0
        self.bar_open: float = 0.0
        self.session_cutoff_key: str = ""
        self.session_active_window_key: str = ""
        self.session_active_from: datetime | None = None
        self.session_active_to: datetime | None = None
        self.restart_locked = False
        self.session_preclose = False
        self.daily_would_trigger_logged = False
        self.closed_bars: list[tuple[float, float, float, float]] = []
        self.events: list[ReplayEvent] = []
        self.feedback: list[PullbackFeedback] = []
        self.actions: list[ReplayAction] = []
        self.rejections: list[tuple[str, int]] = []

    @profile_it
    def _event(self, order: ReplayOrder, kind: ReplayEventKind, time: datetime, reason: ReplayReason = "") -> None:
        snapshot: OrderSnapshot = self.order_snapshot(order)
        self.events.append(
            {
                "request_id": order.request_id,
                "event": kind,
                "time": time,
                "reason": reason,
                **snapshot,
            }
        )

    @profile_it
    def order_snapshot(self, order: ReplayOrder) -> OrderSnapshot:
        return {
            "order_id": order.request_id,
            "order_type": int(order.candidate.order_type),
            "order_direction": int(order.direction),
            "order_status": int(order.status),
            "entry_price": order.candidate.entry_price,
            "stop_loss": order.stop_loss,
            "take_profit": order.take_profit,
            "order_time": order.submitted_time,
            "fill_price": order.fill_price,
            "close_price": order.close_price,
            "candidate_id": order.candidate.candidate_id,
            "parent_breakout_id": order.candidate.parent_breakout_id,
        }

    @profile_it
    def position_snapshot(self, order: ReplayOrder, bid: float, ask: float) -> PositionSnapshot:
        price = order.close_price if order.status == XauExecutionStatus.CLOSED else order.mark(bid, ask)
        pnl = (
            0.0
            if order.status == XauExecutionStatus.CLOSED
            else self.economics.profit(order.direction, order.volume, order.fill_price, price) - order.costs
        )
        return {
            "position_id": order.position_id,
            "position_direction": int(order.direction),
            "position_size": order.volume,
            "position_entry_price": order.fill_price,
            "position_current_price": price,
            "position_unrealized_pnl": pnl,
            "position_realized_pnl": order.realized_pnl,
            "position_status": int(order.status),
            "position_time": order.fill_time,
            "position_close_time": order.close_time,
            "stop_loss": order.stop_loss,
            "take_profit": order.take_profit,
        }

    @profile_it
    def _window(self, order: ReplayOrder) -> XauPullbackWindowState | None:
        return next(
            (
                w
                for w in self.state.pullbacks
                if w.active
                and w.broker_day == order.broker_day
                and w.zone.id == order.candidate.zone_id
                and w.direction == order.direction
            ),
            None,
        )

    def _feedback(self, order: ReplayOrder, filled: bool = False) -> None:
        if order.candidate.family != XauSignalFamily.PULLBACK:
            return
        zone = next((z for z in self.state.zones if z.zone.id == order.candidate.zone_id), None)
        window = self._window(order)
        if filled:
            if zone is not None and order.broker_day == self.state.broker_day:
                zone.pullback_fills += 1
            if window is not None:
                window.active = False
                window.pending_active = False
                window.order_ticket = ""
        elif window is not None:
            window.pending_active = order.status == XauExecutionStatus.SUBMITTED
            if window.pending_active:
                window.order_ticket = order.request_id
        self.feedback.append(
            PullbackFeedback(
                order.candidate.zone_id,
                order.direction,
                zone.pullback_fills if zone else 0,
                bool(window and window.pending_active),
                filled,
            )
        )

    def _fill(self, order: ReplayOrder, time: datetime, bid: float, ask: float) -> None:
        order.request_active = False
        order.stacked_pullback = order.candidate.family == XauSignalFamily.PULLBACK and any(
            other is not order
            and other.status == XauExecutionStatus.FILLED
            and other.candidate.family == XauSignalFamily.PULLBACK
            and other.broker_day == order.broker_day
            and other.candidate.zone_id == order.candidate.zone_id
            and other.direction == order.direction
            for other in self.orders.values()
        )
        order.status = XauExecutionStatus.FILLED
        order.fill_price = ask if order.direction == XauDirection.BUY else bid
        order.fill_time = time
        order.costs = self.economics.cost(order.volume, time, True)
        self.balance -= order.costs
        self._feedback(order, filled=True)
        zone = next((z for z in self.state.zones if z.zone.id == order.candidate.zone_id), None)
        if (
            order.candidate.family == XauSignalFamily.REVERSAL
            and zone is not None
            and order.broker_day == self.state.broker_day
        ):
            zone.reversal_fill_count += 1
            zone.reversal_usage = 1
        self._event(order, "FILL", time)
        if self._risk(bid, ask)[2] > self.config.inputs.max_positions:
            self._close(order, time, bid, ask, "POSITION_CAP")
        if order.status == XauExecutionStatus.FILLED and self._risk_used(bid, ask) > self._budget() + 0.05:
            self._close(order, time, bid, ask, "PORTFOLIO_RISK")

    def _close(self, order: ReplayOrder, time: datetime, bid: float, ask: float, reason: ReplayReason) -> bool:
        if not self.economics.accepts("CLOSE", order.request_id, time):
            order.session_close_requested = False
            self._event(order, "CLOSE_REJECT", time, reason)
            return False
        order.status = XauExecutionStatus.CLOSED
        order.close_price = order.mark(bid, ask)
        order.close_time = time
        gross = self.economics.profit(order.direction, order.volume, order.fill_price, order.close_price)
        exit_cost = self.economics.cost(order.volume, time, False)
        self.balance += gross - exit_cost
        order.costs += exit_cost
        order.realized_pnl = gross - order.costs
        self.net_realized += order.realized_pnl
        self.gross_loss += max(-order.realized_pnl, 0.0)
        if order.candidate.family == XauSignalFamily.REVERSAL and order.broker_day == self.state.broker_day:
            zone = next(z for z in self.state.zones if z.zone.id == order.candidate.zone_id)
            zone.reversal_usage = 2 if zone.reversal_fill_count >= reversal_limit(zone.zone, self.config.inputs) else 0
        self._event(order, "CLOSE", time, reason)
        self._daily_guard(time)
        self._enforce_pending_risk(time, bid, ask)
        return True

    @profile_it
    def _cancel(self, order: ReplayOrder, time: datetime, reason: ReplayReason) -> None:
        if self.economics.accepts("CANCEL", order.request_id, time):
            order.status = XauExecutionStatus.CANCELLED
            self._feedback(order)
            self._event(order, "CANCEL", time, reason)
        else:
            self._event(order, "CANCEL_REJECT", time, reason)

    def _roll(
        self,
        day: str,
        bar: datetime,
        bar_open: float,
        zones: Sequence[XauZone],
        openings: Sequence[XauPullbackWindowState],
        time: datetime,
        bid: float,
        ask: float,
    ) -> None:
        if self.bar != bar:
            self._age_cycles(time)
        if self.state.broker_day != day:
            self._change_day(day, zones, time)
        self.bar, self.bar_open = bar, bar_open
        for opening in openings:
            self._open_cycle(opening, time)

    def _change_day(self, day: str, zones: Sequence[XauZone], time: datetime) -> None:
        if self.state.broker_day:
            for window in self.state.pullbacks:
                self._end_cycle(window, time, "DAY_ROLLOVER")
        self.state.broker_day = day
        self.state.zones = [XauDailyZoneSignalState(deepcopy(z)) for z in zones]
        self.state.breakout_sequence = 0
        self.state.attempted_bars.clear()
        self.net_realized = self.gross_loss = 0.0
        self.daily_locked = self.daily_would_trigger_logged = False
        self.restart_locked = day in self.config.restart_days and not (
            self.config.inputs.allow_same_day_fresh_start
            and not any(
                o.status in (XauExecutionStatus.SUBMITTED, XauExecutionStatus.FILLED) for o in self.orders.values()
            )
        )

    def _age_cycles(self, time: datetime) -> None:
        for window in self.state.pullbacks:
            if not window.active:
                continue
            if window.bar_offset >= self.config.inputs.window_bars:
                self._end_cycle(window, time, "WINDOW_EXPIRED")
            else:
                window.bar_offset += 1

    def _open_cycle(self, opening: XauPullbackWindowState, time: datetime) -> bool:
        if self.daily_locked or self.restart_locked or not self.config.inputs.enable_pullback or self.session_preclose:
            return False
        zone = next((z for z in self.state.zones if z.zone.id == opening.zone.id), None)
        zones = [z.zone for z in self.state.zones]
        if zone is None or not pullback_allowed(zones, zone, opening.direction == XauDirection.BUY, self.config.inputs):
            return False
        if any(
            w.active
            and w.broker_day == self.state.broker_day
            and w.zone.id == opening.zone.id
            and w.direction == opening.direction
            for w in self.state.pullbacks
        ):
            return False
        window = deepcopy(opening)
        window.active = True
        window.bar_offset = 1
        window.broker_day = self.state.broker_day
        window.pending_active = window.penetration_latched = False
        window.order_ticket = ""
        self.state.pullbacks.append(window)
        return True

    def _session(self, time: datetime, bid: float, ask: float) -> None:
        inputs = self.config.inputs
        session = self.economics.session_window(time)
        if session is None:
            self.session_preclose = False
            return
        start, end = session
        timezone = ZoneInfo(inputs.broker_timezone)
        window_key = (
            start.astimezone(timezone).strftime("%Y.%m.%d %H:%M:%S")
            + "->"
            + end.astimezone(timezone).strftime("%Y.%m.%d %H:%M:%S")
        )
        self.session_active_window_key = window_key
        self.session_active_from, self.session_active_to = start, end
        if inputs.session_safety_telemetry:
            for order in self._session_positions():
                if (
                    order.status == XauExecutionStatus.FILLED
                    and order.fill_time is not None
                    and order.fill_time < start
                ):
                    order.last_carry_audit_key = window_key
        cutoff = end - timedelta(seconds=max(1, int(inputs.preclose_minutes * 60 + 0.5)))
        self.session_preclose = inputs.session_mode != "carry" and cutoff <= time < end
        self.operational_locked = self.restart_locked or self.session_preclose
        if self.session_preclose:
            mode = {"all": "ALL_FLAT", "pullback": "PB_FLAT", "carry": "BASELINE_CARRY"}[inputs.session_mode]
            key = window_key + "|" + mode
            reason = (
                f"broker_session_end={end.astimezone(timezone):%Y.%m.%d %H:%M:%S} "
                f"cutoff={cutoff.astimezone(timezone):%Y.%m.%d %H:%M:%S} "
                f"minutes={inputs.preclose_minutes:.2f} window={window_key}"
            )
            if self.session_cutoff_key != key:
                self.session_cutoff_key = key
                for window in self.state.pullbacks:
                    self._end_cycle(window, time, "SESSION_OR_RESTART")
                for order in self._session_pending():
                    self._cancel(order, time, "SESSION_OR_RESTART")
            for order in self._session_positions():
                if order.status == XauExecutionStatus.FILLED and (
                    inputs.session_mode == "all"
                    or (
                        order.native_trade_type == "P"
                        if order.native_trade_type is not None
                        else order.candidate.family == XauSignalFamily.PULLBACK
                    )
                ):
                    order.session_close_requested = True
                    order.session_close_reason = reason
                    self._close(order, time, bid, ask, "SESSION_OR_RESTART")

    def _session_positions(self) -> list[ReplayOrder]:
        return [o for o in reversed(list(self.orders.values())) if o.status == XauExecutionStatus.FILLED]

    def _session_pending(self) -> list[ReplayOrder]:
        return [o for o in self.orders.values() if o.status == XauExecutionStatus.SUBMITTED]

    def _restart(self, time: datetime, bid: float, ask: float) -> bool:
        if not self.restart_locked:
            return False
        for order in self.orders.values():
            if order.status == XauExecutionStatus.SUBMITTED:
                self._cancel(order, time, "SESSION_OR_RESTART")
            elif order.status == XauExecutionStatus.FILLED:
                self._close(order, time, bid, ask, "SESSION_OR_RESTART")
        return True

    def _breakout(self, candidate: XauSignalCandidate, time: datetime, bid: float, ask: float) -> bool:
        for order in list(self.orders.values()):
            if (
                order.status == XauExecutionStatus.FILLED
                and order.broker_day == self.state.broker_day
                and order.candidate.family == XauSignalFamily.REVERSAL
                and order.candidate.zone_id == candidate.zone_id
                and order.direction != candidate.direction
            ):
                if not self._close(order, time, bid, ask, "OPPOSITE_BREAKOUT"):
                    return False
        self._submit(candidate, time, bid, ask)
        zone = next((z.zone for z in self.state.zones if z.zone.id == candidate.zone_id), None)
        if zone is None:
            return False
        return self._open_cycle(
            XauPullbackWindowState(
                candidate.candidate_id,
                deepcopy(zone),
                candidate.direction,
                active=True,
                bar_offset=1,
                breakout_bar_time=pd.Timestamp(candidate.bar_id).to_pydatetime(),
            ),
            time,
        )

    def _pullbacks(self, time: datetime, bid: float, ask: float) -> list[XauSignalCandidate]:
        candidates = []
        if self.daily_locked or self.session_preclose or self.restart_locked:
            return candidates
        zones = [z.zone for z in self.state.zones]
        for window in self.state.pullbacks:
            if not window.active or window.broker_day != self.state.broker_day:
                continue
            zone = next((z for z in self.state.zones if z.zone.id == window.zone.id), None)
            if zone is None:
                continue
            buy = window.direction == XauDirection.BUY
            if not pullback_allowed(zones, zone, buy, self.config.inputs):
                self._end_cycle(window, time, "PULLBACK_FILTER")
                continue
            if not window.penetration_latched:
                window.penetration_latched = (
                    bid <= window.zone.high - self.config.inputs.penetration
                    if buy
                    else bid >= window.zone.low + self.config.inputs.penetration
                )
            if window.penetration_latched and not window.order_ticket:
                candidate = XauSignalCandidate(
                    candidate_id=f"{window.parent_breakout_id}:PB",
                    parent_breakout_id=window.parent_breakout_id,
                    bar_id=str(self.bar),
                    zone_id=window.zone.id,
                    family=XauSignalFamily.PULLBACK,
                    direction=window.direction,
                    order_type=XauOrderType.PENDING_STOP,
                    signal_time=time,
                    entry_price=window.zone.high if buy else window.zone.low,
                )
                if self._submit(candidate, time, bid, ask):
                    candidates.append(candidate)
            elif window.order_ticket:
                order = self.orders.get(window.order_ticket)
                if order is None or order.status != XauExecutionStatus.SUBMITTED:
                    window.order_ticket = ""
                    window.pending_active = window.waiting_logged = False
        return candidates

    def _settle(self, time: datetime, bid: float, ask: float) -> None:
        for order in self.orders.values():
            if order.status == XauExecutionStatus.SUBMITTED:
                triggered = (
                    ask >= order.candidate.entry_price
                    if order.direction == XauDirection.BUY
                    else (bid <= order.candidate.entry_price)
                )
                if triggered:
                    self._fill(order, time, bid, ask)
            if order.status == XauExecutionStatus.FILLED:
                mark = order.mark(bid, ask)
                stop_hit = mark <= order.stop_loss if order.direction == XauDirection.BUY else mark >= order.stop_loss
                tp_hit = mark >= order.take_profit if order.direction == XauDirection.BUY else mark <= order.take_profit
                if stop_hit or tp_hit:
                    self._close(order, time, bid, ask, "SL" if stop_hit else "TP")

    def _manage(self, time: datetime, bid: float, ask: float, breakouts: Sequence[XauSignalCandidate]) -> None:
        if not self.config.inputs.profit_protection:
            return
        for order in self.orders.values():
            if order.status != XauExecutionStatus.FILLED or order.r0 <= 0 or not self._position_available(order):
                continue
            buy = order.direction == XauDirection.BUY
            entry = order.candidate.entry_price
            favorable = max(0.0, bid - entry if buy else entry - ask)
            for stage, threshold in ((1, 1.0), (2, 1.5), (3, 2.0)):
                if favorable >= threshold * order.r0:
                    order.r_stage = max(order.r_stage, stage)
            desired = self._structure_stop(buy) if order.r_stage >= 3 else None
            if desired is not None and not self._stop_improves(buy, order.stop_loss, desired):
                desired = None
            if desired is None and order.r_stage >= 2:
                desired = entry + (0.5 * order.r0 if buy else -0.5 * order.r0)
            if desired is None and order.r_stage >= 1:
                offset = self._cost_offset(order)
                desired = order.fill_price + (offset if buy else -offset)
            if desired is None:
                continue
            desired = normalize_price(desired, self.config.inputs.digits)
            if not self._stop_improves(buy, order.stop_loss, desired):
                continue
            order.desired_sl = desired
            quote = bid if buy else ask
            distance = quote - desired if buy else desired - quote
            accepted = distance > 0 and distance >= self.economics.minimum_stop_distance
            accepted = accepted and self._accept_modification(order, time)
            order.sl_retry_logged = not accepted
            if accepted:
                order.stop_loss = desired
                order.desired_sl = 0.0
            self._event(order, "MODIFY" if accepted else "MODIFY_REJECT", time)

    def _cost_offset(self, order: ReplayOrder) -> float:
        unit_exit = order.fill_price + (1 if order.direction == XauDirection.BUY else -1)
        cash = abs(self.economics.profit(order.direction, self.config.inputs.volume, order.fill_price, unit_exit))
        return max(order.costs, 0.0) / cash if cash > 0 else 0.0

    def _position_available(self, order: ReplayOrder) -> bool:
        return True

    def _accept_modification(self, order: ReplayOrder, time: datetime) -> bool:
        return self.economics.accepts("MODIFY", order.request_id, time)

    def _stop_improves(self, buy: bool, current: float, proposed: float) -> bool:
        if proposed <= 0:
            return False
        epsilon = 10 ** (-self.config.inputs.digits) * 0.1
        return current <= 0 or (proposed > current + epsilon if buy else proposed < current - epsilon)

    def _structure_stop(self, buy: bool) -> float | None:
        values = [bar[2 if buy else 1] for bar in self.closed_bars]
        found = []
        for i in range(len(values) - 2, max(-1, len(values) - 101), -1):
            if i < 1:
                break
            cur, newer, older = values[i], values[i + 1], values[i - 1]
            if (cur < newer and cur < older) if buy else (cur > newer and cur > older):
                found.append(cur)
                if len(found) == 2:
                    valid = found[0] > found[1] if buy else found[0] < found[1]
                    return normalize_price(found[0], self.config.inputs.digits) if valid else None
        return None

    @profile_it
    def _protection_valid(self, direction: XauDirection, stop: float, target: float, bid: float, ask: float) -> bool:
        distance = self.economics.minimum_stop_distance
        if direction == XauDirection.BUY:
            return 0 < stop < bid < target and bid - stop >= distance and target - bid >= distance
        return 0 < target < ask < stop and stop - ask >= distance and ask - target >= distance

    @profile_it
    def _risk(self, bid: float, ask: float) -> tuple[float, float, int, float]:
        open_risk = pending_risk = margin = unrealized = 0.0
        count = 0
        for order in self.orders.values():
            if order.status == XauExecutionStatus.SUBMITTED:
                pending_risk += max(
                    -self.economics.profit(order.direction, order.volume, order.candidate.entry_price, order.stop_loss),
                    0.0,
                )
            elif order.status == XauExecutionStatus.FILLED:
                open_risk += max(
                    -self.economics.profit(
                        order.direction,
                        order.volume,
                        order.fill_price,
                        order.stop_loss if order.stop_loss > 0 else order.initial_sl,
                    ),
                    0.0,
                )
                unrealized += self.economics.profit(
                    order.direction, order.volume, order.fill_price, order.mark(bid, ask)
                )
                count += 1
            else:
                continue
            margin += self.economics.margin(order.volume, order.fill_price or order.candidate.entry_price)
        return open_risk, pending_risk, count, self.balance + unrealized - margin

    def _blocked_reversal(self, candidate: XauSignalCandidate, bid: float, ask: float) -> bool:
        return False

    def _submit(self, candidate: XauSignalCandidate, time: datetime, bid: float, ask: float) -> bool:
        inputs = self.config.inputs
        zones = [z.zone for z in self.state.zones]
        index = next((i for i, z in enumerate(zones) if z.id == candidate.zone_id), -1)
        if index < 0 or self.daily_locked or self.restart_locked:
            return False
        family = candidate.family
        is_pb = family == XauSignalFamily.PULLBACK
        if self.session_preclose and (inputs.session_mode == "all" or is_pb):
            return False
        zone = self.state.zones[index]
        buy = candidate.direction == XauDirection.BUY
        if family == XauSignalFamily.BREAKOUT:
            if not inputs.enable_direct_breakout or (inputs.breakout_normal_only and zone.zone.priority == 1):
                return False
        elif family == XauSignalFamily.REVERSAL:
            if not reversal_allowed(zones, index, buy, inputs):
                return False
            if zone.reversal_fill_count >= reversal_limit(zone.zone, inputs):
                return False
        elif not pullback_allowed(zones, zone, buy, inputs):
            return False
        if self._live_positions_count(bid, ask) >= inputs.max_positions:
            self.rejections.append((candidate.candidate_id, int(XauEntryRejection.CONCURRENCY)))
            return False
        requested = normalize_price(candidate.entry_price, inputs.digits) if is_pb else (ask if buy else bid)
        window = (
            next(
                (
                    w
                    for w in self.state.pullbacks
                    if w.active
                    and w.parent_breakout_id == candidate.parent_breakout_id
                    and w.zone.id == candidate.zone_id
                    and w.direction == candidate.direction
                ),
                None,
            )
            if is_pb
            else None
        )
        if is_pb:
            gap = requested - ask if buy else bid - requested
            if gap <= 0 or gap < self.economics.minimum_stop_distance:
                if window is not None:
                    window.waiting_logged = True
                return False
        protected = protection(
            zones,
            index,
            candidate.direction,
            requested,
            family == XauSignalFamily.REVERSAL and zone.zone.priority == 1,
            inputs,
        )
        if protected is None:
            self.rejections.append((candidate.candidate_id, int(XauEntryRejection.INITIAL_RISK)))
            if window is not None:
                self._end_cycle(window, time, "INVALID_PROTECTION")
            return False
        stop, target, r0, target_id = protected
        used = self._risk_used(bid, ask)
        cash_risk = (
            0.0
            if inputs.risk_mode == "off"
            else self._new_cash_risk(candidate.direction, inputs.volume, requested, stop)
        )
        if inputs.risk_mode != "off" and (self._budget() - used < -0.01 or cash_risk > self._budget() - used + 0.01):
            if window is not None:
                window.risk_waiting_logged = True
            self.rejections.append((candidate.candidate_id, int(XauEntryRejection.GROSS_RISK)))
            return False
        if window is not None:
            window.risk_waiting_logged = False
        bar_id = str(self.bar)
        if inputs.one_order_per_candle:
            if bar_id in self.state.attempted_bars:
                return False
            self.state.attempted_bars[:] = [bar_id]
        self.sequence += 1
        request_candidate = deepcopy(candidate)
        request_candidate.entry_price = requested
        if family == XauSignalFamily.BREAKOUT:
            request_candidate.parent_breakout_id = candidate.candidate_id
        order = ReplayOrder(
            f"REQ-{self.stream_id}-{self.sequence}",
            request_candidate,
            inputs.volume,
            stop,
            target,
            target_id,
            time,
            broker_day=self.state.broker_day,
            initial_sl=stop,
            r0=r0,
            reversal_ordinal=zone.reversal_fill_count + 1 if family == XauSignalFamily.REVERSAL else 0,
        )
        accepted = self._send(order, time, bid, ask, is_pb)
        self.orders[order.request_id] = order
        self.requests.append(order)
        self.actions.append(
            {
                "request_id": order.request_id,
                "candidate": CandidateSnapshot(
                    candidate_id=candidate.candidate_id,
                    parent_breakout_id=candidate.parent_breakout_id,
                    bar_id=candidate.bar_id,
                    zone_id=candidate.zone_id,
                    family=family,
                    direction=candidate.direction,
                    order_type=candidate.order_type,
                    signal_time=candidate.signal_time,
                    entry_price=requested,
                ),
                "direction": int(candidate.direction),
                "order_type": int(candidate.order_type),
                "entry_price": requested,
                "stop_loss": stop,
                "take_profit": target,
                "volume": inputs.volume,
                "accepted": accepted,
            }
        )
        if not accepted:
            order.request_active = False
            order.status = XauExecutionStatus.REJECTED
            self._event(order, "REJECT", time)
            return False
        self._event(order, "SUBMIT", time)
        if not is_pb:
            self._fill(order, time, bid, ask)
        else:
            self._feedback(order)
            if window is not None:
                window.waiting_logged = window.risk_waiting_logged = False
        return True

    def _send(self, order: ReplayOrder, time: datetime, bid: float, ask: float, is_pb: bool) -> bool:
        requested = order.candidate.entry_price
        accepted = self._protection_valid(
            order.direction,
            order.stop_loss,
            order.take_profit,
            requested if is_pb else bid,
            requested if is_pb else ask,
        )
        margin = self.economics.margin(order.volume, requested)
        return (
            accepted and margin <= self._risk(bid, ask)[3] and self.economics.accepts("SUBMIT", order.request_id, time)
        )

    def _live_positions_count(self, bid: float, ask: float) -> int:
        return self._risk(bid, ask)[2]

    def _new_cash_risk(self, direction: XauDirection, volume: float, entry: float, sl: float) -> float:
        return max(0.0, -self.economics.profit(direction, volume, entry, sl))

    def _budget(self) -> float:
        inputs = self.config.inputs
        if inputs.risk_mode == "off":
            return float("inf")
        basis = inputs.qa_capital if inputs.qa_discovery else self.config.initial_balance
        return basis * inputs.risk_percent / 100.0

    def _risk_used(self, bid: float, ask: float) -> float:
        if self.config.inputs.risk_mode == "off":
            return 0.0
        realized = self.gross_loss if self.config.inputs.risk_mode == "gross" else max(0.0, -self.net_realized)
        opened, pending, _, _ = self._risk(bid, ask)
        return realized + opened + pending

    def _daily_guard(self, time: datetime) -> None:
        inputs = self.config.inputs
        basis = inputs.qa_capital if inputs.qa_discovery else self.config.initial_balance
        if self.daily_locked or (not inputs.daily_loss_override and basis >= 300):
            return
        pct = inputs.daily_loss_percent if inputs.daily_loss_override else 20.0
        if self.net_realized > -basis * pct / 100.0:
            return
        if inputs.qa_discovery:
            self.daily_would_trigger_logged = True
            return
        self.daily_locked = True
        for window in self.state.pullbacks:
            self._end_cycle(window, time, "DAILY_LOSS")

    def _end_cycle(self, window: XauPullbackWindowState, time: datetime, reason: ReplayReason) -> None:
        if not window.active:
            return
        order = self.orders.get(window.order_ticket)
        if order is not None and order.status == XauExecutionStatus.SUBMITTED:
            self._cancel(order, time, reason)
        window.active = False

    def _enforce_pending_risk(self, time: datetime, bid: float, ask: float) -> None:
        for window in reversed(self.state.pullbacks):
            if self._risk_used(bid, ask) <= self._budget() + 0.01:
                break
            if not window.active or not window.order_ticket:
                continue
            order = self.orders.get(window.order_ticket)
            if order is not None and order.status == XauExecutionStatus.SUBMITTED:
                self._cancel(order, time, "PORTFOLIO_RISK")
                if order.status == XauExecutionStatus.SUBMITTED:
                    continue
            window.order_ticket = ""
            window.pending_active = window.waiting_logged = window.risk_waiting_logged = False

    def step(
        self,
        time: datetime,
        day: str,
        bar: datetime,
        bar_open: float,
        bid: float,
        ask: float,
        zones: Sequence[XauZone],
        openings: Sequence[XauPullbackWindowState],
        breakouts: Sequence[XauSignalCandidate],
        reversals: Sequence[XauSignalCandidate],
    ) -> ReplaySnapshot:
        self._begin_tick(bid, ask)
        self._session(time, bid, ask)
        self._roll(day, bar, bar_open, zones, openings, time, bid, ask)
        if not self._restart(time, bid, ask):
            self._settle(time, bid, ask)
            for candidate in breakouts:
                self._breakout(candidate, time, bid, ask)
            for candidate in reversals:
                self._submit(candidate, time, bid, ask)
            pullbacks = self._pullbacks(time, bid, ask)
            self._manage(time, bid, ask, ())
        else:
            pullbacks = []
        return self._snapshot(bid, ask, pullbacks)

    def _begin_tick(self, bid: float, ask: float) -> None:
        if not (isfinite(bid) and isfinite(ask) and 0 < bid <= ask):
            raise ValueError("Replay requires positive finite Bid/Ask and nonnegative spread")
        self.events, self.feedback, self.actions, self.rejections = [], [], [], []

    def _snapshot(self, bid: float, ask: float, pullbacks: list[XauSignalCandidate]) -> ReplaySnapshot:
        self.previous_bid, self.previous_ask = bid, ask
        changed_ids = {event["request_id"] for event in self.events}
        visible = [
            o
            for o in self.orders.values()
            if o.request_id in changed_ids or o.status in (XauExecutionStatus.SUBMITTED, XauExecutionStatus.FILLED)
        ]
        self.operational_locked = self.restart_locked or self.session_preclose
        return {
            "action": self.actions[0] if self.actions else None,
            "actions": tuple(self.actions),
            "execution_events": tuple(self.events),
            "orders": tuple(self.order_snapshot(o) for o in visible),
            "positions": tuple(self.position_snapshot(o, bid, ask) for o in visible if o.fill_time is not None),
            "pullback_signals": tuple(pullbacks),
            "pullback_feedback": tuple(self.feedback),
            "attempted_bars": "|".join(self.state.attempted_bars),
            "entry_rejections": tuple(self.rejections),
            "daily_net_realized_pnl": self.net_realized,
            "daily_gross_loss": self.gross_loss,
            "account_balance": self.balance,
            "daily_loss_locked": self.daily_locked,
            "operational_locked": self.operational_locked,
        }
