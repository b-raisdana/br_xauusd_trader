"""Batched replay projection reconstruction."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from br_pre_commit import pandera_validate

from ..domain.batch_schema import ReplayTables
from .adapter import BatchReplay
from .table_keys import KINDS, REASONS, numeric_rows, utc


@pandera_validate
def tables(self: BatchReplay, account_values: NDArray[np.float64]) -> ReplayTables:
    k = self.kernel
    si = numeric_rows(k.si, 18, np.int64)
    sf = numeric_rows(k.sf, 13, np.float64)
    oi = numeric_rows(k.oi, 16, np.int64)
    request = np.char.add(f"REQ-{self.stream_id}-", (np.arange(len(oi)) + 1).astype(str))
    position = np.char.add(f"POS-{self.stream_id}-", (np.arange(len(oi)) + 1).astype(str))
    orders = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": si[:, 0],
            "request_id": request[si[:, 1]],
            "order_type": si[:, 15],
            "order_direction": si[:, 3],
            "order_status": si[:, 2],
            "entry_price": sf[:, 0],
            "stop_loss": sf[:, 1],
            "take_profit": sf[:, 2],
            "order_time": utc(si[:, 10]),
            "fill_price": sf[:, 5],
            "close_price": sf[:, 6],
            "candidate_id": self.candidate_ids(si[:, 5]),
            "parent_breakout_id": self.identities.take(si[:, 6]).to_numpy(),
        }
    )
    has_fill = si[:, 11] >= 0
    p = si[has_fill]
    v = sf[has_fill]
    positions = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": p[:, 0],
            "position_id": position[p[:, 1]],
            "position_direction": p[:, 3],
            "position_size": self.config.inputs.volume,
            "position_entry_price": v[:, 5],
            "position_current_price": v[:, 11],
            "position_unrealized_pnl": v[:, 12],
            "position_realized_pnl": v[:, 9],
            "position_status": p[:, 2],
            "position_time": utc(p[:, 11]),
            "position_close_time": utc(p[:, 12]),
            "stop_loss": v[:, 1],
            "take_profit": v[:, 2],
        }
    )
    ei = numeric_rows(k.ei, 7, np.int64)
    ef = numeric_rows(k.ef, 9, np.float64)
    events = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": ei[:, 0],
            "event_ordinal": ei[:, 1],
            "phase": ei[:, 2],
            "request_id": request[ei[:, 3]],
            "event": KINDS[ei[:, 4]],
            "time": utc(ei[:, 6]),
            "reason": REASONS[ei[:, 5]],
        }
    )
    selected = ei[:, 4] == 1
    e, f = ei[selected], ef[selected]
    fills = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": e[:, 0],
            "event_ordinal": e[:, 1],
            "request_id": request[e[:, 3]],
            "position_id": position[e[:, 3]],
            "position_direction": oi[e[:, 3], 1],
            "fill_time": utc(e[:, 6]),
            "fill_price": f[:, 4],
            "fill_side": np.where(oi[e[:, 3], 1] == 0, "ask", "bid"),
            "volume": self.config.inputs.volume,
            "cost": f[:, 7],
            "vectorbt_size": self.config.inputs.volume * k.multiplier,
        }
    )
    selected = ei[:, 4] == 2
    e, f = ei[selected], ef[selected]
    closes = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": e[:, 0],
            "event_ordinal": e[:, 1],
            "request_id": request[e[:, 3]],
            "position_id": position[e[:, 3]],
            "position_direction": oi[e[:, 3], 1],
            "close_time": utc(e[:, 6]),
            "close_price": f[:, 5],
            "close_reason": REASONS[e[:, 5]],
            "realized_pnl": f[:, 6],
            "exit_cost": f[:, 8],
        }
    )
    r = numeric_rows(k.ri, 3, np.int64)
    rejections = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": r[:, 0],
            "candidate_id": self.candidate_ids(r[:, 1]),
            "rejection_code": r[:, 2],
        }
    )
    rejections.insert(2, "rejection_ordinal", rejections.groupby("stream_tick", sort=False).cumcount())
    e, f = ei[np.isin(ei[:, 4], [5, 8])], ef[np.isin(ei[:, 4], [5, 8])]
    self.modifications = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": e[:, 0],
            "event_ordinal": e[:, 1],
            "request_id": request[e[:, 3]],
            "event": KINDS[e[:, 4]],
            "time": utc(e[:, 6]),
            "accepted": e[:, 4] == 5,
            "previous_stop_loss": f[:, 0],
            "requested_stop_loss": f[:, 1],
            "resulting_stop_loss": f[:, 2],
            "take_profit": f[:, 3],
        }
    )
    cr = numeric_rows(k.ri, 16, np.int64)
    self.cycles = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": cr[:, 1],
            "cycle_ordinal": cr[:, 2],
            "cycle_id": np.char.add(f"CYCLE-{self.stream_id}-", cr[:, 2].astype(str)),
            "parent_breakout_id": self.identities.take(cr[:, 3]).to_numpy(),
            "zone_id": self.zone_table.zone_id.iloc[cr[:, 4]].to_numpy(),
            "direction": cr[:, 5],
            "bar_offset": cr[:, 8],
            "active": cr[:, 7].astype(bool),
            "penetration_latched": cr[:, 9].astype(bool),
            "pending_active": cr[:, 10].astype(bool),
            "sequence": np.zeros(len(cr), dtype=np.int64),
            "breakout_bar_time": utc(cr[:, 14]),
            "broker_day": self.days.take(cr[:, 6]).to_numpy(),
            "order_ticket": np.where(cr[:, 11] >= 0, request[np.maximum(cr[:, 11], 0)] if len(request) else "", ""),
            "waiting_logged": cr[:, 12].astype(bool),
            "risk_waiting_logged": cr[:, 13].astype(bool),
            "reason": REASONS[cr[:, 15]],
        }
    )
    from .audit_projection import audit_tables

    audit_tables(self, account_values, request, oi)
    from ..domain.execution_schema import (
        AccountSnapshots,
        ActionEvents,
        CloseEvents,
        ExecutionEvents,
        FeedbackEvents,
        FillEvents,
        ModificationEvents,
        OrderEvents,
        PositionSnapshots,
        PullbackCycleSnapshots,
        RejectionEvents,
    )

    self.accounts = AccountSnapshots.validate(self.accounts)
    self.actions = ActionEvents.validate(self.actions)
    self.feedback = FeedbackEvents.validate(self.feedback)
    self.modifications = ModificationEvents.validate(self.modifications)
    self.cycles = PullbackCycleSnapshots.validate(self.cycles)
    return tuple(
        schema.validate(table)
        for schema, table in zip(
            (OrderEvents, FillEvents, CloseEvents, PositionSnapshots, ExecutionEvents, RejectionEvents),
            (orders, fills, closes, positions, events, rejections),
            strict=True,
        )
    )
