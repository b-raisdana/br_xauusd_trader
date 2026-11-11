from hashlib import file_digest
from pathlib import Path
from uuid import uuid4

import pandas as pd

from application.strategy_v1.contracts import ArtifactReference
from br_pre_commit import pandera_validate


class ParquetArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    @pandera_validate(allow_pandas_dataframe=True)
    def read_frame(self, reference: ArtifactReference) -> pd.DataFrame:
        if not reference.path.is_file():
            raise FileNotFoundError(f"Artifact is missing: {reference.path}")
        if self._sha256(reference.path) != reference.sha256:
            raise ValueError(f"Artifact digest mismatch: {reference.path}")
        frame = pd.read_parquet(reference.path)
        if len(frame) != reference.row_count:
            raise ValueError(f"Artifact row count mismatch: {reference.path}")
        if tuple(frame.index.names) != reference.index_names:
            raise ValueError(f"Artifact index schema mismatch: {reference.path}")
        if tuple(frame.columns) != reference.columns:
            raise ValueError(f"Artifact column schema mismatch: {reference.path}")
        return frame

    @pandera_validate(allow_pandas_dataframe=True)
    def write_frame(self, frame: pd.DataFrame, *, schema_id: str) -> ArtifactReference:
        if not schema_id.strip():
            raise ValueError("schema_id must not be empty")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{uuid4().hex}.parquet"
        temporary_path = path.with_suffix(".parquet.tmp")
        frame.to_parquet(temporary_path, engine="pyarrow", index=True, compression="zstd")
        temporary_path.replace(path)
        return ArtifactReference(
            path=path,
            sha256=self._sha256(path),
            schema_id=schema_id,
            row_count=len(frame),
            index_names=tuple(frame.index.names),
            columns=tuple(frame.columns),
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        with path.open("rb") as source:
            return file_digest(source, "sha256").hexdigest()
