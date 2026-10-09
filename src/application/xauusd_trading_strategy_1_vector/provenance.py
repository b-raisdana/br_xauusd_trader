"""Durable input/configuration/code/artifact provenance for offline replay."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from application.xauusd_trading_strategy_1_vector.domain.replay import ReplayConfig
    from infrastructure.result_processing.io import ResultFilesManifest


import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def file_digest(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_provenance(
    manifest: ResultFilesManifest,
    output_path: Path | str,
    execution: ReplayConfig | None,
    inputs: dict[str, Path | None],
) -> Path:
    output_path = Path(output_path)
    artifacts = manifest.model_dump(mode="json")
    paths = {"source": output_path}
    for suffix in ("signals", "windows", "backtest_report", "backtest_trades"):
        path = output_path.with_name(f"{output_path.stem}_{suffix}.parquet")
        if path.is_file():
            paths[suffix] = path
    package = Path(__file__).parent
    code = {str(p.relative_to(package)): file_digest(p) for p in sorted(package.rglob("*.py"))}
    evidence = {
        "created_utc": datetime.now(UTC).isoformat(),
        "configuration": {
            "initial_balance": execution.initial_balance,
            "strategy_capital": execution.strategy_capital,
            "inputs": execution.inputs.model_dump(mode="json"),
            "restart_days": sorted(execution.restart_days),
            "economics": repr(execution.economics),
        }
        if execution is not None
        else None,
        "inputs": {
            name: {"path": str(path), "sha256": file_digest(path)} for name, path in inputs.items() if path is not None
        },
        "outputs": {
            name: {"path": str(path), "sha256": file_digest(path), "bytes": path.stat().st_size}
            for name, path in paths.items()
        },
        "code_sha256": code,
        "manifest": artifacts,
    }
    path = output_path.with_name(f"{output_path.stem}_provenance.json")
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return path
