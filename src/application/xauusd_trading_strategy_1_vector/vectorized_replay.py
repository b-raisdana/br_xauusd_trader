"""Adapt normalized native event tables to the causal execution state machine."""

from __future__ import annotations

import pandas as pd
from br_py_log_n_profile import profile_it

from br_pre_commit import pandera_validate
from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily
from domain.xau_usd.models import XauPullbackWindowState, XauSignalCandidate, XauZone

from .domain.columnar import WindowTable
from .domain.execution_schema import CandidateEvents, StreamEvents, ZoneEvents
from .domain.replay import ReplayConfig
from .replay import ExecutionReplay


class VectorizedExecutionReplay:
    """Adapt normalized native stream, signal and window events to replay state."""

    def __init__(self, config: ReplayConfig, stream_id: str = "default") -> None:
        self.config = config
        self.stream_id = stream_id
        self.inputs = config.inputs
        self.replay = ExecutionReplay(config, stream_id)

    @profile_it
    @pandera_validate(dump_output=True)
    def run(
        self,
        streams: pd.DataFrame,
        zones: pd.DataFrame,
        candidates: pd.DataFrame,
        windows: pd.DataFrame | None = None,
    ):
        """Replay one stream while matching candidate and window events by tick ordinal.

        Args:
            streams: Ordered tick-level stream input with stable identity and M15 opens
            zones: Zone definitions per broker day in native ordering
            candidates: Native candidate events keyed by stream tick
            windows: Native pullback-window opening events keyed by stream tick

        Returns:
            Tuple of (orders, fills, closes, positions, events)
        """
        streams = StreamEvents.validate(streams)
        zones = ZoneEvents.validate(zones)
        candidates = CandidateEvents.validate(candidates)

        streams = streams.sort_values(["precise_time", "stream_tick"], kind="stable")
        candidates = candidates.sort_values("stream_tick", kind="stable")
        if windows is None:
            windows = pd.DataFrame()
        elif not windows.empty:
            windows = WindowTable.validate(windows)
        stream_ids = streams.stream_id.unique()
        if len(stream_ids) > 1 or (len(stream_ids) == 1 and stream_ids[0] != self.stream_id):
            raise ValueError(f"Replay input must contain only stream {self.stream_id!r}")
        if streams.stream_tick.duplicated().any():
            raise ValueError("Replay stream_tick values must be unique within a stream partition")
        if len(streams) > 1 and not streams.stream_tick.diff().iloc[1:].gt(0).all():
            raise ValueError("Replay stream_tick values must increase with stream time")
        available_ticks = set(streams.stream_tick)
        if not candidates.stream_tick.isin(available_ticks).all():
            raise ValueError("Candidate events reference stream ticks outside this replay partition")
        if not windows.empty and not windows.stream_tick.isin(available_ticks).all():
            raise ValueError("Window events reference stream ticks outside this replay partition")
        if (
            not windows.empty
            and not windows.broker_day.eq(
                streams.set_index("stream_tick").broker_day.reindex(windows.stream_tick).to_numpy()
            ).all()
        ):
            raise ValueError("Window broker_day must match its replay stream tick")

        records: dict[str, list[dict]] = {
            key: [] for key in ("orders", "fills", "closes", "positions", "events", "rejections")
        }
        self._run_state_machine(streams, zones, candidates, windows, records)
        return tuple(
            pd.DataFrame.from_records(records[name], columns=columns)
            for name, columns in (
                ("orders", self._initialize_orders_dataframe().columns),
                ("fills", self._initialize_fills_dataframe().columns),
                ("closes", self._initialize_closes_dataframe().columns),
                ("positions", self._initialize_positions_dataframe().columns),
                ("events", self._initialize_events_dataframe().columns),
                ("rejections", self._initialize_rejections_dataframe().columns),
            )
        )

    def _initialize_orders_dataframe(self) -> pd.DataFrame:
        """Create empty orders DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "stream_id",
                "stream_tick",
                "request_id",
                "order_type",
                "order_direction",
                "order_status",
                "entry_price",
                "stop_loss",
                "take_profit",
                "order_time",
                "fill_price",
                "close_price",
                "candidate_id",
                "parent_breakout_id",
            ]
        )

    def _initialize_rejections_dataframe(self) -> pd.DataFrame:
        """Create empty entry rejections DataFrame with correct schema."""
        return pd.DataFrame(columns=["stream_id", "stream_tick", "rejection_ordinal", "candidate_id", "rejection_code"])

    def _initialize_fills_dataframe(self) -> pd.DataFrame:
        """Create empty fills DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "stream_id",
                "stream_tick",
                "request_id",
                "position_id",
                "position_direction",
                "fill_time",
                "fill_price",
                "fill_side",
                "volume",
                "cost",
            ]
        )

    def _initialize_closes_dataframe(self) -> pd.DataFrame:
        """Create empty closes DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "stream_id",
                "stream_tick",
                "request_id",
                "position_id",
                "position_direction",
                "close_time",
                "close_price",
                "close_reason",
                "realized_pnl",
                "exit_cost",
            ]
        )

    def _initialize_positions_dataframe(self) -> pd.DataFrame:
        """Create empty positions DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "stream_id",
                "stream_tick",
                "position_id",
                "position_direction",
                "position_size",
                "position_entry_price",
                "position_current_price",
                "position_unrealized_pnl",
                "position_realized_pnl",
                "position_status",
                "position_time",
                "position_close_time",
                "stop_loss",
                "take_profit",
            ]
        )

    def _initialize_events_dataframe(self) -> pd.DataFrame:
        """Create empty events DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "stream_id",
                "stream_tick",
                "event_ordinal",
                "request_id",
                "event",
                "time",
                "reason",
            ]
        )

    def _run_state_machine(
        self,
        streams: pd.DataFrame,
        zones: pd.DataFrame,
        candidates: pd.DataFrame,
        windows: pd.DataFrame,
        records: dict[str, list[dict]],
    ) -> None:
        """Apply the established causal transition order to one market stream."""
        zones_by_day: dict[str, list[XauZone]] = {}
        for day, day_zones in zones.groupby("broker_day"):
            zones_by_day[day] = [
                XauZone(
                    row.zone_id,
                    row.low,
                    row.high,
                    row.priority,
                )
                for _, row in day_zones.iterrows()
            ]

        candidates_by_tick: dict[int, list[XauSignalCandidate]] = {}
        for row in candidates.itertuples(index=False):
            tick = int(row.stream_tick)
            if tick not in candidates_by_tick:
                candidates_by_tick[tick] = []
            candidates_by_tick[tick].append(
                XauSignalCandidate(
                    candidate_id=row.candidate_id,
                    parent_breakout_id=row.parent_breakout_id,
                    bar_id=row.bar_id,
                    zone_id=row.zone_id,
                    family=XauSignalFamily(row.family),
                    direction=XauDirection(row.direction),
                    order_type=XauOrderType(row.order_type),
                    signal_time=row.signal_time.to_pydatetime(),
                    entry_price=row.entry_price,
                )
            )

        openings_by_tick: dict[int, list[XauPullbackWindowState]] = {}
        if not windows.empty:
            for row in windows.itertuples(index=False):
                openings_by_tick.setdefault(int(row.stream_tick), []).append(
                    XauPullbackWindowState(
                        parent_breakout_id=row.parent_breakout_id,
                        zone=XauZone(row.zone_id, row.zone_low, row.zone_high, row.priority),
                        direction=XauDirection(row.direction),
                        active=bool(row.active),
                        bar_offset=int(row.bar_offset),
                        penetration_latched=bool(row.penetration_latched),
                        breakout_bar_time=row.breakout_bar_time.to_pydatetime(),
                        broker_day=row.broker_day,
                    )
                )

        for row in streams.itertuples(index=False):
            time = row.precise_time
            day = row.broker_day
            bar_time = row.bar_time
            stream_tick = int(row.stream_tick)
            bid = row.bid
            ask = row.ask

            day_zones = zones_by_day.get(day, [])

            tick_candidates = candidates_by_tick.get(stream_tick, [])
            breakouts = [c for c in tick_candidates if c.family == XauSignalFamily.BREAKOUT]
            reversals = [c for c in tick_candidates if c.family == XauSignalFamily.REVERSAL]
            self.replay._begin_tick(bid, ask)
            self.replay._session(time, bid, ask)
            self.replay._roll(
                day, bar_time, row.bar_open, day_zones, openings_by_tick.get(stream_tick, []), time, bid, ask
            )
            if not self.replay._restart(time, bid, ask):
                self.replay._settle(time, bid, ask)
                for candidate in breakouts:
                    self.replay._breakout(candidate, time, bid, ask)
                for candidate in reversals:
                    self.replay._submit(candidate, time, bid, ask)
                pullbacks = self.replay._pullbacks(time, bid, ask)
                self.replay._manage(time, bid, ask, ())
            else:
                pullbacks = []
            snapshot = self.replay._snapshot(bid, ask, pullbacks)
            self._collect_snapshot(snapshot, records, stream_tick)

    def _collect_snapshot(
        self,
        snapshot: dict,
        records: dict[str, list[dict]],
        stream_tick: int,
    ) -> None:
        for event_ordinal, event in enumerate(snapshot.get("execution_events", [])):
            records["events"].append(
                {
                    "stream_id": self.stream_id,
                    "stream_tick": stream_tick,
                    "event_ordinal": event_ordinal,
                    "request_id": event["request_id"],
                    "event": event["event"],
                    "time": event["time"],
                    "reason": event.get("reason", ""),
                }
            )
            order = self.replay.orders[event["request_id"]]
            if event["event"] == "FILL":
                records["fills"].append(
                    {
                        "stream_id": self.stream_id,
                        "stream_tick": stream_tick,
                        "request_id": order.request_id,
                        "position_id": order.position_id,
                        "position_direction": int(order.direction),
                        "fill_time": order.fill_time,
                        "fill_price": order.fill_price,
                        "fill_side": "ask" if order.direction == XauDirection.BUY else "bid",
                        "volume": order.volume,
                        "cost": order.entry_cost,
                    }
                )
            elif event["event"] == "CLOSE":
                records["closes"].append(
                    {
                        "stream_id": self.stream_id,
                        "stream_tick": stream_tick,
                        "request_id": order.request_id,
                        "position_id": order.position_id,
                        "position_direction": int(order.direction),
                        "close_time": order.close_time,
                        "close_price": order.close_price,
                        "close_reason": event.get("reason", ""),
                        "realized_pnl": order.realized_pnl,
                        "exit_cost": order.exit_cost,
                    }
                )
        records["rejections"].extend(
            {
                "stream_id": self.stream_id,
                "stream_tick": stream_tick,
                "rejection_ordinal": rejection_ordinal,
                "candidate_id": candidate_id,
                "rejection_code": rejection_code,
            }
            for rejection_ordinal, (candidate_id, rejection_code) in enumerate(snapshot.get("entry_rejections", []))
        )
        records["orders"].extend(
            {
                "stream_id": self.stream_id,
                "stream_tick": stream_tick,
                "request_id": order["order_id"],
                "order_type": order["order_type"],
                "order_direction": order["order_direction"],
                "order_status": order["order_status"],
                "entry_price": order["entry_price"],
                "stop_loss": order["stop_loss"],
                "take_profit": order["take_profit"],
                "order_time": order["order_time"],
                "fill_price": order["fill_price"],
                "close_price": order["close_price"],
                "candidate_id": order["candidate_id"],
                "parent_breakout_id": order["parent_breakout_id"],
            }
            for order in snapshot.get("orders", [])
        )
        records["positions"].extend(
            {
                "stream_id": self.stream_id,
                "stream_tick": stream_tick,
                **position,
            }
            for position in snapshot.get("positions", [])
        )
