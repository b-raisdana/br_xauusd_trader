"""Compiled replay protection operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .kernel import ReplayKernel


import numpy as np
from numba import njit

from .prices import decimal_price


@njit(cache=False)
def structure(self: ReplayKernel, buy: bool) -> float:
    prepared = self.structure_buy if buy else self.structure_sell
    if np.isfinite(prepared):
        return prepared
    found = 0
    first = 0.0
    n = len(self.hi)
    for h in range(n - 2, max(-1, n - 101), -1):
        if h < 1:
            break
        col = 1 if buy else 0
        current, newer, older = self.hi[h][col], self.hi[h + 1][col], self.hi[h - 1][col]
        strict = current < newer and current < older if buy else current > newer and current > older
        if strict:
            if found == 0:
                first, found = current, 1
            else:
                return first if (first > current if buy else first < current) else 0.0
    return 0.0


@njit(cache=False)
def manage(self: ReplayKernel) -> None:
    if not self.p["profit_protection"]:
        return
    for k in self.active:
        i, f = self.oi[k], self.of[k]
        if i[0] != 1 or f[4] <= 0:
            continue
        buy = i[1] == 0
        favorable = max(0.0, self.bid - f[0] if buy else f[0] - self.ask)
        if favorable >= 2 * f[4]:
            i[11] = 3
        elif favorable >= 1.5 * f[4]:
            i[11] = max(i[11], 2)
        elif favorable >= f[4]:
            i[11] = max(i[11], 1)
        desired = self.structure(buy) if i[11] >= 3 else 0.0
        epsilon = 10.0 ** (-self.p["digits"]) * 0.1
        if desired and not (desired > f[1] + epsilon if buy else desired < f[1] - epsilon):
            desired = 0.0
        if not desired and i[11] >= 2:
            desired = f[0] + (0.5 * f[4] if buy else -0.5 * f[4])
        if not desired and i[11] >= 1:
            offset = max(f[7] + f[8], 0.0) / (self.p["volume"] * self.multiplier)
            desired = f[5] + (offset if buy else -offset)
        if not desired:
            continue
        desired = decimal_price(desired, int(self.p["digits"]))
        improves = f[1] <= 0 or (desired > f[1] + epsilon if buy else desired < f[1] - epsilon)
        if not improves:
            continue
        previous = f[1]
        distance = self.bid - desired if buy else desired - self.ask
        accepted = distance > 0 and distance >= self.min_stop and self.accept[3] != 0
        f[10] = desired
        if accepted:
            f[1], f[10] = desired, 0.0
        self.event(k, 5 if accepted else 8, 0, previous, desired)
