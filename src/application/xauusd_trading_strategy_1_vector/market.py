import json
from copy import deepcopy
from datetime import datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray

from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily, XauTrend
from domain.xau_usd.models import (
    XauDailyZoneSignalState,
    XauMarketCoordinator,
    XauPullbackWindowState,
    XauSignalCandidate,
    XauZone,
)

from .domain.robust import RobustInputs, pullback_allowed
from .replay import ExecutionReplay
from .trace import shared_trace, timestamp

type ClosedHistory = NDArray[np.float64] | list[tuple[float, float, float, float]]


class MarketState:
    """Ordered visible ApprovedStrategyOnTick transitions for a single stream."""

    def __init__(self, inputs: RobustInputs, execution: ExecutionReplay | None = None) -> None:
        self.inputs = inputs
        self.execution = execution
        self.state = execution.state if execution else XauMarketCoordinator()
        self.bar: datetime | None = None
        self.previous_bid = 0.0
        self.trend = XauTrend.NONE
        self.history: ClosedHistory = []

    def _change_day(self, day: str, zones: list[XauZone], time: datetime) -> None:
        if self.execution:
            self.execution._change_day(day, zones, time)
        else:
            for cycle in self.state.pullbacks:
                cycle.active = False
            self.state.zones = [XauDailyZoneSignalState(deepcopy(z)) for z in zones]
            self.state.broker_day = day
            self.state.breakout_sequence = 0

    def _age(self, time: datetime) -> None:
        if self.execution:
            self.execution._age_cycles(time)
            return
        for cycle in self.state.pullbacks:
            if cycle.active:
                if cycle.bar_offset >= self.inputs.window_bars:
                    cycle.active = False
                else:
                    cycle.bar_offset += 1

    def _breakouts(self, time: datetime, close: float, bid: float, ask: float) -> list[XauSignalCandidate]:
        candidates = []
        for state in self.state.zones:
            zone = state.zone
            buy = state.buy_engaged and self.trend == XauTrend.UP and close > zone.high + self.inputs.breakout_buffer
            sell = state.sell_engaged and self.trend == XauTrend.DOWN and close < zone.low - self.inputs.breakout_buffer
            if not (buy or sell):
                continue
            self.state.breakout_sequence += 1
            candidate = XauSignalCandidate(
                candidate_id=f"BO#{self.state.breakout_sequence:02d}",
                bar_id=str(self.bar),
                zone_id=zone.id,
                family=XauSignalFamily.BREAKOUT,
                direction=XauDirection.BUY if buy else XauDirection.SELL,
                signal_time=time,
                entry_price=close,
            )
            candidates.append(candidate)
            if self.execution:
                self.execution._breakout(candidate, time, bid, ask)
            elif (
                self.inputs.enable_pullback
                and pullback_allowed([z.zone for z in self.state.zones], state, buy, self.inputs)
                and not any(
                    w.active and w.zone.id == zone.id and w.direction == candidate.direction
                    for w in self.state.pullbacks
                )
            ):
                self.state.pullbacks.append(
                    XauPullbackWindowState(
                        candidate.candidate_id,
                        deepcopy(zone),
                        candidate.direction,
                        bar_offset=1,
                        active=True,
                        breakout_bar_time=self.bar,
                        broker_day=self.state.broker_day,
                    )
                )
        return candidates

    def _touches(self, time: datetime, bid: float, ask: float) -> tuple[bool, list[XauSignalCandidate]]:
        crossings = [
            (self.previous_bid < z.zone.low <= bid, self.previous_bid > z.zone.high >= bid) for z in self.state.zones
        ]
        multi = sum(up or down for up, down in crossings) >= 2
        candidates = []
        for state, (up, down) in zip(self.state.zones, crossings, strict=True):
            if multi:
                if state.zone.low <= bid <= state.zone.high:
                    state.buy_engaged = state.sell_engaged = True
                continue
            state.buy_engaged |= up
            state.sell_engaged |= down
            if self.execution and self.execution.daily_locked:
                continue
            buy = self.trend == XauTrend.DOWN and down
            sell = self.trend == XauTrend.UP and up
            if not (buy or sell):
                continue
            slot = "last_reversal_buy_signal_bar" if buy else "last_reversal_sell_signal_bar"
            if getattr(state, slot) == self.bar:
                continue
            setattr(state, slot, self.bar)
            direction = XauDirection.BUY if buy else XauDirection.SELL
            candidate = XauSignalCandidate(
                candidate_id=f"{self.bar}:R:{state.zone.id}:{direction.value}",
                bar_id=str(self.bar),
                zone_id=state.zone.id,
                family=XauSignalFamily.REVERSAL,
                direction=direction,
                signal_time=time,
                entry_price=ask if buy else bid,
            )
            if self.execution:
                before = len(self.execution.actions)
                self.execution._submit(candidate, time, bid, ask)
                if len(self.execution.actions) == before:
                    continue
            candidates.append(candidate)
        return multi, candidates

    def _signal_pullbacks(self, time: datetime, bid: float) -> list[XauSignalCandidate]:
        candidates = []
        for window in self.state.pullbacks:
            if not window.active:
                continue
            buy = window.direction == XauDirection.BUY
            was_latched = window.penetration_latched
            window.penetration_latched |= (
                bid <= window.zone.high - self.inputs.penetration
                if buy
                else bid >= window.zone.low + self.inputs.penetration
            )
            if window.penetration_latched and not was_latched:
                candidates.append(
                    XauSignalCandidate(
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
                )
        return candidates

    def step(
        self,
        time: datetime,
        day: str,
        bar: datetime,
        bar_open: float,
        bid: float,
        ask: float,
        history: ClosedHistory,
        zones: list[XauZone],
    ) -> dict[str, Any]:
        if len(history) < 3:
            raise ValueError("MT5 startup requires three native closed M15 candles")
        execution = self.execution
        if execution:
            execution._begin_tick(bid, ask)
            execution._session(time, bid, ask)
        previous_cycles = len(self.state.pullbacks)
        breakouts = []
        if self.bar != bar:
            if self.bar is not None:
                self._age(time)
                breakouts = self._breakouts(time, float(history[-1][3]), bid, ask)
            if day != self.state.broker_day:
                self._change_day(day, zones, time)
            if self.bar is None:
                self.previous_bid = bid
            self.bar = bar
            self.state.bar_open = bar_open
            self.history = history
            for state in self.state.zones:
                state.buy_engaged = state.sell_engaged = state.zone.low <= bar_open <= state.zone.high
            if execution:
                execution.bar, execution.bar_open = bar, bar_open
                execution.closed_bars = history
        reference_high = max(c[1] for c in self.history[-3:])
        reference_low = min(c[2] for c in self.history[-3:])
        locked = execution is not None and execution._restart(time, bid, ask)
        multi = False
        reversals: list[XauSignalCandidate] = []
        pullbacks: list[XauSignalCandidate] = []
        if not locked:
            if execution:
                execution._settle(time, bid, ask)
            if bid > reference_high:
                self.trend = XauTrend.UP
            elif bid < reference_low:
                self.trend = XauTrend.DOWN
            multi, reversals = self._touches(time, bid, ask)
            if execution:
                pullbacks = execution._pullbacks(time, bid, ask)
                execution._manage(time, bid, ask, ())
            else:
                pullbacks = self._signal_pullbacks(time, bid)
        self.previous_bid = bid
        active = [w for w in self.state.pullbacks if w.active]
        result: dict[str, Any] = {
            "trend": int(self.trend),
            "trend_count": 3,
            "bar_open": bar_open,
            "bar_active": True,
            "day_active": bool(self.state.zones),
            "reference_high": reference_high,
            "reference_low": reference_low,
            "buy_engaged": any(z.buy_engaged for z in self.state.zones),
            "sell_engaged": any(z.sell_engaged for z in self.state.zones),
            "multi_zone_tick_gap": multi,
            "breakout_sequence": self.state.breakout_sequence,
            "breakout_signals": tuple(breakouts),
            "reversal_signals": tuple(reversals),
            "pullback_signals": tuple(pullbacks),
            "pullback_windows_opened": tuple(deepcopy(self.state.pullbacks[previous_cycles:])),
            "pullback_active": bool(active),
            "pullback_bar_offset": max((w.bar_offset for w in active), default=0),
            "pullback_penetration_latched": any(w.penetration_latched for w in active),
        }
        for i, candle in enumerate(self.history[-3:]):
            result[f"trend_high_{i}"] = candle[1]
            result[f"trend_low_{i}"] = candle[2]
        for z in self.state.zones:
            result[f"buy_engaged:{z.zone.id}"] = z.buy_engaged
            result[f"sell_engaged:{z.zone.id}"] = z.sell_engaged
        for z in self.state.zones:
            for direction in XauDirection:
                window = next((w for w in active if w.zone.id == z.zone.id and w.direction == direction), None)
                prefix = f"pullback:{z.zone.id}:{direction.value}"
                result[f"{prefix}:parent"] = window.parent_breakout_id if window else ""
                result[f"{prefix}:offset"] = window.bar_offset if window else 0
        if execution:
            result.update(execution._snapshot(bid, ask, pullbacks))
        trace = shared_trace(self.state, execution)
        trace.update(
            {
                "g_bar_time": timestamp(bar),
                "g_prev_bid": bid,
                "g_trend": int(self.trend),
                "g_ref_high": reference_high,
                "g_ref_low": reference_low,
            }
        )
        result["mt5_state"] = json.dumps(trace, allow_nan=False)
        return result
