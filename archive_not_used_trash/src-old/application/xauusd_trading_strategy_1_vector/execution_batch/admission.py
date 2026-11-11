"""Compiled replay admission operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .kernel import ReplayKernel


import numpy as np
from numba import njit

from .prices import decimal_price


@njit(cache=False)
def submit(
    self: ReplayKernel,
    candidate: int,
    parent: int,
    z: int,
    side: int,
    family: int,
    entry: float,
    order_type: int,
    candidate_bar: int,
) -> bool:
    if z < 0 or self.locked or self.restart:
        return False
    if self.preclose and (self.p["session_mode"] == 2 or family == 2):
        return False
    zr = self.zones[z]
    if family == 0:
        if not self.p["enable_direct_breakout"] or (self.p["breakout_normal_only"] and zr[2] == 1):
            return False
    elif family == 1:
        if not zr[7 + side] or self.counts[z, 1] >= zr[3]:
            return False
    elif not self.pb_allowed(z, side):
        return False
    if self.risk()[2] >= self.p["max_positions"]:
        self.ri.append(np.array([self.tick, candidate, 3], np.int64))
        return False
    requested = decimal_price(entry, int(self.p["digits"])) if family == 2 else (self.ask if side == 0 else self.bid)
    c = -1
    if family == 2:
        for j in self.active_cycles:
            w = self.cycles[j]
            if w[4] and w[0] == parent and w[1] == z and w[2] == side:
                c = j
                break
        gap = requested - self.ask if side == 0 else self.bid - requested
        if gap <= 0 or gap < self.min_stop:
            if c >= 0:
                self.cycles[c][9] = 1
            return False
    neighbor = zr[9 + side]
    stop = max(neighbor, requested - self.p["r_cap"]) if side == 0 else min(neighbor, requested + self.p["r_cap"])
    risk = requested - stop if side == 0 else stop - requested
    if family == 1 and zr[2] == 1:
        risk *= self.p["high_reversal_sl_multiplier"]
        stop = requested + (-risk if side == 0 else risk)
    target = 0.0
    if neighbor >= 0 and risk > 0:
        step = 1 if side == 0 else -1
        h = z + step
        while 0 <= h < len(self.zones) and self.zones[h, 11] == self.day:
            price = self.zones[h, 0 if side == 0 else 1]
            distance = price - requested if side == 0 else requested - price
            if distance >= self.p["target_r_multiplier"] * risk and price > 0:
                target = decimal_price(price, int(self.p["digits"]))
                break
            h += step
    if target == 0:
        self.ri.append(np.array([self.tick, candidate, 7], np.int64))
        if c >= 0:
            self.end_cycle(c, 8)
        return False
    stop = decimal_price(stop, int(self.p["digits"]))
    risk = abs(requested - stop)
    cash_risk = max(0.0, -self.profit(side, requested, stop)) if self.p["risk_mode"] else 0.0
    remaining = self.budget() - self.used()
    if self.p["risk_mode"] and (remaining < -0.01 or cash_risk > remaining + 0.01):
        if c >= 0:
            self.cycles[c][10] = 1
        self.ri.append(np.array([self.tick, candidate, 2], np.int64))
        return False
    if c >= 0:
        self.cycles[c][10] = 0
    if self.p["one_order_per_candle"]:
        if self.attempted == self.bar:
            return False
        self.attempted = self.bar
    quote_bid = requested if family == 2 else self.bid
    quote_ask = requested if family == 2 else self.ask
    valid = (
        (0 < stop < quote_bid < target and quote_bid - stop >= self.min_stop and target - quote_bid >= self.min_stop)
        if side == 0
        else (
            0 < target < quote_ask < stop and stop - quote_ask >= self.min_stop and quote_ask - target >= self.min_stop
        )
    )
    accepted = valid and self.p["volume"] * self.margin <= self.risk()[3] and self.accept[0] != 0
    # status, side, family, candidate, parent, zone, day, bar, submitted,
    # filled, closed, stage, cycle, order_type, changed_tick, candidate_bar.
    i = np.array(
        [
            0,
            side,
            family,
            candidate,
            candidate if family == 0 else parent,
            z,
            self.day,
            self.bar,
            self.time,
            -1,
            -1,
            0,
            c,
            order_type,
            self.tick,
            candidate_bar,
        ],
        np.int64,
    )
    # entry, stop, target, initial_stop, r0, fill, close, entry_cost, exit_cost, pnl, desired_stop.
    f = np.array([requested, stop, target, stop, risk, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], np.float64)
    k = len(self.oi)
    self.oi.append(i)
    self.of.append(f)
    self.active.append(k)
    self.ai.append(np.array([self.tick, k, candidate, parent, candidate_bar, int(accepted), self.phase], np.int64))
    self.af.append(np.array([requested, stop, target, self.p["volume"]], np.float64))
    if not accepted:
        i[0] = 2
        self.event(k, 3, 0)
        return False
    self.event(k, 0, 0)
    if family != 2:
        self.fill(k)
    else:
        self.feedback(k, 0)
        if c >= 0:
            self.cycles[c][9] = self.cycles[c][10] = 0
    return True
