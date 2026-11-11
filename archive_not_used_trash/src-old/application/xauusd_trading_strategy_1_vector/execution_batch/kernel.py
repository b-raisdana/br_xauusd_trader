"""Typed causal recurrence over precomputed arrays; no Python tick callbacks.
Column layouts are documented beside allocations. All timestamps remain int64 ns.
Only active orders/cycles are scanned; terminated history is never a tick Cartesian product.
"""

from __future__ import annotations

import numpy as np
from numba import float64, int64, types
from numba.experimental import jitclass
from numba.typed import List
from numpy.typing import NDArray

from .admission import submit as submit_impl
from .lifecycle import cancel as cancel_impl
from .lifecycle import close as close_impl
from .lifecycle import end_cycle as end_cycle_impl
from .lifecycle import event as event_impl
from .lifecycle import feedback as feedback_impl
from .lifecycle import fill as fill_impl
from .lifecycle import open_cycle as open_cycle_impl
from .lifecycle import pb_allowed as pb_allowed_impl
from .prices import decimal_price as decimal_price
from .protection import manage as manage_impl
from .protection import structure as structure_impl
from .risk_state import budget as budget_impl
from .risk_state import daily_guard as daily_guard_impl
from .risk_state import enforce_pending as enforce_pending_impl
from .risk_state import profit as profit_impl
from .risk_state import risk as risk_impl
from .risk_state import used as used_impl
from .scan import scan as scan
from .snapshots import snapshot as snapshot_impl

IROW = types.Array(int64, 1, "C")
FROW = types.Array(float64, 1, "C")
CFG = types.DictType(types.unicode_type, float64)
SPEC = [
    ("p", CFG),
    ("oi", types.ListType(IROW)),
    ("of", types.ListType(FROW)),
    ("cycles", types.ListType(IROW)),
    ("cycle_previous", types.ListType(IROW)),
    ("active", types.ListType(int64)),
    ("active_cycles", types.ListType(int64)),
    ("ei", types.ListType(IROW)),
    ("ef", types.ListType(FROW)),
    ("si", types.ListType(IROW)),
    ("sf", types.ListType(FROW)),
    ("ci", types.ListType(IROW)),
    ("ri", types.ListType(IROW)),
    ("ai", types.ListType(IROW)),
    ("af", types.ListType(FROW)),
    ("fi", types.ListType(IROW)),
    ("hi", types.ListType(FROW)),
    ("zones", float64[:, ::1]),
    ("counts", int64[:, ::1]),
    ("balance", float64),
    ("net", float64),
    ("gross", float64),
    ("day", int64),
    ("bar", int64),
    ("attempted", int64),
    ("tick", int64),
    ("time", int64),
    ("ordinal", int64),
    ("phase", int64),
    ("cutoff_key", int64),
    ("locked", int64),
    ("restart", int64),
    ("preclose", int64),
    ("would_lock", int64),
    ("bid", float64),
    ("ask", float64),
    ("bar_high", float64),
    ("bar_low", float64),
    ("multiplier", float64),
    ("entry_cost", float64),
    ("exit_cost", float64),
    ("margin", float64),
    ("min_stop", float64),
    ("accept", int64[::1]),
    ("structure_buy", float64),
    ("structure_sell", float64),
]


@jitclass(SPEC)
class ReplayKernel:
    def __init__(self, p: dict[str, float]) -> None:
        self.p = p
        self.oi = List.empty_list(IROW)
        self.of = List.empty_list(FROW)
        self.cycles = List.empty_list(IROW)
        self.cycle_previous = List.empty_list(IROW)
        self.active = List.empty_list(int64)
        self.active_cycles = List.empty_list(int64)
        self.ei = List.empty_list(IROW)
        self.ef = List.empty_list(FROW)
        self.si = List.empty_list(IROW)
        self.sf = List.empty_list(FROW)
        self.ci = List.empty_list(IROW)
        self.ri = List.empty_list(IROW)
        self.ai = List.empty_list(IROW)
        self.af = List.empty_list(FROW)
        self.fi = List.empty_list(IROW)
        self.hi = List.empty_list(FROW)
        self.zones = np.empty((0, 12))
        self.counts = np.empty((0, 2), dtype=np.int64)
        self.balance = p["initial_balance"]
        self.net = self.gross = 0.0
        self.day = self.bar = self.attempted = -1
        self.tick = self.time = self.ordinal = self.phase = 0
        self.cutoff_key = -1
        self.locked = self.restart = self.preclose = self.would_lock = 0
        self.bid = self.ask = self.bar_high = self.bar_low = 0.0
        self.multiplier = self.entry_cost = self.exit_cost = self.margin = self.min_stop = 0.0
        self.accept = np.ones(4, dtype=np.int64)
        self.structure_buy = self.structure_sell = np.nan

    def set_zones(self, zones: NDArray[np.float64]) -> None:
        counts = np.zeros((len(zones), 2), dtype=np.int64)
        counts[: len(self.counts)] = self.counts
        self.counts = counts
        self.zones = zones

    def clear_outputs(self) -> None:
        self.ei.clear()
        self.ef.clear()
        self.si.clear()
        self.sf.clear()
        self.ci.clear()
        self.ri.clear()
        self.ai.clear()
        self.af.clear()
        self.fi.clear()

    def profit(self, side: int, entry: float, price: float) -> float:
        return profit_impl(self, side, entry, price)

    def risk(self) -> tuple[float, float, int, float]:
        return risk_impl(self)

    def budget(self) -> float:
        return budget_impl(self)

    def used(self) -> float:
        return used_impl(self)

    def event(self, k: int, kind: int, reason: int, previous: float = 0.0, requested: float = 0.0) -> None:
        return event_impl(self, k, kind, reason, previous, requested)

    def feedback(self, k: int, filled: int) -> None:
        return feedback_impl(self, k, filled)

    def cancel(self, k: int, reason: int) -> None:
        return cancel_impl(self, k, reason)

    def end_cycle(self, j: int, reason: int) -> None:
        return end_cycle_impl(self, j, reason)

    def daily_guard(self) -> None:
        return daily_guard_impl(self)

    def enforce_pending(self) -> None:
        return enforce_pending_impl(self)

    def close(self, k: int, reason: int) -> bool:
        return close_impl(self, k, reason)

    def fill(self, k: int) -> None:
        return fill_impl(self, k)

    def pb_allowed(self, z: int, side: int) -> bool:
        return pb_allowed_impl(self, z, side)

    def open_cycle(self, parent: int, z: int, side: int, born: int) -> None:
        return open_cycle_impl(self, parent, z, side, born)

    def submit(
        self,
        candidate: int,
        parent: int,
        z: int,
        side: int,
        family: int,
        entry: float,
        order_type: int,
        candidate_bar: int,
    ) -> bool:
        return submit_impl(self, candidate, parent, z, side, family, entry, order_type, candidate_bar)

    def structure(self, buy: bool) -> float:
        return structure_impl(self, buy)

    def manage(self) -> None:
        return manage_impl(self)

    def snapshot(self) -> None:
        return snapshot_impl(self)
