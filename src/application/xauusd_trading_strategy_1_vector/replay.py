from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
from math import isfinite

from br_py_log_n_profile import profile_it

from application.xauusd_trading_strategy_1.domain.entry import initial_stop
from application.xauusd_trading_strategy_1.domain.models import (
    XauDailyZoneSignalState,
    XauMarketCoordinator,
    XauPreparedEntry,
)
from application.xauusd_trading_strategy_1.domain.protection import daily_loss_locked, profit_protection_stop
from application.xauusd_trading_strategy_1.domain.requests import (
    candidate_attempt_available,
    commit_prepared_entry_attempt,
    prepare_candidate_entry,
)
from application.xauusd_trading_strategy_1.domain.state import (
    evaluate_pullback_tp_failure,
    initialize_pullback_tp,
    pre_zone_cross_once,
    propose_pullback_tp_extension,
    record_pullback_fill,
    record_pullback_tp_extension,
    record_pullback_tp_restore,
)
from application.xauusd_trading_strategy_1.domain.zone import strict_pullback_trend
from application.xauusd_trading_strategy_1_vector.domain.replay import ReplayConfig, ReplayOrder
from application.xauusd_trading_strategy_1_vector.domain.schema import PullbackFeedback
from application.xauusd_trading_strategy_1_vector.signals import _pullback_candidate
from domain.xau_usd.enums import (
    XauDirection,
    XauEntryRejection,
    XauExecutionStatus,
    XauOrderType,
    XauSignalFamily,
    XauTpFailureAction,
)


class ExecutionReplay:
    """Causal execution state for one broker/symbol; no terminal I/O."""

    @profile_it
    def __init__(self, config: ReplayConfig, stream_id: str):
        self.config = config
        self.economics = config.economics
        self.stream_id = stream_id
        self.state = XauMarketCoordinator()
        self.orders: dict[str, ReplayOrder] = {}
        self.sequence = 0
        self.balance = config.initial_balance
        self.net_realized = self.gross_loss = 0.0
        self.daily_locked = self.operational_locked = False
        self.bar = None
        self.previous_bid = self.previous_ask = self.bar_open = 0.0
        self.events = []
        self.feedback = []
        self.actions = []
        self.rejections = []

    @profile_it
    def _event(self, order, kind, time, reason=""):
        self.events.append(
            {
                "request_id": order.request_id,
                "event": kind,
                "datetime": time,
                "reason": reason,
                **self.order_snapshot(order),
            }
        )

    @profile_it
    def order_snapshot(self, order):
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
    def position_snapshot(self, order, bid, ask):
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
    def _window(self, order):
        return next(
            (
                w
                for w in self.state.pullbacks
                if w.parent_breakout_id == order.candidate.parent_breakout_id
                and w.zone.id == order.candidate.zone_id
                and w.direction == order.direction
            ),
            None,
        )

    @profile_it
    def _feedback(self, order, filled=False):
        if order.candidate.family != XauSignalFamily.PULLBACK:
            return
        zone = next(z for z in self.state.zones if z.zone.id == order.candidate.zone_id)
        window = self._window(order)
        if filled:
            if window is None or not record_pullback_fill(window, zone):
                zone.pullback_fills += 1
        elif window is not None:
            window.pending_active = order.status == XauExecutionStatus.SUBMITTED
        self.feedback.append(
            PullbackFeedback(
                zone.zone.id, order.direction, zone.pullback_fills, bool(window and window.pending_active), filled
            )
        )

    @profile_it
    def _fill(self, order, time, bid, ask):
        order.status = XauExecutionStatus.FILLED
        order.fill_price = ask if order.direction == XauDirection.BUY else bid
        order.fill_time = time
        order.costs = self.economics.cost(order.volume, time, True)
        self.balance -= order.costs
        self._feedback(order, filled=True)
        if order.candidate.family == XauSignalFamily.PULLBACK:
            target = next(z.zone for z in self.state.zones if z.zone.id == order.target_zone_id)
            initialize_pullback_tp(order.tp, order.position_id, order.direction, target)
        self._event(order, "FILL", time)

    @profile_it
    def _close(self, order, time, bid, ask, reason):
        if not self.economics.accepts("CLOSE", order.request_id, time):
            self._event(order, "CLOSE_REJECT", time, reason)
            return
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
        self._event(order, "CLOSE", time, reason)

    @profile_it
    def _cancel(self, order, time, reason):
        if self.economics.accepts("CANCEL", order.request_id, time):
            order.status = XauExecutionStatus.CANCELLED
            self._feedback(order)
            self._event(order, "CANCEL", time, reason)
        else:
            self._event(order, "CANCEL_REJECT", time, reason)

    @profile_it
    def _roll(self, day, bar, bar_open, zones, openings, time, bid, ask):
        if self.state.broker_day != day:
            # A missing session-end tick cannot justify silently dropping existing exposure.
            for order in self.orders.values():
                if order.status == XauExecutionStatus.SUBMITTED:
                    self._cancel(order, time, "DAY_ROLLOVER")
                elif order.status == XauExecutionStatus.FILLED:
                    self._close(order, time, bid, ask, "DAY_ROLLOVER")
            if any(o.status in (XauExecutionStatus.SUBMITTED, XauExecutionStatus.FILLED) for o in self.orders.values()):
                raise RuntimeError("Cannot reset broker day with unresolved exposure")
            self.state = XauMarketCoordinator(
                broker_day=day, zones=[XauDailyZoneSignalState(deepcopy(z)) for z in zones]
            )
            self.net_realized = self.gross_loss = 0.0
            self.daily_locked = False
            self.operational_locked = day in self.config.restart_days
            self.bar = None
        if self.bar != bar:
            if self.bar is not None:
                direction = int(self.previous_bid > self.bar_open) - int(self.previous_bid < self.bar_open)
                for order in self.orders.values():
                    signal_bar = order.candidate.signal_time.replace(
                        minute=(order.candidate.signal_time.minute // 15) * 15, second=0, microsecond=0
                    )
                    if (
                        order.status in (XauExecutionStatus.SUBMITTED, XauExecutionStatus.FILLED)
                        and self.bar > signal_bar
                    ):
                        order.closed_directions.append(direction)
                for window in self.state.pullbacks:
                    window.bar_offset += 1
                    window.active = window.bar_offset <= 5
            self.bar, self.bar_open = bar, bar_open
        for opening in openings:
            if not any(
                w.active and w.zone.id == opening.zone.id and w.direction == opening.direction
                for w in self.state.pullbacks
            ):
                self.state.pullbacks = [
                    w for w in self.state.pullbacks if w.zone.id != opening.zone.id or w.direction != opening.direction
                ]
                self.state.pullbacks.append(deepcopy(opening))

    @profile_it
    def _settle(self, time, bid, ask):
        for order in self.orders.values():
            if order.status == XauExecutionStatus.SUBMITTED:
                window = self._window(order)
                if window is None or not window.active:
                    self._cancel(order, time, "WINDOW_EXPIRED")
                    continue
                triggered = (
                    ask >= order.candidate.entry_price
                    if order.direction == XauDirection.BUY
                    else bid <= order.candidate.entry_price
                )
                if triggered:
                    self._fill(order, time, bid, ask)
            if order.status == XauExecutionStatus.FILLED:
                mark = order.mark(bid, ask)
                stop_hit = mark <= order.stop_loss if order.direction == XauDirection.BUY else mark >= order.stop_loss
                tp_hit = mark >= order.take_profit if order.direction == XauDirection.BUY else mark <= order.take_profit
                if stop_hit or tp_hit:
                    self._close(order, time, bid, ask, "SL" if stop_hit else "TP")

    @profile_it
    def _modify(self, order, stop, target, time, bid, ask):
        accepted = self._protection_valid(order.direction, stop, target, bid, ask)
        accepted = accepted and self.economics.accepts("MODIFY", order.request_id, time)
        if accepted:
            order.stop_loss, order.take_profit = stop, target
        self._event(order, "MODIFY" if accepted else "MODIFY_REJECT", time)
        return accepted

    @profile_it
    def _strict(self, order, bid, ask):
        return strict_pullback_trend(order.direction, order.closed_directions, self.bar_open, bid, ask)

    @profile_it
    def _manage_tp(self, order, time, bid, ask):
        if order.candidate.family != XauSignalFamily.PULLBACK:
            return
        strict = self._strict(order, bid, ask)
        zones = [z.zone for z in self.state.zones]
        target_index = next((i for i, z in enumerate(zones) if z.id == order.tp.current_target_zone_id), None)
        if target_index is None:
            raise ValueError("Pullback target zone is unavailable")
        if not order.tp.extended:
            previous = self.previous_bid if order.direction == XauDirection.BUY else self.previous_ask
            if not pre_zone_cross_once(
                order.trigger, order.position_id, order.direction, zones[target_index], previous, order.mark(bid, ask)
            ):
                return
            next_index = target_index + (1 if order.direction == XauDirection.BUY else -1)
            has_next = 0 <= next_index < len(zones)
            valid, target, zone_id = propose_pullback_tp_extension(
                order.tp, zones[target_index], zones[next_index] if has_next else zones[target_index], has_next, strict
            )
            if valid:
                accepted = self._modify(order, order.stop_loss, target, time, bid, ask)
                record_pullback_tp_extension(order.tp, target, zone_id, accepted)
        else:
            action, target = evaluate_pullback_tp_failure(order.tp, strict, bid, ask)
            if action == XauTpFailureAction.RESTORE:
                record_pullback_tp_restore(order.tp, self._modify(order, order.stop_loss, target, time, bid, ask))
            elif action == XauTpFailureAction.MARKET_CLOSE:
                self._close(order, time, bid, ask, "STRICT_TREND_FAILED")

    @profile_it
    def _manage(self, time, bid, ask, breakouts):
        for order in self.orders.values():
            if order.status != XauExecutionStatus.FILLED:
                continue
            self._manage_tp(order, time, bid, ask)
            if order.status != XauExecutionStatus.FILLED:
                continue
            unit_exit = order.fill_price + (1 if order.direction == XauDirection.BUY else -1)
            cash = abs(self.economics.profit(order.direction, order.volume, order.fill_price, unit_exit))
            if not isfinite(cash) or cash <= 0:
                raise ValueError("Broker profit calculation must provide positive cash per favorable price unit")
            offset = max(order.costs, 0.0) / cash
            rf = order.fill_price + (offset if order.direction == XauDirection.BUY else -offset)
            valid, stop = profit_protection_stop(order.direction, order.fill_price, rf, bid, ask, order.stop_loss)
            if valid:
                self._modify(order, stop, order.take_profit, time, bid, ask)
            if order.candidate.family == XauSignalFamily.REVERSAL and any(
                c.zone_id == order.candidate.zone_id and c.direction != order.direction for c in breakouts
            ):
                self._close(order, time, bid, ask, "OPPOSITE_BREAKOUT")

    @profile_it
    def _protection_valid(self, direction, stop, target, bid, ask):
        distance = self.economics.minimum_stop_distance
        if direction == XauDirection.BUY:
            return 0 < stop < bid < target and bid - stop >= distance and target - bid >= distance
        return 0 < target < ask < stop and stop - ask >= distance and ask - target >= distance

    @profile_it
    def _risk(self, bid, ask):
        open_risk = pending_risk = margin = unrealized = 0.0
        count = 0
        for order in self.orders.values():
            if order.status == XauExecutionStatus.SUBMITTED:
                pending_risk += abs(
                    self.economics.profit(order.direction, order.volume, order.candidate.entry_price, order.stop_loss)
                )
            elif order.status == XauExecutionStatus.FILLED:
                open_risk += max(
                    -self.economics.profit(order.direction, order.volume, order.fill_price, order.stop_loss), 0.0
                )
                unrealized += self.economics.profit(
                    order.direction, order.volume, order.fill_price, order.mark(bid, ask)
                )
                count += 1
            else:
                continue
            margin += self.economics.margin(order.volume, order.fill_price or order.candidate.entry_price)
        return open_risk, pending_risk, count, self.balance + unrealized - margin

    @profile_it
    def _blocked_reversal(self, candidate, bid, ask):
        return candidate.family == XauSignalFamily.REVERSAL and any(
            o.status == XauExecutionStatus.FILLED
            and o.candidate.family == XauSignalFamily.PULLBACK
            and o.direction != candidate.direction
            and o.tp.current_target_zone_id == candidate.zone_id
            and self._strict(o, bid, ask)
            for o in self.orders.values()
        )

    @profile_it
    def _submit(self, candidate, time, bid, ask):
        if not candidate_attempt_available(self.state, candidate) or self._blocked_reversal(candidate, bid, ask):
            return
        zones = [z.zone for z in self.state.zones]
        found, stop, _ = initial_stop(candidate.direction, candidate.entry_price, zones)
        if not found:
            self.rejections.append((candidate.candidate_id, int(XauEntryRejection.INITIAL_RISK)))
            return
        cash_risk = abs(self.economics.profit(candidate.direction, 0.01, candidate.entry_price, stop))
        margin = self.economics.margin(0.01, candidate.entry_price)
        open_risk, pending_risk, count, free_margin = self._risk(bid, ask)
        if not all(isfinite(x) for x in (cash_risk, margin, open_risk, pending_risk, free_margin)):
            raise ValueError("Non-finite broker risk calculation")
        prepared = XauPreparedEntry()
        if not prepare_candidate_entry(
            candidate,
            zones,
            self.daily_locked,
            self.config.strategy_capital,
            self.gross_loss,
            open_risk,
            pending_risk,
            count,
            cash_risk,
            margin,
            max(free_margin, 0.0),
            prepared,
        ):
            raise ValueError("Invalid signal candidate")
        if prepared.decision != XauEntryRejection.ALLOWED:
            self.rejections.append((candidate.candidate_id, int(prepared.decision)))
            return
        self.sequence += 1
        order = ReplayOrder(
            f"REQ-{self.stream_id}-{self.sequence}",
            deepcopy(candidate),
            0.01,
            prepared.stop_loss,
            prepared.take_profit,
            prepared.target_zone_id,
            time,
        )
        accepted = self._protection_valid(order.direction, order.stop_loss, order.take_profit, bid, ask)
        if candidate.order_type == XauOrderType.PENDING_STOP:
            accepted = self._protection_valid(
                order.direction, order.stop_loss, order.take_profit, candidate.entry_price, candidate.entry_price
            )
            gap = (
                candidate.entry_price - ask if candidate.direction == XauDirection.BUY else bid - candidate.entry_price
            )
            accepted = accepted and gap > 0 and gap >= self.economics.minimum_stop_distance
        accepted = accepted and self.economics.accepts("SUBMIT", order.request_id, time)
        if not commit_prepared_entry_attempt(self.state, prepared, accepted):
            raise RuntimeError("Entry attempt could not be committed")
        self.orders[order.request_id] = order
        self.actions.append(
            {
                "request_id": order.request_id,
                "candidate": asdict(candidate),
                "direction": int(candidate.direction),
                "order_type": int(candidate.order_type),
                "entry_price": candidate.entry_price,
                "stop_loss": order.stop_loss,
                "take_profit": order.take_profit,
                "volume": order.volume,
                "accepted": accepted,
            }
        )
        if not accepted:
            order.status = XauExecutionStatus.REJECTED
            self._event(order, "REJECT", time)
            return
        self._event(order, "SUBMIT", time)
        if candidate.order_type == XauOrderType.MARKET:
            self._fill(order, time, bid, ask)
        else:
            self._feedback(order)

    @profile_it
    def step(self, time, day, bar, bar_open, bid, ask, zones, openings, breakouts, reversals):
        self.events, self.feedback, self.actions, self.rejections = [], [], [], []
        if not (isfinite(bid) and isfinite(ask) and 0 < bid <= ask):
            raise ValueError("Replay requires positive finite Bid/Ask and nonnegative spread")
        self._roll(day, bar, bar_open, zones, openings, time, bid, ask)
        end = self.economics.session_end(time)
        if end.tzinfo is None:
            raise ValueError("Session end must be timezone-aware")
        self.operational_locked |= time >= end - timedelta(minutes=5)
        if not self.operational_locked:
            self._settle(time, bid, ask)
        self.daily_locked = daily_loss_locked(self.config.strategy_capital, self.net_realized, self.daily_locked)
        if self.operational_locked or self.daily_locked:
            for order in self.orders.values():
                if order.status == XauExecutionStatus.SUBMITTED:
                    self._cancel(order, time, "SESSION_OR_RESTART" if self.operational_locked else "DAILY_LOSS")
                elif self.operational_locked and order.status == XauExecutionStatus.FILLED:
                    self._close(order, time, bid, ask, "SESSION_OR_RESTART")
        pullbacks = []
        if not self.operational_locked:
            self._manage(time, bid, ask, breakouts)
            self.daily_locked = daily_loss_locked(self.config.strategy_capital, self.net_realized, self.daily_locked)
            for candidate in breakouts:
                self._submit(candidate, time, bid, ask)
            for window in self.state.pullbacks:
                zone = next(z for z in self.state.zones if z.zone.id == window.zone.id)
                candidate = _pullback_candidate(window, bid, bar, time, zone.pullback_fills)
                if candidate is not None:
                    pullbacks.append(candidate)
            for candidate in (*reversals, *pullbacks):
                self._submit(candidate, time, bid, ask)
        self.previous_bid, self.previous_ask = bid, ask
        changed_ids = {event["request_id"] for event in self.events}
        visible = [
            o
            for o in self.orders.values()
            if o.request_id in changed_ids or o.status in (XauExecutionStatus.SUBMITTED, XauExecutionStatus.FILLED)
        ]
        snapshot = {
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
        self.orders = {
            key: order
            for key, order in self.orders.items()
            if order.status in (XauExecutionStatus.SUBMITTED, XauExecutionStatus.FILLED)
        }
        return snapshot
