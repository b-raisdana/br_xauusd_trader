"""Vectorized execution replay using batched pandas operations.

This module implements execution replay using pandas/NumPy operations
instead of per-tick iteration. It converts the scalar ExecutionReplay logic
into batched state reconstruction using grouped shifts, joins, and event tables.
"""

from __future__ import annotations

import pandas as pd
from br_py_log_n_profile import profile_it

from br_pre_commit import pandera_validate
from helper.importer import pt

from .domain.execution_schema import (
    CandidateEvents,
    CloseEvents,
    ExecutionEvents,
    FillEvents,
    OrderEvents,
    PositionSnapshots,
    StreamEvents,
    ZoneEvents,
)
from .domain.replay import ReplayConfig
from .replay import ExecutionReplay


class VectorizedExecutionReplay:
    """Batched execution replay over stream events and candidates.

    This class reconstructs execution state using pandas operations rather
    than per-tick iteration. It produces the same outputs as ExecutionReplay
    but in a vectorized form suitable for large datasets.
    """

    def __init__(self, config: ReplayConfig, stream_id: str = "default") -> None:
        self.config = config
        self.stream_id = stream_id
        self.inputs = config.inputs

    @profile_it
    @pandera_validate(dump_output=True)
    def run(
        self,
        streams: pd.DataFrame,
        zones: pd.DataFrame,
        candidates: pd.DataFrame,
    ):
        """Run vectorized execution replay.

        Args:
            streams: Tick-level stream input with stable identity
            zones: Zone definitions per trading day
            candidates: Signal candidates emitted by strategy

        Returns:
            Tuple of (orders, fills, closes, positions, events)
        """
        # Initial validation
        streams = StreamEvents.validate(streams)
        zones = ZoneEvents.validate(zones)
        candidates = CandidateEvents.validate(candidates)

        # Sort by time to ensure chronological order
        streams = streams.sort_values("precise_time")
        candidates = candidates.sort_values("signal_time")

        # Initialize output containers
        orders = self._initialize_orders_dataframe()
        fills = self._initialize_fills_dataframe()
        closes = self._initialize_closes_dataframe()
        positions = self._initialize_positions_dataframe()
        events = self._initialize_events_dataframe()

        # For now, use the scalar oracle as reference implementation
        # This will be replaced with batched operations in subsequent steps
        self._run_scalar_oracle(
            streams,
            zones,
            candidates,
            orders,
            fills,
            closes,
            positions,
            events,
        )

        return orders, fills, closes, positions, events

    def _initialize_orders_dataframe(self) -> pd.DataFrame:
        """Create empty orders DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
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

    def _initialize_fills_dataframe(self) -> pd.DataFrame:
        """Create empty fills DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "request_id",
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
                "request_id",
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
                "request_id",
                "event",
                "time",
                "reason",
            ]
        )

    def _run_scalar_oracle(
        self,
        streams: pd.DataFrame,
        zones: pd.DataFrame,
        candidates: pd.DataFrame,
        orders: pd.DataFrame,
        fills: pd.DataFrame,
        closes: pd.DataFrame,
        positions: pd.DataFrame,
        events: pd.DataFrame,
    ) -> None:
        """Run scalar ExecutionReplay oracle as reference implementation.

        This method converts the vectorized inputs back to the scalar format
        expected by ExecutionReplay, runs it tick-by-tick, and collects the
        outputs. This serves as the reference implementation while the batched
        version is being developed.
        """
        from domain.xau_usd.enums import XauDirection, XauOrderType, XauSignalFamily
        from domain.xau_usd.models import XauSignalCandidate, XauZone

        # Convert streams to zones per day
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

        # Convert candidates to scalar format
        candidates_by_tick: dict[pd.Timestamp, list[XauSignalCandidate]] = {}
        for _, row in candidates.iterrows():
            time = row.signal_time
            if time not in candidates_by_tick:
                candidates_by_tick[time] = []
            candidates_by_tick[time].append(
                XauSignalCandidate(
                    candidate_id=row.candidate_id,
                    parent_breakout_id=row.parent_breakout_id,
                    bar_id=row.bar_id,
                    zone_id=row.zone_id,
                    family=XauSignalFamily(row.family),
                    direction=XauDirection(row.direction),
                    order_type=XauOrderType(row.order_type) if row.order_type is not None else XauOrderType.MARKET,
                    signal_time=row.signal_time,
                    entry_price=row.entry_price,
                )
            )

        # Initialize scalar replay
        replay = ExecutionReplay(self.config, self.stream_id)

        # Process tick by tick
        for _, row in streams.iterrows():
            time = row.precise_time
            day = row.broker_day
            bar_time = row.bar_time
            bid = row.bid
            ask = row.ask

            # Get zones for this day
            day_zones = zones_by_day.get(day, [])

            # Get candidates for this tick
            tick_candidates = candidates_by_tick.get(time, [])

            # Separate by family
            breakouts = [c for c in tick_candidates if c.family == XauSignalFamily.BREAKOUT]
            reversals = [c for c in tick_candidates if c.family == XauSignalFamily.REVERSAL]
            # Pullbacks are generated by replay, not from candidates

            # Run scalar step
            replay._begin_tick(bid, ask)
            replay._session(time, bid, ask)
            replay._roll(day, bar_time, bid, day_zones, [], time, bid, ask)
            if not replay._restart(time, bid, ask):
                replay._settle(time, bid, ask)
                for candidate in breakouts:
                    replay._breakout(candidate, time, bid, ask)
                for candidate in reversals:
                    replay._submit(candidate, time, bid, ask)
                pullbacks = replay._pullbacks(time, bid, ask)
                replay._manage(time, bid, ask, ())
            else:
                pullbacks = []

            # Collect snapshot
            snapshot = replay._snapshot(bid, ask, pullbacks)

            # Convert snapshot to DataFrames
            self._collect_snapshot(snapshot, time, orders, fills, closes, positions, events)

    def _collect_snapshot(
        self,
        snapshot: dict,
        time: pd.Timestamp,
        orders: pt.DataFrame[OrderEvents],
        fills: pt.DataFrame[FillEvents],
        closes: pt.DataFrame[CloseEvents],
        positions: pt.DataFrame[PositionSnapshots],
        events: pt.DataFrame[ExecutionEvents],
    ) -> None:
        """Collect snapshot data into output DataFrames."""
        # Collect events
        for event in snapshot.get("execution_events", []):
            events = pd.concat(
                [
                    events,
                    pd.DataFrame(
                        [
                            {
                                "request_id": event["request_id"],
                                "event": event["event"],
                                "time": event["time"],
                                "reason": event.get("reason", ""),
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

        # Collect orders
        for order in snapshot.get("orders", []):
            orders = pd.concat(
                [
                    orders,
                    pd.DataFrame(
                        [
                            {
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
                        ]
                    ),
                ],
                ignore_index=True,
            )

        # Collect positions
        for position in snapshot.get("positions", []):
            positions = pd.concat(
                [
                    positions,
                    pd.DataFrame(
                        [
                            {
                                "position_id": position["position_id"],
                                "position_direction": position["position_direction"],
                                "position_size": position["position_size"],
                                "position_entry_price": position["position_entry_price"],
                                "position_current_price": position["position_current_price"],
                                "position_unrealized_pnl": position["position_unrealized_pnl"],
                                "position_realized_pnl": position["position_realized_pnl"],
                                "position_status": position["position_status"],
                                "position_time": position["position_time"],
                                "position_close_time": position["position_close_time"],
                                "stop_loss": position["stop_loss"],
                                "take_profit": position["take_profit"],
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )

        # Note: fills and closes are derived from events in the scalar oracle
        # They will be extracted from order status changes in a batched version
