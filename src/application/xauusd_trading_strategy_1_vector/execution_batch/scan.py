"""Ordered replay phases over aligned primitive tick arrays."""

from __future__ import annotations

from typing import TYPE_CHECKING

from numpy.typing import NDArray

if TYPE_CHECKING:
    from .kernel import ReplayKernel


import numpy as np
from numba import njit


@njit(cache=False)
def scan(
    kernel: ReplayKernel,
    ticks: NDArray[np.int64],
    quotes: NDArray[np.float64],
    economics: NDArray[np.float64],
    acceptance: NDArray[np.int64],
    candidates: NDArray[np.int64],
    candidate_prices: NDArray[np.float64],
    windows: NDArray[np.int64],
    pointers: NDArray[np.int64],
    account_values: NDArray[np.float64],
) -> None:
    for row in range(len(ticks)):
        t = ticks[row]
        kernel.tick, kernel.time = t[0], t[1]
        kernel.bid, kernel.ask = quotes[row, 0], quotes[row, 1]
        kernel.structure_buy, kernel.structure_sell = quotes[row, 2], quotes[row, 3]
        kernel.multiplier, kernel.margin, kernel.entry_cost, kernel.exit_cost, kernel.min_stop = economics[row]
        kernel.accept = acceptance[row]
        kernel.ordinal, kernel.phase = 0, 1
        kernel.preclose = int(t[6] >= 0 and kernel.p["session_mode"] != 0 and t[1] >= t[7] and t[1] < t[6])
        if kernel.preclose:
            if kernel.cutoff_key != t[6]:
                kernel.cutoff_key = t[6]
                for j in kernel.active_cycles:
                    kernel.end_cycle(j, 3)
                for k in kernel.active:
                    if kernel.oi[k][0] == 0:
                        kernel.cancel(k, 3)
            for h in range(len(kernel.active) - 1, -1, -1):
                k = kernel.active[h]
                i = kernel.oi[k]
                if i[0] == 1 and (kernel.p["session_mode"] == 2 or i[2] == 2):
                    kernel.close(k, 3)
        kernel.phase = 2
        if kernel.bar != t[3]:
            if kernel.bar >= 0:
                kernel.hi.append(np.array([kernel.bar_high, kernel.bar_low], np.float64))
            kernel.bar_high = kernel.bar_low = kernel.bid
            for j in kernel.active_cycles:
                w = kernel.cycles[j]
                if w[4]:
                    if w[5] >= kernel.p["window_bars"]:
                        kernel.end_cycle(j, 6)
                    else:
                        w[5] += 1
        else:
            kernel.bar_high = max(kernel.bar_high, kernel.bid)
            kernel.bar_low = min(kernel.bar_low, kernel.bid)
        if kernel.day != t[2]:
            for j in kernel.active_cycles:
                kernel.end_cycle(j, 9)
            kernel.day = t[2]
            kernel.attempted = -1
            kernel.net = kernel.gross = 0.0
            kernel.locked = kernel.would_lock = 0
            has_live = False
            for k in kernel.active:
                has_live = has_live or kernel.oi[k][0] in (0, 1)
            kernel.restart = int(t[4] and not (kernel.p["allow_same_day_fresh_start"] and not has_live))
        kernel.bar = t[3]
        for h in range(pointers[row, 2], pointers[row + 1, 2]):
            w = windows[h]
            kernel.open_cycle(w[0], w[1], w[2], w[3])
        kernel.phase = 3
        if kernel.restart:
            for k in kernel.active:
                if kernel.oi[k][0] == 0:
                    kernel.cancel(k, 3)
                elif kernel.oi[k][0] == 1:
                    kernel.close(k, 3)
        else:
            kernel.phase = 4
            for k in kernel.active:
                i, f = kernel.oi[k], kernel.of[k]
                if i[0] == 0 and (kernel.ask >= f[0] if i[1] == 0 else kernel.bid <= f[0]):
                    kernel.fill(k)
                if i[0] == 1:
                    mark = kernel.bid if i[1] == 0 else kernel.ask
                    stop = mark <= f[1] if i[1] == 0 else mark >= f[1]
                    target = mark >= f[2] if i[1] == 0 else mark <= f[2]
                    if stop or target:
                        kernel.close(k, 1 if stop else 2)
            for family in range(2):
                kernel.phase = 5 + family
                for h in range(pointers[row, family], pointers[row + 1, family]):
                    c = candidates[h]
                    proceed = True
                    if family == 0:
                        for k in kernel.active:
                            i = kernel.oi[k]
                            if (
                                i[0] == 1
                                and i[6] == kernel.day
                                and i[2] == 1
                                and i[5] == c[2]
                                and i[1] != c[3]
                                and not kernel.close(k, 10)
                            ):
                                proceed = False
                                break
                    if proceed:
                        kernel.submit(c[0], c[1], c[2], c[3], family, candidate_prices[h], c[4], c[5])
                        if family == 0:
                            kernel.open_cycle(c[0], c[2], c[3], c[5])
            kernel.phase = 7
            if not kernel.locked and not kernel.preclose:
                for j in kernel.active_cycles:
                    w = kernel.cycles[j]
                    if not w[4] or w[3] != kernel.day:
                        continue
                    if not kernel.pb_allowed(w[1], w[2]):
                        kernel.end_cycle(j, 11)
                        continue
                    zr = kernel.zones[w[1]]
                    if not w[6]:
                        w[6] = int(
                            kernel.bid <= zr[1] - kernel.p["penetration"]
                            if w[2] == 0
                            else kernel.bid >= zr[0] + kernel.p["penetration"]
                        )
                    if w[6] and w[8] < 0:
                        kernel.submit(-w[0] - 2, w[0], w[1], w[2], 2, zr[1] if w[2] == 0 else zr[0], 1, kernel.bar)
                    elif w[8] >= 0 and kernel.oi[w[8]][0] != 0:
                        w[8] = -1
                        w[7] = w[9] = 0
            kernel.phase = 8
            kernel.manage()
        kernel.phase = 9
        r = kernel.risk()
        account_values[row] = np.array(
            [kernel.balance, kernel.net, kernel.gross, r[0], r[1], r[2], r[3], kernel.used(), kernel.budget()]
        )
        kernel.snapshot()
