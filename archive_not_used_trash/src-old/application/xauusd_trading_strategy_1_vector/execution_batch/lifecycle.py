"""Compiled replay lifecycle operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .kernel import ReplayKernel


import numpy as np
from numba import njit


@njit(cache=False)
def event(self: ReplayKernel, k: int, kind: int, reason: int, previous: float = 0.0, requested: float = 0.0) -> None:
    i, f = self.oi[k], self.of[k]
    # tick, ordinal, phase, order index, kind, reason, time; snapshots.
    self.ei.append(np.array([self.tick, self.ordinal, self.phase, k, kind, reason, self.time], np.int64))
    self.ef.append(np.array([previous, requested, f[1], f[2], f[5], f[6], f[9], f[7], f[8]], np.float64))
    self.ordinal += 1
    i[14] = self.tick


@njit(cache=False)
def feedback(self: ReplayKernel, k: int, filled: int) -> None:
    i = self.oi[k]
    if i[2] != 2:
        return
    c = -1
    for j in self.active_cycles:
        w = self.cycles[j]
        if w[4] and w[3] == i[6] and w[1] == i[5] and w[2] == i[1]:
            c = j
            break
    if filled:
        if i[6] == self.day:
            self.counts[i[5], 0] += 1
        if c >= 0:
            w = self.cycles[c]
            w[4] = w[7] = 0
            w[8] = -1
    elif c >= 0:
        w = self.cycles[c]
        w[7] = int(i[0] == 0)
        if w[7]:
            w[8] = k
    pending = int(c >= 0 and self.cycles[c][7] != 0)
    self.fi.append(np.array([self.tick, i[5], i[1], self.counts[i[5], 0], pending, filled], np.int64))


@njit(cache=False)
def cancel(self: ReplayKernel, k: int, reason: int) -> None:
    if self.accept[2]:
        self.oi[k][0] = 4
        self.feedback(k, 0)
        self.event(k, 4, reason)
    else:
        self.event(k, 7, reason)


@njit(cache=False)
def end_cycle(self: ReplayKernel, j: int, reason: int) -> None:
    w = self.cycles[j]
    if not w[4]:
        return
    k = w[8]
    if k >= 0 and self.oi[k][0] == 0:
        self.cancel(k, reason)
    w[4] = 0
    w[12] = reason


@njit(cache=False)
def close(self: ReplayKernel, k: int, reason: int) -> bool:
    i, f = self.oi[k], self.of[k]
    if not self.accept[1]:
        self.event(k, 6, reason)
        return False
    i[0], i[10] = 3, self.time
    f[6] = self.bid if i[1] == 0 else self.ask
    gross = self.profit(i[1], f[5], f[6])
    f[8] = self.p["volume"] * self.exit_cost
    self.balance += gross - f[8]
    f[9] = gross - f[7] - f[8]
    self.net += f[9]
    self.gross += max(-f[9], 0.0)
    self.event(k, 2, reason)
    self.daily_guard()
    self.enforce_pending()
    return True


@njit(cache=False)
def fill(self: ReplayKernel, k: int) -> None:
    i, f = self.oi[k], self.of[k]
    i[0], i[9] = 1, self.time
    f[5] = self.ask if i[1] == 0 else self.bid
    f[7] = self.p["volume"] * self.entry_cost
    self.balance -= f[7]
    self.feedback(k, 1)
    if i[2] == 1 and i[6] == self.day:
        self.counts[i[5], 1] += 1
    self.event(k, 1, 0)
    if self.risk()[2] > self.p["max_positions"]:
        self.close(k, 4)
    if i[0] == 1 and self.used() > self.budget() + 0.05:
        self.close(k, 5)


@njit(cache=False)
def pb_allowed(self: ReplayKernel, z: int, side: int) -> bool:
    if z < 0:
        return False
    row = self.zones[z]
    limit = row[4]
    return row[5 + side] != 0 and (limit < 0 or self.counts[z, 0] < limit)


@njit(cache=False)
def open_cycle(self: ReplayKernel, parent: int, z: int, side: int, born: int) -> None:
    if self.locked or self.restart or self.preclose or not self.p["enable_pullback"] or not self.pb_allowed(z, side):
        return
    for j in self.active_cycles:
        w = self.cycles[j]
        if w[4] and w[3] == self.day and w[1] == z and w[2] == side:
            return
    # parent, zone, side, day, active, age, latch, pending, order, waiting,
    # risk_waiting, birth time, reason, previous state fingerprint.
    w = np.array([parent, z, side, self.day, 1, 1, 0, 0, -1, 0, 0, born, 0, -1], np.int64)
    j = len(self.cycles)
    self.cycles.append(w)
    self.cycle_previous.append(np.full(13, -1, dtype=np.int64))
    self.active_cycles.append(j)
