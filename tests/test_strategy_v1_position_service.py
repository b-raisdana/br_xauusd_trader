from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from application.strategy_v1.contracts import ArtifactReference, OrderResult, StrategySnapshot
from application.strategy_v1.position_service import PositionStageService, position_state_frame
from domain.xau_usd.strategy_v1 import PositionState, PositionStatus


class _MemoryArtifactStore:
    def __init__(self, frames: dict[Path, pd.DataFrame]) -> None:
        self.frames = frames
        self.sequence = 0

    def read_frame(self, reference: ArtifactReference) -> pd.DataFrame:
        return self.frames[reference.path]

    def write_frame(self, frame: pd.DataFrame, *, schema_id: str) -> ArtifactReference:
        self.sequence += 1
        path = Path(f"memory-{self.sequence}")
        self.frames[path] = frame.copy()
        return ArtifactReference(
            path=path,
            sha256="0" * 64,
            schema_id=schema_id,
            row_count=len(frame),
            index_names=tuple(frame.index.names),
            columns=tuple(frame.columns),
        )


def _reference(name: str, frame: pd.DataFrame | None = None) -> ArtifactReference:
    return ArtifactReference(
        path=Path(name),
        sha256="0" * 64,
        schema_id="test",
        row_count=0 if frame is None else len(frame),
        index_names=("date",),
        columns=() if frame is None else tuple(frame.columns),
    )


def _execution_events(event: dict[str, str | float | datetime | None] | None = None) -> pd.DataFrame:
    columns: dict[str, list[str | float | datetime | None]] = {
        "event_id": [] if event is None else [event["event_id"]],
        "kind": [] if event is None else [event["kind"]],
        "order_id": [] if event is None else [event["order_id"]],
        "position_id": [] if event is None else [event.get("position_id")],
        "direction": [] if event is None else [event.get("direction")],
        "entry_reference": [] if event is None else [event.get("entry_reference")],
        "fill_price": [] if event is None else [event.get("fill_price")],
        "volume_lots": [] if event is None else [event.get("volume_lots")],
        "stop_loss": [] if event is None else [event.get("stop_loss")],
        "take_profit": [] if event is None else [event.get("take_profit")],
        "close_reason": [] if event is None else [event.get("close_reason")],
        "profit_before_charges_usd": [] if event is None else [event.get("profit_before_charges_usd")],
        "commission_cost_usd": [] if event is None else [event.get("commission_cost_usd")],
        "swap_pnl_usd": [] if event is None else [event.get("swap_pnl_usd")],
        "fee_cost_usd": [] if event is None else [event.get("fee_cost_usd")],
        "spread_slippage_cost_usd": [] if event is None else [event.get("spread_slippage_cost_usd")],
    }
    frame = pd.DataFrame(columns)
    for column in (
        "entry_reference",
        "fill_price",
        "volume_lots",
        "stop_loss",
        "take_profit",
        "profit_before_charges_usd",
        "commission_cost_usd",
        "swap_pnl_usd",
        "fee_cost_usd",
        "spread_slippage_cost_usd",
    ):
        frame[column] = frame[column].astype("float64")
    frame.index = pd.DatetimeIndex(
        [] if event is None else [event["event_time"]],
        tz="UTC",
        name="date",
    ).astype("datetime64[ns, UTC]")
    return frame


def _incoming(store: _MemoryArtifactStore, state: PositionState, event: pd.DataFrame, as_of: datetime) -> OrderResult:
    state_frame = position_state_frame(state, as_of)
    calendar = pd.DataFrame(
        {"session_id": ["session-1"], "broker_open": [True]},
        index=pd.DatetimeIndex([datetime(2026, 7, 29, 20, tzinfo=UTC)], name="date"),
    )
    state_ref = _reference("state", state_frame)
    event_ref = _reference("events", event)
    calendar_ref = _reference("calendar", calendar)
    generic_ref = _reference("source")
    snapshot = StrategySnapshot(
        snapshot_id="snapshot-1",
        as_of=as_of,
        symbol="XAUUSD!",
        broker="opofinance",
        ticks=generic_ref,
        candles_m5=generic_ref,
        candles_m15=generic_ref,
        zones=generic_ref,
        account_and_costs=generic_ref,
        broker_calendar=calendar_ref,
        execution_events=event_ref,
    )
    store.frames[state_ref.path] = state_frame
    store.frames[event_ref.path] = event
    store.frames[calendar_ref.path] = calendar
    return OrderResult(
        run_id="run-1",
        snapshot=snapshot,
        signal_result=generic_ref,
        orders=generic_ref,
        risk_audit=generic_ref,
        state=state_ref,
    )


def test_position_stage_emits_close_retry_from_fresh_snapshot_without_second_position():
    as_of = datetime(2026, 7, 29, 10, 5, tzinfo=UTC)
    state = PositionState(
        status=PositionStatus.CLOSE_RETRY_REQUIRED,
        order_id="order-1",
        position_id="position-1",
        direction="buy",
        entry_reference=4000.0,
        fill_price=4000.0,
        volume_lots=0.01,
        stop_loss=3994.0,
        take_profit=4030.0,
        opened_at=datetime(2026, 7, 29, 10, tzinfo=UTC),
        close_retry_count=1,
    )
    store = _MemoryArtifactStore({})

    result = PositionStageService(store).execute(_incoming(store, state, _execution_events(), as_of))

    assert store.read_frame(result.positions).iloc[0]["action"] == "retry_close"
    assert store.read_frame(result.state).iloc[0]["status"] == "close_retry_required"
    assert store.read_frame(result.realized_results).empty


def test_position_stage_records_realized_close_and_net_pnl_in_result_artifact():
    as_of = datetime(2026, 7, 29, 10, 5, tzinfo=UTC)
    state = PositionState(
        status=PositionStatus.OPEN,
        order_id="order-1",
        position_id="position-1",
        direction="sell",
        entry_reference=4000.0,
        fill_price=4000.0,
        volume_lots=0.01,
        stop_loss=4006.0,
        take_profit=3970.0,
        opened_at=datetime(2026, 7, 29, 10, tzinfo=UTC),
    )
    event_time = datetime(2026, 7, 29, 10, 4, tzinfo=UTC)
    event = _execution_events(
        {
            "event_id": "close-1",
            "kind": "closed",
            "event_time": event_time,
            "order_id": "order-1",
            "position_id": "position-1",
            "profit_before_charges_usd": 30.0,
            "commission_cost_usd": 6.0,
            "swap_pnl_usd": -2.0,
            "fee_cost_usd": 1.0,
            "spread_slippage_cost_usd": 3.0,
        },
    )
    store = _MemoryArtifactStore({})

    result = PositionStageService(store).execute(_incoming(store, state, event, as_of))

    assert store.read_frame(result.positions).iloc[0]["status"] == "flat"
    assert store.read_frame(result.realized_results)["net_pnl_usd"].iloc[0] == 18.0
