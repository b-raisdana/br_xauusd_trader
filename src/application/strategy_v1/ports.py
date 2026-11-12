from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.common.ohlcv import MultiTimeframeTicksSpreadOHLC
from domain.schemas.tick import Tick
from domain.schemas.xau_usd.zones import StrategyZoneRows
from helper.importer import pt

from .contracts import ArtifactReference
from .risk_models import Mt5RiskSnapshot


class ArtifactStore(Protocol):
    @pandera_validate(allow_pandas_dataframe=True)
    def read_frame(self, reference: ArtifactReference) -> pd.DataFrame: ...

    @pandera_validate(allow_pandas_dataframe=True)
    def write_frame(self, frame: pd.DataFrame, *, schema_id: str) -> ArtifactReference: ...


class MarketDataSource(Protocol):
    @pandera_validate
    async def get_ticks(self, symbol: str, start: datetime, end: datetime) -> pt.DataFrame[Tick]: ...

    @pandera_validate
    async def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> pt.DataFrame[MultiTimeframeTicksSpreadOHLC]: ...


class ZoneDataSource(Protocol):
    @pandera_validate
    def load_zones(self, path: Path) -> pt.DataFrame[StrategyZoneRows]: ...


class RiskCalculationSource(Protocol):
    def get_risk_snapshot(self, symbol: str) -> Mt5RiskSnapshot: ...

    def profit_at_stop_per_lot(
        self,
        symbol: str,
        direction: Literal["buy", "sell"],
        entry: float,
        stop: float,
    ) -> float: ...

    def margin_per_lot(self, symbol: str, direction: Literal["buy", "sell"], entry: float) -> float: ...
