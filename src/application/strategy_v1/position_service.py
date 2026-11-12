from datetime import datetime

import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.strategy_v1 import (
    BrokerCalendarRows,
    PositionSnapshotRows,
    PositionStateRows,
    RealizedTradeRows,
    StrategyExecutionEvents,
)
from domain.xau_usd.strategy_v1 import (
    PositionEvent,
    PositionState,
    PositionStatus,
    PositionTransition,
    apply_position_event,
    position_deadline_action,
    request_close_retry,
)
from domain.xau_usd.strategy_v1.config import StrategyV1Config
from helper.importer import pt

from .contracts import OrderResult, PositionResult
from .ports import ArtifactStore


class PositionStageService:
    def __init__(self, artifact_store: ArtifactStore, config: StrategyV1Config | None = None) -> None:
        self.artifact_store = artifact_store
        self.config = config or StrategyV1Config()

    def execute(self, incoming: OrderResult) -> PositionResult:
        prior_state = state_from_frame(self.artifact_store.read_frame(incoming.state))
        execution_events = execution_event_from_frame(
            self.artifact_store.read_frame(incoming.snapshot.execution_events),
        )
        if execution_events is not None:
            transition = apply_position_event(prior_state, execution_events)
        elif prior_state.status == PositionStatus.CLOSE_RETRY_REQUIRED:
            transition = request_close_retry(prior_state)
        elif prior_state.status == PositionStatus.FLAT:
            transition = PositionTransition(state=prior_state)
        else:
            calendar = broker_calendar(self.artifact_store.read_frame(incoming.snapshot.broker_calendar))
            market_close_at = calendar.index[0].to_pydatetime()
            action = position_deadline_action(
                prior_state,
                incoming.snapshot.as_of,
                market_close_at,
                self.config,
            )
            transition = PositionTransition(state=prior_state, action=action or "none")

        state_reference = self.artifact_store.write_frame(
            position_state_frame(transition.state, incoming.snapshot.as_of),
            schema_id="strategy-v1.position-state.1",
        )
        positions_reference = self.artifact_store.write_frame(
            position_snapshot_frame(transition, incoming.snapshot.as_of),
            schema_id="strategy-v1.positions.1",
        )
        realized_reference = self.artifact_store.write_frame(
            realized_results_frame(transition, execution_events, incoming.snapshot.as_of),
            schema_id="strategy-v1.realized-trades.1",
        )
        return PositionResult(
            run_id=incoming.run_id,
            snapshot=incoming.snapshot,
            order_result=incoming.orders,
            positions=positions_reference,
            realized_results=realized_reference,
            state=state_reference,
        )


@pandera_validate
def state_from_frame(frame: pt.DataFrame[PositionStateRows]) -> PositionState:
    if frame.empty:
        return PositionState()
    if len(frame) != 1:
        raise ValueError("position state artifact must contain exactly one state row")
    state_values = frame.iloc[0].astype(object).where(pd.notna(frame.iloc[0]), None).to_dict()
    return PositionState.model_validate(state_values)


@pandera_validate
def execution_event_from_frame(frame: pt.DataFrame[StrategyExecutionEvents]) -> PositionEvent | None:
    if frame.empty:
        return None
    if len(frame) != 1:
        raise ValueError("position stage consumes one ordered execution event per snapshot")
    event_values = frame.iloc[0].astype(object).where(pd.notna(frame.iloc[0]), None).to_dict()
    event_values["event_time"] = frame.index[0].to_pydatetime()
    return PositionEvent.model_validate(event_values)


@pandera_validate
def broker_calendar(frame: pt.DataFrame[BrokerCalendarRows]) -> pt.DataFrame[BrokerCalendarRows]:
    if len(frame) != 1:
        raise ValueError("position deadline requires exactly one next market close")
    return frame


@pandera_validate
def position_state_frame(
    state: PositionState,
    as_of: datetime,
) -> pt.DataFrame[PositionStateRows]:
    index = pd.DatetimeIndex([pd.Timestamp(as_of)]).astype("datetime64[ns, UTC]")
    index.name = "date"
    frame = pd.DataFrame([state.model_dump(mode="json")], index=index)
    for column in (
        "entry_reference",
        "fill_price",
        "volume_lots",
        "stop_loss",
        "take_profit",
        "last_realized_net_pnl_usd",
    ):
        frame[column] = frame[column].astype("float64")
    frame["close_retry_count"] = frame["close_retry_count"].astype("int64")
    return frame


@pandera_validate
def position_snapshot_frame(
    transition: PositionTransition,
    as_of: datetime,
) -> pt.DataFrame[PositionSnapshotRows]:
    index = pd.DatetimeIndex([pd.Timestamp(as_of)]).astype("datetime64[ns, UTC]")
    index.name = "date"
    state = transition.state.model_dump(mode="json")
    state["action"] = transition.action
    frame = pd.DataFrame([state], index=index)
    for column in (
        "entry_reference",
        "fill_price",
        "volume_lots",
        "stop_loss",
        "take_profit",
        "last_realized_net_pnl_usd",
    ):
        frame[column] = frame[column].astype("float64")
    frame["close_retry_count"] = frame["close_retry_count"].astype("int64")
    return frame


@pandera_validate
def realized_results_frame(
    transition: PositionTransition,
    event: PositionEvent | None,
    as_of: datetime,
) -> pt.DataFrame[RealizedTradeRows]:
    time = event.event_time if event is not None and event.kind == "closed" else as_of
    index = pd.DatetimeIndex([time] if transition.realized_net_pnl_usd is not None else [], tz="UTC")
    index = index.astype("datetime64[ns, UTC]")
    index.name = "date"
    values = [] if transition.realized_net_pnl_usd is None else [transition.realized_net_pnl_usd]
    return pd.DataFrame({"net_pnl_usd": pd.Series(values, index=index, dtype="float64")}, index=index)
