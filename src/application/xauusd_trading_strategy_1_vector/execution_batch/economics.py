"""Validated aligned economics inputs for the compiled replay boundary."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from br_pre_commit import pandera_validate
from helper.importer import pt

from ..domain.batch_schema import StreamTimes
from ..domain.replay import LinearReplayEconomics, ReplayEconomics


@dataclass(frozen=True)
class BatchEconomics:
    """Profit multiplier, margin/lot, entry/exit cost/lot and minimum stop.

    `values` has shape (ticks, 5); the linear profit multiplier is constant to
    preserve account-currency units. `acceptance` has shape (ticks, 4) in
    SUBMIT/CLOSE/CANCEL/MODIFY order. Session end/cutoff are UTC int64 ns;
    -1 denotes no active session. No callbacks run inside the recurrence.
    """

    values: NDArray[np.float64]
    acceptance: NDArray[np.int64]
    session_end: NDArray[np.int64]
    cutoff: NDArray[np.int64]

    def validate(self, count: int) -> BatchEconomics:
        if self.values.shape != (count, 5) or self.acceptance.shape != (count, 4):
            raise ValueError("Batch economics arrays are not aligned with replay ticks")
        if self.session_end.shape != (count,) or self.cutoff.shape != (count,):
            raise ValueError("Batch session arrays are not aligned with replay ticks")
        if not np.isfinite(self.values).all() or (self.values < 0).any():
            raise ValueError("Batch economics requires finite nonnegative coefficients")
        if count and ((self.values[:, 0] <= 0).any() or np.ptp(self.values[:, 0]) != 0):
            raise ValueError("Batch profit multiplier must be positive and constant")
        if not np.isin(self.acceptance, [0, 1]).all():
            raise ValueError("Batch acceptance must contain booleans")
        return self


@pandera_validate
def prepare_economics(
    economics: ReplayEconomics, streams: pt.DataFrame[StreamTimes], preclose_minutes: float
) -> BatchEconomics:
    """Adapt explicit linear assumptions or a provider's complete batch contract."""
    if type(economics) is not LinearReplayEconomics:
        prepare = getattr(economics, "prepare_batch", None)
        if prepare is None:
            raise ValueError(
                "Replay economics requires prepare_batch; scalar callbacks are unsupported in batch replay"
            )
        batch = prepare(streams.copy(), preclose_minutes)
        if not isinstance(batch, BatchEconomics):
            raise ValueError("prepare_batch must return BatchEconomics")
        return batch.validate(len(streams))
    count = len(streams)
    times = streams.precise_time
    ends = np.full(count, -1, dtype=np.int64)
    if economics.session_windows:
        # Windows are configuration entities; vector masks retain scalar first-match order.
        for start, end in economics.session_windows:
            mask = (ends < 0) & times.ge(start).to_numpy() & times.lt(end).to_numpy()
            ends[mask] = pd.Timestamp(end).value
    else:
        utc_days = times.dt.strftime("%Y-%m-%d")
        missing = set(utc_days.unique()) - economics.sessions.keys()
        if missing:
            raise ValueError(f"Replay session calendar is missing UTC days: {sorted(missing)}")
        mapped = pd.to_datetime(utc_days.map(economics.sessions), utc=True).astype("datetime64[ns, UTC]")
        starts = mapped.dt.normalize()
        valid = times.ge(starts) & times.lt(mapped)
        ends[valid] = mapped.loc[valid].astype("int64")
    cutoff = ends - max(1, int(preclose_minutes * 60 + 0.5)) * 1_000_000_000
    cutoff[ends < 0] = -1
    values = np.broadcast_to(
        np.array(
            [
                economics.cash_per_price_unit_per_lot,
                economics.margin_per_lot,
                economics.entry_cost_per_lot,
                economics.exit_cost_per_lot,
                economics.minimum_stop_distance,
            ],
            dtype=np.float64,
        ),
        (count, 5),
    ).copy()
    return BatchEconomics(values, np.ones((count, 4), dtype=np.int64), ends, cutoff).validate(count)
