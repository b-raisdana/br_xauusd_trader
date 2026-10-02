from __future__ import annotations

import secrets
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

import pandas as pd
from pydantic import BaseModel, Field, PrivateAttr

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
    "candles", "per_candle_states", "ticks", "per_tick_state", "orders", "results_with_columns", "positions"
]


class ResultFilesManifest(BaseModel):
    run_id: str = Field(default_factory=lambda: f"{datetime.now(UTC):%Y%m%d%H%M%S.%f}-{secrets.token_hex(2)}")
    root: Path = Field(default_factory=lambda: app_config.path_of_data / "strategy-results")
    meta: dict[str, float] = Field(default_factory=dict)
    candles: dict[datetime, tuple[Path, bool]] = Field(default_factory=dict)
    per_candle_states: dict[datetime, tuple[Path, bool]] = Field(default_factory=dict)
    ticks: dict[datetime, tuple[Path, bool]] = Field(default_factory=dict)
    per_tick_state: dict[datetime, tuple[Path, bool]] = Field(default_factory=dict)
    orders: dict[datetime, tuple[Path, bool]] = Field(default_factory=dict)
    results_with_columns: dict[datetime, tuple[Path, bool]] = Field(default_factory=dict)
    positions: dict[datetime, tuple[Path, bool]] = Field(default_factory=dict)
    _executor: ThreadPoolExecutor = PrivateAttr(default_factory=lambda: ThreadPoolExecutor(max_workers=4))
    _pending: dict[tuple[ResultCategory, datetime], Future[Path]] = PrivateAttr(default_factory=dict)

    def get_id(self) -> str:
        return self.run_id

    def _folder(self) -> Path:
        return self.root / self.run_id

    def _store(self, category: ResultCategory) -> dict[datetime, tuple[Path, bool]]:
        return {
            "candles": self.candles,
            "per_candle_states": self.per_candle_states,
            "ticks": self.ticks,
            "per_tick_state": self.per_tick_state,
            "orders": self.orders,
            "results_with_columns": self.results_with_columns,
            "positions": self.positions,
        }[category]

    def _submit(self, category: ResultCategory, day: datetime, df: pd.DataFrame, name: str) -> None:
        self._finish(category, day)
        path = self._folder() / name
        self._store(category)[day] = (path, False)
        snapshot = df.copy(deep=True)
        for column in snapshot.select_dtypes(include="object", exclude="str"):
            snapshot[column] = snapshot[column].map(deepcopy)
        self._pending[category, day] = self._executor.submit(write_parquet, snapshot, name, self._folder())

    def _finish(self, category: ResultCategory, day: datetime) -> None:
        future = self._pending.get((category, day))
        if future is not None:
            path = future.result()
            self._store(category)[day] = (path, True)
            del self._pending[category, day]

    def wait_for_writes(self) -> None:
        for category, day in list(self._pending):
            self._finish(category, day)

    def close(self) -> None:
        try:
            self.wait_for_writes()
        finally:
            self._executor.shutdown(wait=True)

    def is_write_successful(self, category: ResultCategory, day: datetime) -> bool:
        self._finish(category, day)
        entry = self._store(category).get(day)
        return entry is not None and entry[1]

    def get_path(self, category: ResultCategory, day: datetime) -> Path | None:
        self._finish(category, day)
        entry = self._store(category).get(day)
        return entry[0] if entry else None

    def successful_days(self, category: ResultCategory) -> list[datetime]:
        self.wait_for_writes()
        return sorted(day for day, (_, ok) in self._store(category).items() if ok)

    def _read(self, category: ResultCategory, day: datetime) -> pd.DataFrame:
        path = self.get_path(category, day)
        if path is None or not self._store(category)[day][1]:
            raise FileNotFoundError(f"No completed {category} artifact for {day}")
        return read_parquet(path)

    @pandera_validate
    def save_daily_ticks_temp_state(self, day: datetime, df: pt.DataFrame[PerTickState]) -> Self:
        PerTickState.validate(df, lazy=True)
        self._submit("per_tick_state", day, df, f"{day:%Y%m%d}_ticks_temp_state.parquet")
        return self

    @pandera_validate
    def read_daily_ticks_temp_state(self, day: datetime) -> pt.DataFrame[PerTickState]:
        return PerTickState.validate(self._read("per_tick_state", day), lazy=True)

    @pandera_validate
    def save_daily_candles_temp_state(self, day: datetime, df: pt.DataFrame[PerCandleState]) -> Self:
        PerCandleState.validate(df, lazy=True)
        self._submit("per_candle_states", day, df, f"{day:%Y%m%d}_candles_temp_state.parquet")
        return self

    @pandera_validate
    def read_daily_candles_temp_state(self, day: datetime) -> pt.DataFrame[PerCandleState]:
        return PerCandleState.validate(self._read("per_candle_states", day), lazy=True)

    @pandera_validate
    def save_daily_ticks(self, day: datetime, df: pt.DataFrame[VectorizedTick]) -> Self:
        VectorizedTick.validate(df, lazy=True)
        self._submit("ticks", day, df, f"{day:%Y%m%d}_ticks.parquet")
        return self

    @pandera_validate
    def read_daily_ticks(self, day: datetime) -> pt.DataFrame[VectorizedTick]:
        return VectorizedTick.validate(self._read("ticks", day), lazy=True)

    @pandera_validate
    def save_daily_candles(self, day: datetime, df: pt.DataFrame[StrategyCandles]) -> Self:
        StrategyCandles.validate(df, lazy=True)
        self._submit("candles", day, df, f"{day:%Y%m%d}_candles.parquet")
        return self

    @pandera_validate
    def read_daily_candles(self, day: datetime) -> pt.DataFrame[StrategyCandles]:
        return StrategyCandles.validate(self._read("candles", day), lazy=True)

    @pandera_validate
    def save_orders(self, day: datetime, df: pt.DataFrame[OrderManagementResult]) -> Self:
        OrderManagementResult.validate(df, lazy=True)
        self._submit("orders", day, df, f"{day:%Y%m%d}_orders.parquet")
        return self

    @pandera_validate
    def read_orders(self, day: datetime) -> pt.DataFrame[OrderManagementResult]:
        return OrderManagementResult.validate(self._read("orders", day), lazy=True)

    @pandera_validate
    def save_results_with_columns(self, day: datetime, df: pt.DataFrame[StrategyResultWithCandles]) -> Self:
        StrategyResultWithCandles.validate(df, lazy=True)
        self._submit("results_with_columns", day, df, f"{day:%Y%m%d}_results_with_columns.parquet")
        return self

    @pandera_validate
    def read_results_with_columns(self, day: datetime) -> pt.DataFrame[StrategyResultWithCandles]:
        return StrategyResultWithCandles.validate(self._read("results_with_columns", day), lazy=True)

    @pandera_validate
    def save_positions(self, day: datetime, df: pt.DataFrame[PositionTrackingResult]) -> Self:
        PositionTrackingResult.validate(df, lazy=True)
        self._submit("positions", day, df, f"{day:%Y%m%d}_positions.parquet")
        return self

    @pandera_validate
    def read_positions(self, day: datetime) -> pt.DataFrame[PositionTrackingResult]:
        return PositionTrackingResult.validate(self._read("positions", day), lazy=True)
