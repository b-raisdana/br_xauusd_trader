from __future__ import annotations

import csv
from pathlib import Path

from domain.xau_usd.models import XauZone

DEFAULT_RANGES_PATH = Path(__file__).resolve().parents[2] / "data" / "ranges.csv"


def load_generated_raw_zones(
    broker_day: str,
    path: str | Path = DEFAULT_RANGES_PATH,
) -> list[XauZone] | None:
    zones: list[XauZone] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("date") != broker_day or row.get("enabled", "true").lower() != "true":
                continue
            try:
                low = float(row["lower"])
                high = float(row["upper"])
            except (KeyError, TypeError, ValueError):
                return None
            priority = 1 if row.get("priority", "normal").lower() == "high" else 0
            zones.append(XauZone(id="", low=low, high=high, priority=priority))
    return zones if zones else None


def load_all_generated_raw_zones(path: str | Path = DEFAULT_RANGES_PATH) -> dict[str, list[XauZone]]:
    result: dict[str, list[XauZone]] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            broker_day = row.get("date", "")
            if not broker_day or row.get("enabled", "true").lower() != "true":
                continue
            zones = load_generated_raw_zones(broker_day, path)
            if zones is not None:
                result[broker_day] = zones
    return result
