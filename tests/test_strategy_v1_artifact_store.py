import pandas as pd
import pytest

from infrastructure.strategy_v1.artifact_store import ParquetArtifactStore


def test_parquet_artifact_store_round_trips_index_and_schema(tmp_path):
    frame = pd.DataFrame(
        {"bid": [4026.51, 4026.52], "ask": [4028.6, 4028.61]},
        index=pd.DatetimeIndex(
            ["2026-07-29 01:00:00+00:00", "2026-07-29 01:00:01+00:00"],
            name="date",
        ),
    )
    store = ParquetArtifactStore(tmp_path)
    reference = store.write_frame(frame, schema_id="ticks.v1")
    pd.testing.assert_frame_equal(store.read_frame(reference), frame)


def test_parquet_artifact_store_rejects_tampered_artifact(tmp_path):
    frame = pd.DataFrame({"bid": [4026.51]}, index=pd.Index([1], name="row"))
    store = ParquetArtifactStore(tmp_path)
    reference = store.write_frame(frame, schema_id="ticks.v1")
    frame.to_parquet(reference.path, engine="pyarrow", index=True)
    with pytest.raises(ValueError, match="digest mismatch"):
        store.read_frame(reference)
