"""Compiled replay risk state operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .kernel import ReplayKernel


import numpy as np
from numba import njit


@njit(cache=False)
def profit(self: ReplayKernel, side: int, entry: float, price: float) -> float:
    return (1.0 if side == 0 else -1.0) * (price - entry) * self.p["volume"] * self.multiplier


@njit(cache=False)
def risk(self: ReplayKernel) -> tuple[float, float, int, float]:
    opened = pending = margin = unrealized = 0.0
    count = 0
    for k in self.active:
        i, f = self.oi[k], self.of[k]
        if i[0] == 0:
            pending += max(0.0, -self.profit(i[1], f[0], f[1]))
        elif i[0] == 1:
            opened += max(0.0, -self.profit(i[1], f[5], f[1] if f[1] > 0 else f[3]))
            unrealized += self.profit(i[1], f[5], self.bid if i[1] == 0 else self.ask)
            count += 1
        else:
            continue
        margin += self.p["volume"] * self.margin
    return opened, pending, count, self.balance + unrealized - margin


@njit(cache=False)
def budget(self: ReplayKernel) -> float:
    if self.p["risk_mode"] == 0:
        return np.inf
    basis = self.p["qa_capital"] if self.p["qa_discovery"] else self.p["initial_balance"]
    return basis * self.p["risk_percent"] / 100.0


@njit(cache=False)
def used(self: ReplayKernel) -> float:
    if self.p["risk_mode"] == 0:
        return 0.0
    realized = self.gross if self.p["risk_mode"] == 2 else max(0.0, -self.net)
    r = self.risk()
    return realized + r[0] + r[1]


@njit(cache=False)
def daily_guard(self: ReplayKernel) -> None:
    basis = self.p["qa_capital"] if self.p["qa_discovery"] else self.p["initial_balance"]
    if self.locked or (not self.p["daily_loss_override"] and basis >= 300):
        return
    pct = self.p["daily_loss_percent"] if self.p["daily_loss_override"] else 20.0
    if self.net > -basis * pct / 100.0:
        return
    if self.p["qa_discovery"]:
        self.would_lock = 1
        return
    self.locked = 1
    for j in self.active_cycles:
        self.end_cycle(j, 7)


@njit(cache=False)
def enforce_pending(self: ReplayKernel) -> None:
    for h in range(len(self.active_cycles) - 1, -1, -1):
        if self.used() <= self.budget() + 0.01:
            break
        w = self.cycles[self.active_cycles[h]]
        if not w[4] or w[8] < 0:
            continue
        k = w[8]
        if self.oi[k][0] == 0:
            self.cancel(k, 5)
            if self.oi[k][0] == 0:
                continue
        w[8] = -1
        w[7] = w[9] = w[10] = 0
