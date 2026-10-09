"""Batched replay zones reconstruction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from br_pre_commit import pandera_validate
from helper.importer import pt

from ..domain.execution_schema import ZoneEvents
from .adapter import BatchReplay


@pandera_validate
def normalize_zones(self: BatchReplay, zones: pt.DataFrame[ZoneEvents]) -> None:
    p = self.config.inputs
    z = zones.copy()
    z["_key"] = z.broker_day + "|" + z.zone_id
    if z._key.duplicated().any():
        raise ValueError("Zone identity must be unique within a broker day")
    if not self.zone_table.empty:
        overlap = z.set_index("_key").index.intersection(self.zone_table.index)
        if len(overlap):
            prior = self.zone_table.loc[overlap, ["low", "high", "priority"]]
            now = z.set_index("_key").loc[overlap, ["low", "high", "priority"]]
            if not np.array_equal(prior.to_numpy(), now.to_numpy()):
                raise ValueError("Zone definitions changed within a replay broker day")
    fresh = z.loc[~z._key.isin(self.zone_keys)].set_index("_key")
    self.zone_table = pd.concat([self.zone_table, fresh])
    self.zone_keys = self.zone_table.index
    z = self.zone_table.copy()
    group = z.groupby("broker_day", sort=False)
    previous_high = group.high.shift().fillna(-1)
    next_low = group.low.shift(-1).fillna(-1)
    buy_space = (next_low - z.high).clip(lower=0).where(next_low.ge(0), np.finfo(float).max)
    sell_space = (z.low - previous_high).clip(lower=0).where(previous_high.ge(0), np.finfo(float).max)
    high = z.priority.eq(1)
    if p.explicit_controls:
        reversal_limit = np.where(high, p.high_reversal_max, int(not p.reversal_high_only))
        pb_limit = np.where(high, p.high_pullback_max or -1, p.normal_pullback_max)
        pb_enable = p.enable_pullback & np.where(high, p.high_pullback, p.normal_pullback)
        pb_buy = pb_enable & buy_space.ge(p.pullback_min_space)
        pb_sell = pb_enable & sell_space.ge(p.pullback_min_space)
        r_enable = p.enable_reversal & (high | (not p.reversal_high_only))
        r_buy = r_enable & (~high | buy_space.ge(p.high_reversal_min_space))
        r_sell = r_enable & (~high | sell_space.ge(p.high_reversal_min_space))
    else:
        reversal_limit = np.where(
            high,
            0
            if p.legacy_profile == 1
            else 1
            if p.legacy_profile == 2
            else 2
            if p.legacy_profile
            else p.high_reversal_max,
            0 if p.legacy_profile else 1,
        )
        pb_limit = np.where(high | (p.legacy_profile == 0), -1, 1)
        pb_buy = (p.legacy_profile == 0) | buy_space.ge(15)
        pb_sell = (p.legacy_profile == 0) | sell_space.ge(15)
        r_buy = (p.legacy_profile == 0) | (
            (p.legacy_profile != 1) & high & ((p.legacy_profile != 4) | buy_space.ge(15))
        )
        r_sell = (p.legacy_profile == 0) | (
            (p.legacy_profile != 1) & high & ((p.legacy_profile != 4) | sell_space.ge(15))
        )
    self.days = self.days.append(pd.Index(z.broker_day.unique()).difference(self.days, sort=False))
    array = np.column_stack(
        [
            z.low,
            z.high,
            z.priority,
            reversal_limit,
            pb_limit,
            pb_buy,
            pb_sell,
            r_buy,
            r_sell,
            previous_high,
            next_low,
            self.days.get_indexer(z.broker_day),
        ]
    )
    self.kernel.set_zones(np.ascontiguousarray(array, dtype=np.float64))
