from __future__ import annotations

import base64
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

import pandas as pd
from pydantic import BaseModel, Field, PrivateAttr

from application.xauusd_trading_strategy_1_vector.domain.columnar import SignalTable, SignalTickState, WindowTable
from application.xauusd_trading_strategy_1_vector.domain.execution_schema import (
    AccountSnapshots,
    ActionEvents,
    FeedbackEvents,
    ModificationEvents,
    PullbackCycleSnapshots,
    RejectionEvents,
)
from application.xauusd_trading_strategy_1_vector.domain.schema import (
    OrderManagementResult,
    PerCandleState,
    PerTickState,
    PositionTrackingResult,
    StrategyCandles,
    StrategyResultWithCandles,
    VectorizedTick,
)
from br_pre_commit import pandera_validate
from config import app_config
from helper.importer import pt
from infrastructure.result_processing.parquet import read_parquet, write_parquet

type ResultCategory = Literal[
    "candles",
    "per_candle_states",
    "ticks",
    "per_tick_state",
    "orders",
    "fills",
    "closes",
    "execution_events",
    "rejections",
    "modifications",
    "cycles",
    "accounts",
    "actions",
    "feedback",
    "results_with_columns",
    "positions",
    "signal_state",
    "signals",
    "windows",
]

type ArtifactEntry = tuple[Path, bool]


def _write_columnar(frame: pd.DataFrame, file_name: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / file_name
    frame.to_parquet(path, engine="pyarrow", index=True)
    return path


@lru_cache
def _check_once_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path  # / self.run_id


class ResultFilesManifest(BaseModel):
    # run_id: str = Field(default_factory=lambda: f"{datetime.now(UTC):%Y%m%d%H%M%S.%f}-{secrets.token_hex(2)}")
    # root: Path = Field(default_factory=lambda: app_config.path_of_data / "strategy-results")
    root: Path = Field(default_factory=lambda: app_config.path_of_data / "strategy-results")
    meta: dict[str, float] = Field(default_factory=dict)
    candles: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    per_candle_states: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    ticks: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    per_tick_state: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    orders: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    fills: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    closes: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    execution_events: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    rejections: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    modifications: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    cycles: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    accounts: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    actions: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    feedback: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    results_with_columns: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    positions: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    signal_state: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    signals: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    windows: dict[datetime, ArtifactEntry] = Field(default_factory=dict)
    _write_executor: ThreadPoolExecutor = PrivateAttr(default_factory=lambda: ThreadPoolExecutor(max_workers=4))
    _pending_writes: dict[tuple[ResultCategory, datetime], Future[Path]] = PrivateAttr(default_factory=dict)
    _frames: dict[tuple[ResultCategory, datetime], pd.DataFrame] = PrivateAttr(default_factory=dict)

    # def get_id(self) -> str:
    #     return self.run_id

    def __init__(self, **data: object):  # ignore: no-object-annotations
        super().__init__(**data)
        self._output_dir().mkdir(parents=True, exist_ok=True)
        file_name = f"new_run_at_{datetime.now(UTC):%y-%m-%dT%H-%M-%S}.log"
        (self._output_dir() / file_name).touch()

    def _output_dir(self) -> Path:
        return _check_once_output_dir(self.root)  # / self.run_id

    def _artifacts_by_day(self, category: ResultCategory) -> dict[datetime, ArtifactEntry]:
        return {
            "candles": self.candles,
            "per_candle_states": self.per_candle_states,
            "ticks": self.ticks,
            "per_tick_state": self.per_tick_state,
            "orders": self.orders,
            "fills": self.fills,
            "closes": self.closes,
            "execution_events": self.execution_events,
            "rejections": self.rejections,
            "modifications": self.modifications,
            "cycles": self.cycles,
            "accounts": self.accounts,
            "actions": self.actions,
            "feedback": self.feedback,
            "results_with_columns": self.results_with_columns,
            "positions": self.positions,
            "signal_state": self.signal_state,
            "signals": self.signals,
            "windows": self.windows,
        }[category]

    def _submit_write(self, category: ResultCategory, day: datetime, df: pd.DataFrame, file_name: str) -> None:
        self._complete_pending_write(category, day)
        self._frames[(category, day)] = df
        self._artifacts_by_day(category)[day] = (self._output_dir() / file_name, False)
        if category in {"signal_state", "signals", "windows"}:
            self._pending_writes[category, day] = self._write_executor.submit(
                _write_columnar, df.copy(deep=False), file_name, self._output_dir()
            )
            return
        owned_copy = df.copy(deep=False)
        for object_column in owned_copy.select_dtypes(include="object", exclude="str"):
            owned_copy[object_column] = owned_copy[object_column].map(deepcopy)
        self._pending_writes[category, day] = self._write_executor.submit(
            write_parquet, owned_copy, file_name, self._output_dir()
        )

    @pandera_validate(allow_pandas_dataframe=True)
    def get_cached_frame(self, category: ResultCategory, day: datetime) -> pd.DataFrame | None:
        """Return the in-memory frame for a category/day if it was submitted but not yet discarded."""
        return self._frames.get((category, day))

    def _complete_pending_write(self, category: ResultCategory, day: datetime) -> None:
        pending_write = self._pending_writes.get((category, day))
        if pending_write is not None:
            written_path = pending_write.result()
            self._artifacts_by_day(category)[day] = (written_path, True)
            del self._pending_writes[category, day]
            self._frames.pop((category, day), None)

    def wait_for_writes(self) -> None:
        for category, day in list(self._pending_writes):
            self._complete_pending_write(category, day)

    def close(self) -> None:
        try:
            self.wait_for_writes()
        finally:
            self._write_executor.shutdown(wait=True)

    def is_write_successful(self, category: ResultCategory, day: datetime) -> bool:
        self._complete_pending_write(category, day)
        artifact = self._artifacts_by_day(category).get(day)
        return artifact is not None and artifact[1]

    def get_path(self, category: ResultCategory, day: datetime) -> Path | None:
        self._complete_pending_write(category, day)
        artifact = self._artifacts_by_day(category).get(day)
        return artifact[0] if artifact else None

    def successful_days(self, category: ResultCategory) -> list[datetime]:
        self.wait_for_writes()
        return sorted(day for day, (_, written) in self._artifacts_by_day(category).items() if written)

    def _read(self, category: ResultCategory, day: datetime) -> pd.DataFrame:
        path = self.get_path(category, day)
        if path is None or not self._artifacts_by_day(category)[day][1]:
            raise FileNotFoundError(f"No completed {category} artifact for {day}")
        return pd.read_parquet(path) if category in {"signal_state", "signals", "windows"} else read_parquet(path)

    @staticmethod
    @pandera_validate(allow_pandas_dataframe=True)
    def hash_df(df: pd.DataFrame) -> str:
        """Cheap content-addressable hash for artifact filenames.

        Hashes shape + index + column names only. Full-frame hashing costs
        ~1s per artifact in the profile; the hash is only used for filename
        uniqueness, so index-level identity is sufficient and preserves the
        existing 7-char base64 filename format.
        """
        index_hash = pd.util.hash_pandas_object(df.index, index=False).sum()
        shape_hash = hash((df.shape, tuple(df.columns)))
        numeric_hash = int(index_hash) ^ (shape_hash & 0xFFFFFFFFFFFFFFFF)
        hash_7 = base64.urlsafe_b64encode(int(numeric_hash).to_bytes(8, byteorder="big")).decode()[:7]
        return hash_7

    @pandera_validate
    def save_daily_signal_state(self, day: datetime, df: pt.DataFrame[SignalTickState]) -> Self:
        self._submit_write("signal_state", day, df, f"signal_state.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def read_daily_signal_state(self, day: datetime) -> pt.DataFrame[SignalTickState]:
        return SignalTickState.validate(self._read("signal_state", day), lazy=True)

    @pandera_validate
    def save_daily_signals(self, day: datetime, df: pt.DataFrame[SignalTable]) -> Self:
        self._submit_write("signals", day, df, f"signals.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def read_daily_signals(self, day: datetime) -> pt.DataFrame[SignalTable]:
        return SignalTable.validate(self._read("signals", day), lazy=True)

    @pandera_validate
    def save_daily_windows(self, day: datetime, df: pt.DataFrame[WindowTable]) -> Self:
        self._submit_write("windows", day, df, f"windows.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def read_daily_windows(self, day: datetime) -> pt.DataFrame[WindowTable]:
        return WindowTable.validate(self._read("windows", day), lazy=True)

    @pandera_validate
    def save_daily_ticks_temp_state(self, day: datetime, df: pt.DataFrame[PerTickState]) -> Self:
        PerTickState.validate(df, lazy=True)
        self._submit_write("per_tick_state", day, df, f"ticks_temp_state.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def read_daily_ticks_temp_state(self, day: datetime) -> pt.DataFrame[PerTickState]:
        return PerTickState.validate(self._read("per_tick_state", day), lazy=True)

    @pandera_validate
    def save_daily_candles_temp_state(self, day: datetime, df: pt.DataFrame[PerCandleState]) -> Self:
        PerCandleState.validate(df, lazy=True)
        self._submit_write(
            "per_candle_states", day, df, f"candles_temp_state.{day:%y-%m-%d}.{self.hash_df(df)}.parquet"
        )
        return self

    @pandera_validate
    def read_daily_candles_temp_state(self, day: datetime) -> pt.DataFrame[PerCandleState]:
        return PerCandleState.validate(self._read("per_candle_states", day), lazy=True)

    @pandera_validate
    def save_daily_ticks(self, day: datetime, df: pt.DataFrame[VectorizedTick]) -> Self:
        VectorizedTick.validate(df, lazy=True)
        self._submit_write("ticks", day, df, f"ticks.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def read_daily_ticks(self, day: datetime) -> pt.DataFrame[VectorizedTick]:
        return VectorizedTick.validate(self._read("ticks", day), lazy=True)

    @pandera_validate
    def save_daily_candles(self, day: datetime, df: pt.DataFrame[StrategyCandles]) -> Self:
        StrategyCandles.validate(df, lazy=True)
        self._submit_write("candles", day, df, f"candles.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def read_daily_candles(self, day: datetime) -> pt.DataFrame[StrategyCandles]:
        return StrategyCandles.validate(self._read("candles", day), lazy=True)

    @pandera_validate
    def save_orders(self, day: datetime, df: pt.DataFrame[OrderManagementResult]) -> Self:
        OrderManagementResult.validate(df, lazy=True)
        self._submit_write("orders", day, df, f"orders.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def read_orders(self, day: datetime) -> pt.DataFrame[OrderManagementResult]:
        return OrderManagementResult.validate(self._read("orders", day), lazy=True)

    @pandera_validate
    def save_daily_orders(self, day: datetime, df: pd.DataFrame) -> Self:
        """Save execution order events in generic format."""
        self._submit_write("orders", day, df, f"orders.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def save_daily_fills(self, day: datetime, df: pd.DataFrame) -> Self:
        self._submit_write("fills", day, df, f"fills.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def save_daily_closes(self, day: datetime, df: pd.DataFrame) -> Self:
        self._submit_write("closes", day, df, f"closes.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def save_daily_execution_events(self, day: datetime, df: pd.DataFrame) -> Self:
        self._submit_write("execution_events", day, df, f"execution_events.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def save_daily_modifications(self, day: datetime, df: pd.DataFrame) -> Self:
        ModificationEvents.validate(df, lazy=True)
        self._submit_write("modifications", day, df, f"modifications.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def save_daily_cycles(self, day: datetime, df: pd.DataFrame) -> Self:
        PullbackCycleSnapshots.validate(df, lazy=True)
        self._submit_write("cycles", day, df, f"cycles.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def save_daily_actions(self, day: datetime, df: pd.DataFrame) -> Self:
        df = ActionEvents.validate(df)
        self._submit_write("actions", day, df, f"actions.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def save_daily_feedback(self, day: datetime, df: pd.DataFrame) -> Self:
        df = FeedbackEvents.validate(df)
        self._submit_write("feedback", day, df, f"feedback.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def save_daily_accounts(self, day: datetime, df: pd.DataFrame) -> Self:
        df = AccountSnapshots.validate(df)
        self._submit_write("accounts", day, df, f"accounts.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def save_daily_rejections(self, day: datetime, df: pd.DataFrame) -> Self:
        RejectionEvents.validate(df, lazy=True)
        self._submit_write("rejections", day, df, f"rejections.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def save_daily_positions(self, day: datetime, df: pd.DataFrame) -> Self:
        """Save execution position snapshots in generic format."""
        self._submit_write("positions", day, df, f"positions.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate(allow_pandas_dataframe=True)
    def read_daily_positions(self, day: datetime) -> pd.DataFrame:
        """Read raw replay position snapshots without applying the legacy report schema."""
        return self._read("positions", day)

    @pandera_validate(allow_pandas_dataframe=True)
    def read_daily_execution_artifact(
        self,
        category: Literal[
            "fills",
            "closes",
            "execution_events",
            "rejections",
            "modifications",
            "cycles",
            "accounts",
            "actions",
            "feedback",
        ],
        day: datetime,
    ) -> pd.DataFrame:
        return self._read(category, day)

    @pandera_validate
    def save_results_with_columns(self, day: datetime, df: pt.DataFrame[StrategyResultWithCandles]) -> Self:
        StrategyResultWithCandles.validate(df, lazy=True)
        self._submit_write(
            "results_with_columns", day, df, f"results_with_columns.{day:%y-%m-%d}.{self.hash_df(df)}.parquet"
        )
        return self

    @pandera_validate
    def read_results_with_columns(self, day: datetime) -> pt.DataFrame[StrategyResultWithCandles]:
        return StrategyResultWithCandles.validate(self._read("results_with_columns", day), lazy=True)

    @pandera_validate
    def save_positions(self, day: datetime, df: pt.DataFrame[PositionTrackingResult]) -> Self:
        PositionTrackingResult.validate(df, lazy=True)
        self._submit_write("positions", day, df, f"positions.{day:%y-%m-%d}.{self.hash_df(df)}.parquet")
        return self

    @pandera_validate
    def read_positions(self, day: datetime) -> pt.DataFrame[PositionTrackingResult]:
        return PositionTrackingResult.validate(self._read("positions", day), lazy=True)
