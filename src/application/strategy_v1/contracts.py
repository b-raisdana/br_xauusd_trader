from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_id: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    index_names: tuple[str | None, ...]
    columns: tuple[str, ...]


class StrategySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str = Field(min_length=1)
    as_of: datetime
    symbol: str = Field(min_length=1)
    broker: str = Field(min_length=1)
    ticks: ArtifactReference
    candles_m5: ArtifactReference
    candles_m15: ArtifactReference
    zones: ArtifactReference
    account_and_costs: ArtifactReference
    broker_calendar: ArtifactReference
    execution_events: ArtifactReference

    @field_validator("as_of")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None or value.astimezone(UTC) != value:
            raise ValueError("as_of must be expressed in UTC")
        return value


class StrategyContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = "1.0"
    run_id: str = Field(min_length=1)
    snapshot: StrategySnapshot
    state: ArtifactReference


class SignalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = "1.0"
    run_id: str = Field(min_length=1)
    snapshot: StrategySnapshot
    signals: ArtifactReference
    state: ArtifactReference
    rejections: ArtifactReference


class OrderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = "1.0"
    run_id: str = Field(min_length=1)
    snapshot: StrategySnapshot
    signal_result: ArtifactReference
    orders: ArtifactReference
    risk_audit: ArtifactReference
    state: ArtifactReference


class PositionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = "1.0"
    run_id: str = Field(min_length=1)
    snapshot: StrategySnapshot
    order_result: ArtifactReference
    positions: ArtifactReference
    realized_results: ArtifactReference
    state: ArtifactReference
