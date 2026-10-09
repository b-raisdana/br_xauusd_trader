"""Compiled replay snapshots operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .kernel import ReplayKernel


import numpy as np
from numba import njit


@njit(cache=False)
def snapshot(self: ReplayKernel) -> None:
    for k in self.active:
        i, f = self.oi[k], self.of[k]
        if i[0] in (0, 1) or i[14] == self.tick:
            self.si.append(np.concatenate((np.array([self.tick, k], np.int64), i.copy())))
            mark = f[6] if i[0] == 3 else (self.bid if i[1] == 0 else self.ask)
            unrealized = self.profit(i[1], f[5], mark) - f[7] - f[8] if i[9] >= 0 and i[0] != 3 else 0.0
            self.sf.append(np.concatenate((f.copy(), np.array([mark, unrealized]))))
    self.ci.append(
        np.array(
            [
                self.tick,
                self.time,
                self.day,
                self.locked,
                int(self.restart or self.preclose),
                self.would_lock,
                self.attempted,
            ],
            np.int64,
        )
    )
    # Cycle changes are emitted once per tick, not every cycle x every tick.
    for j in self.active_cycles:
        w = self.cycles[j]
        if np.any(w[:13] != self.cycle_previous[j]):
            self.ri.append(np.concatenate((np.array([-1, self.tick, j], np.int64), w[:13].copy())))
            self.cycle_previous[j] = w[:13].copy()
    for h in range(len(self.active) - 1, -1, -1):
        if self.oi[self.active[h]][0] not in (0, 1):
            self.active.pop(h)
    for h in range(len(self.active_cycles) - 1, -1, -1):
        if not self.cycles[self.active_cycles[h]][4]:
            self.active_cycles.pop(h)
