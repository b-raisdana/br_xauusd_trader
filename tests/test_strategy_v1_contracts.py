from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from application.strategy_v1.contracts import ArtifactReference, StrategySnapshot


def artifact(name: str) -> ArtifactReference:
    return ArtifactReference(
        path=Path(f"{name}.parquet"),
        sha256="0" * 64,
        schema_id=name,
        row_count=1,
        index_names=("date",),
        columns=("value",),
    )


def test_strategy_snapshot_is_an_immutable_bundle_of_all_stage_inputs():
    snapshot = StrategySnapshot(
        snapshot_id="snapshot-1",
        as_of=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
        symbol="XAUUSD!",
        broker="opofinance",
        ticks=artifact("ticks"),
        candles_m5=artifact("m5"),
        candles_m15=artifact("m15"),
        zones=artifact("zones"),
        account_and_costs=artifact("account-and-costs"),
        broker_calendar=artifact("broker-calendar"),
        execution_events=artifact("events"),
    )
    with pytest.raises(ValidationError):
        snapshot.symbol = "OTHER"
    assert snapshot.as_of.utcoffset().total_seconds() == 0


def test_artifact_reference_rejects_invalid_digest_and_negative_row_count():
    with pytest.raises(ValidationError):
        ArtifactReference(
            path=Path("bad.parquet"),
            sha256="not-a-digest",
            schema_id="ticks.v1",
            row_count=-1,
            index_names=("date",),
            columns=("bid", "ask"),
        )


def test_strategy_snapshot_requires_utc_and_complete_market_context():
    with pytest.raises(ValidationError):
        StrategySnapshot(
            snapshot_id="snapshot-2",
            as_of=datetime(2026, 7, 29, 10, 0),
            symbol="XAUUSD!",
            broker="opofinance",
            ticks=artifact("ticks"),
            candles_m5=artifact("m5"),
            candles_m15=artifact("m15"),
            zones=artifact("zones"),
            account_and_costs=artifact("account-and-costs"),
            broker_calendar=artifact("broker-calendar"),
            execution_events=artifact("events"),
        )
