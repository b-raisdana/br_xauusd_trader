from pathlib import Path

import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.zones import StrategyZoneRows
from helper.importer import pt


class CsvZoneSource:
    required_columns = {"date", "lower", "upper", "priority", "enabled"}
    enabled_values = {"true", "1", "yes", "on"}
    disabled_values = {"false", "0", "no", "off"}
    priority_values = {"low", "normal", "high"}

    @pandera_validate
    def load_zones(self, path: Path) -> pt.DataFrame[StrategyZoneRows]:
        rows = pd.read_csv(path)
        missing = self.required_columns.difference(rows.columns)
        if missing:
            raise ValueError(f"Zone file is missing required columns: {sorted(missing)}")

        enabled = rows["enabled"].astype("string").str.strip().str.lower()
        is_enabled = enabled.isin(self.enabled_values)
        is_disabled = enabled.isin(self.disabled_values)
        if (~(is_enabled | is_disabled)).any():
            raise ValueError("Zone file contains an invalid enabled value")

        active = rows.loc[is_enabled].copy()
        if active.empty:
            raise ValueError("Zone file has no enabled zones")
        active["date"] = pd.to_datetime(active["date"], format="%Y.%m.%d", errors="coerce", utc=True).astype(
            pd.DatetimeTZDtype(unit="ns", tz="UTC")
        )
        active["lower"] = pd.to_numeric(active["lower"], errors="coerce").astype("float64")
        active["upper"] = pd.to_numeric(active["upper"], errors="coerce").astype("float64")
        active["priority"] = active["priority"].astype("string").str.strip().str.lower()
        invalid = (
            active[["date", "lower", "upper", "priority"]].isna().any(axis=1)
            | active["lower"].le(0.0)
            | active["upper"].le(0.0)
            | active["lower"].gt(active["upper"])
            | ~active["priority"].isin(self.priority_values)
            | active["lower"].isin([float("inf"), float("-inf")])
            | active["upper"].isin([float("inf"), float("-inf")])
        )
        if invalid.any():
            rows_text = active.index[invalid].astype(str).str.cat(sep=", ")
            raise ValueError(f"Zone file contains invalid enabled rows: {rows_text}")

        active["zone_id"] = "zone-" + active.index.astype("string").str.zfill(4)
        active["direction"] = 0
        if "note" not in active.columns:
            active["note"] = None
        active["note"] = active["note"].astype("string[pyarrow]")
        active = active.rename(columns={"priority": "importance_class"})
        columns = ["date", "zone_id", "lower", "upper", "importance_class", "direction", "note"]
        return active[columns].sort_values(["date", "lower", "upper"]).set_index(["date", "zone_id"])
