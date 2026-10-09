"""Pandas normalization and batched event reconstruction around the typed scan."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numba import types
from numba.typed import Dict
from numpy.typing import NDArray

from br_pre_commit import pandera_validate
from helper.importer import pt

from ..domain.batch_schema import CompletedCandles, ReplayTables, ReplayWindows
from ..domain.execution_schema import CandidateEvents, StreamEvents, ZoneEvents
from ..domain.replay import ReplayConfig
from .economics import prepare_economics
from .kernel import ReplayKernel, scan


class BatchReplay:
    def __init__(self, config: ReplayConfig, stream_id: str) -> None:
        import logging

        logging.getLogger("numba").setLevel(logging.WARNING)
        self.config, self.stream_id = config, stream_id
        p = Dict.empty(types.unicode_type, types.float64)
        values = config.inputs.model_dump()
        values["risk_mode"] = {"off": 0, "net": 1, "gross": 2}[values["risk_mode"]]
        values["session_mode"] = {"carry": 0, "pullback": 1, "all": 2}[values["session_mode"]]
        for key, value in values.items():
            if isinstance(value, (float, int, bool)):
                p[key] = float(value)
        p["initial_balance"] = config.initial_balance
        self.kernel = ReplayKernel(p)
        self.identities = pd.Index([""], dtype="str")
        self.days = pd.Index([], dtype="str")
        self.zone_keys = pd.Index([], dtype="str")
        self.zone_table = pd.DataFrame()
        self.cash_multiplier = None
        self.last_tick = -1
        self.last_time = -1
        self.accounts = pd.DataFrame()
        self.modifications = pd.DataFrame()
        self.cycles = pd.DataFrame()
        self.feedback = pd.DataFrame()
        self.actions = pd.DataFrame()

    def intern(self, values: pd.Series | pd.Index) -> NDArray[np.int64]:
        values = pd.Index(values, dtype="str")
        self.identities = self.identities.append(values.unique().difference(self.identities, sort=False))
        return self.identities.get_indexer(values)

    @pandera_validate
    def normalize_zones(self, zones: pt.DataFrame[ZoneEvents]) -> None:
        from .zones import normalize_zones

        return normalize_zones(self, zones)

    @pandera_validate(allow_pandas_dataframe=True)
    def run(
        self,
        streams: pt.DataFrame[StreamEvents],
        zones: pt.DataFrame[ZoneEvents],
        candidates: pt.DataFrame[CandidateEvents],
        windows: pd.DataFrame | None = None,
        candles: pd.DataFrame | None = None,
    ) -> ReplayTables:
        streams = StreamEvents.validate(streams).reset_index(drop=True)
        zones = ZoneEvents.validate(zones).reset_index(drop=True)
        candidates = CandidateEvents.validate(candidates).reset_index(drop=True)
        if candles is not None:
            candles = CompletedCandles.validate(candles.reset_index()).reset_index(drop=True)
        if len(streams) and (not streams.stream_id.eq(self.stream_id).all() or streams.stream_tick.duplicated().any()):
            raise ValueError("Replay requires unique tick identity in one stream")
        if len(streams) and (
            not streams.precise_time.is_monotonic_increasing or not streams.stream_tick.is_monotonic_increasing
        ):
            raise ValueError("Replay ticks must be chronological with increasing ordinals")
        if len(streams) and (
            streams.stream_tick.iloc[0] <= self.last_tick or streams.precise_time.iloc[0].value < self.last_time
        ):
            raise ValueError("Replay partitions must continue after previously processed ticks")
        if (
            not np.isfinite(streams[["bid", "ask", "bar_open"]].to_numpy()).all()
            or (streams.bid <= 0).any()
            or (streams.ask < streams.bid).any()
        ):
            raise ValueError("Replay requires positive finite Bid/Ask and nonnegative spread")
        self.days = self.days.append(pd.Index(streams.broker_day.unique()).difference(self.days, sort=False))
        self.normalize_zones(zones)
        positions = pd.Index(streams.stream_tick)
        cpos = positions.get_indexer(candidates.stream_tick)
        if (cpos < 0).any():
            raise ValueError("Candidate events reference stream ticks outside this replay partition")
        if windows is None:
            windows = pd.DataFrame(
                {
                    "stream_tick": pd.Series([], dtype="int64"),
                    "parent_breakout_id": pd.Series([], dtype="str"),
                    "zone_id": pd.Series([], dtype="str"),
                    "direction": pd.Series([], dtype="int64"),
                    "breakout_bar_time": pd.Series([], dtype="datetime64[ns, UTC]"),
                    "broker_day": pd.Series([], dtype="str"),
                }
            )
        # Normalize windows to match ReplayWindows schema (columns and dtypes)
        windows = ReplayWindows.validate(windows).reset_index(drop=True)
        wpos = positions.get_indexer(windows.stream_tick) if len(windows) else np.empty(0, dtype=np.int64)
        if (wpos < 0).any():
            raise ValueError("Window events reference stream ticks outside this replay partition")
        if len(windows) and not np.array_equal(windows.broker_day.to_numpy(), streams.broker_day.iloc[wpos].to_numpy()):
            raise ValueError("Window broker_day must match its replay stream tick")
        batch = prepare_economics(self.config.economics, streams, self.config.inputs.preclose_minutes)
        if len(streams):
            multiplier = float(batch.values[0, 0])
            if self.cash_multiplier is not None and multiplier != self.cash_multiplier:
                raise ValueError("Profit multiplier cannot change between replay partitions")
            self.cash_multiplier = multiplier
        self.kernel.clear_outputs()
        ticks = np.column_stack(
            [
                streams.stream_tick,
                streams.precise_time.astype("int64"),
                self.days.get_indexer(streams.broker_day),
                streams.bar_time.astype("int64"),
                streams.broker_day.isin(self.config.restart_days),
                np.zeros(len(streams), dtype=np.int64),
                batch.session_end,
                batch.cutoff,
            ]
        ).astype(np.int64)
        c = candidates.assign(_row=cpos)
        # Each phase keeps original candidate order, including duplicate timestamps.
        c = pd.concat([c.loc[c.family.eq(f)].sort_values("_row", kind="stable") for f in (0, 1)], ignore_index=True)
        pointers = np.zeros((len(streams) + 1, 3), dtype=np.int64)
        bo = c.family.eq(0).sum()
        for f in (0, 1):
            pointers[1:, f] = np.bincount(c.loc[c.family.eq(f), "_row"], minlength=len(streams)).cumsum()
        pointers[:, 1] += bo
        ci = np.column_stack(
            [
                self.intern(c.candidate_id),
                self.intern(c.parent_breakout_id),
                self.zone_keys.get_indexer(streams.broker_day.iloc[c._row].reset_index(drop=True) + "|" + c.zone_id),
                c.direction,
                c.order_type,
                pd.to_datetime(c.bar_id, format="mixed", utc=True).astype("int64"),
            ]
        ).astype(np.int64)
        wi = np.empty((0, 4), dtype=np.int64)
        if len(windows):
            w = windows.assign(_row=wpos).sort_values("_row", kind="stable")
            wi = np.column_stack(
                [
                    self.intern(w.parent_breakout_id),
                    self.zone_keys.get_indexer(w.broker_day + "|" + w.zone_id),
                    w.direction,
                    w.breakout_bar_time.astype("int64"),
                ]
            ).astype(np.int64)
            pointers[1:, 2] = np.bincount(w._row, minlength=len(streams)).cumsum()
        account_values = np.empty((len(streams), 9), dtype=np.float64)
        from .structure import structural_stops

        quotes = np.column_stack([streams[["bid", "ask"]].to_numpy(), structural_stops(streams, candles)])
        scan(
            self.kernel,
            np.ascontiguousarray(ticks),
            np.ascontiguousarray(quotes),
            np.ascontiguousarray(batch.values),
            np.ascontiguousarray(batch.acceptance, dtype=np.int64),
            np.ascontiguousarray(ci),
            c.entry_price.to_numpy(dtype=np.float64),
            np.ascontiguousarray(wi),
            pointers,
            account_values,
        )
        if len(streams):
            self.last_tick, self.last_time = int(streams.stream_tick.iloc[-1]), int(streams.precise_time.iloc[-1].value)
        return self.tables(account_values)

    def candidate_ids(self, codes: NDArray[np.int64]) -> NDArray[np.str_]:
        positive = codes >= 0
        safe = np.where(positive, codes, -codes - 2)
        base = self.identities.take(safe).to_numpy(dtype=str)
        return np.where(positive, base, np.char.add(base, ":PB"))

    @pandera_validate
    def tables(self, account_values: NDArray[np.float64]) -> ReplayTables:
        from .projection import tables

        return tables(self, account_values)
