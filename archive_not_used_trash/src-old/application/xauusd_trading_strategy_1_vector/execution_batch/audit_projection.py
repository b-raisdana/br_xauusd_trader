"""Primitive account, action and execution-feedback output projection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from numpy.typing import NDArray

if TYPE_CHECKING:
    from .adapter import BatchReplay


from .table_keys import numeric_rows, utc


def audit_tables(
    self: BatchReplay, account_values: NDArray[np.float64], request: NDArray[np.str_], oi: NDArray[np.int64]
) -> None:
    k = self.kernel
    ai = numeric_rows(k.ci, 7, np.int64)
    self.accounts = pd.DataFrame(
        account_values,
        columns=[
            "account_balance",
            "daily_net_realized_pnl",
            "daily_gross_loss",
            "open_risk",
            "pending_risk",
            "open_count",
            "free_margin",
            "risk_used",
            "risk_budget",
        ],
    )
    self.accounts.insert(0, "stream_tick", ai[:, 0])
    self.accounts.insert(0, "stream_id", self.stream_id)
    self.accounts["time"] = utc(ai[:, 1])
    self.accounts["daily_loss_locked"] = ai[:, 3].astype(bool)
    self.accounts["operational_locked"] = ai[:, 4].astype(bool)
    self.accounts["daily_would_trigger_logged"] = ai[:, 5].astype(bool)
    self.accounts["attempted_bar"] = utc(ai[:, 6])
    action_i = numeric_rows(k.ai, 7, np.int64)
    action_f = numeric_rows(k.af, 4, np.float64)
    self.actions = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": action_i[:, 0],
            "request_id": request[action_i[:, 1]],
            "candidate_id": self.candidate_ids(action_i[:, 2]),
            "parent_breakout_id": self.identities.take(action_i[:, 3]).to_numpy(),
            "bar_time": utc(action_i[:, 4]),
            "accepted": action_i[:, 5].astype(bool),
            "phase": action_i[:, 6],
            "direction": oi[action_i[:, 1], 1],
            "order_type": oi[action_i[:, 1], 13],
            "entry_price": action_f[:, 0],
            "stop_loss": action_f[:, 1],
            "take_profit": action_f[:, 2],
            "volume": action_f[:, 3],
        }
    )
    self.actions.insert(2, "action_ordinal", self.actions.groupby("stream_tick", sort=False).cumcount())
    feedback_i = numeric_rows(k.fi, 6, np.int64)
    self.feedback = pd.DataFrame(
        {
            "stream_id": self.stream_id,
            "stream_tick": feedback_i[:, 0],
            "zone_id": self.zone_table.zone_id.iloc[feedback_i[:, 1]].to_numpy(),
            "direction": feedback_i[:, 2],
            "fill_count": feedback_i[:, 3],
            "pending_active": feedback_i[:, 4].astype(bool),
            "filled": feedback_i[:, 5].astype(bool),
        }
    )
    self.feedback.insert(2, "feedback_ordinal", self.feedback.groupby("stream_tick", sort=False).cumcount())
