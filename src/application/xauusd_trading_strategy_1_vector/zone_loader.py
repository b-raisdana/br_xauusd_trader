from pathlib import Path

import pandas as pd
from br_py_log_n_profile import log_w, profile_it

from config import app_config
from domain.schemas.zone import Zone
from helper.importer import pt
from helper.pandera import pandera_validate


@profile_it
@pandera_validate
async def load_zones_from_file(file_relative_path: Path) -> pt.DataFrame[Zone]:
    zones = pd.read_csv(
        app_config.path_of_data / file_relative_path,
        compression="infer",
        header=None,
        names=["date", "lower", "upper", "priority", "enabled", "note"],
        dtype=str,
        keep_default_na=False,
        on_bad_lines="error",
    )
    if not zones.empty and "date" in zones.iloc[0]["date"].strip().lower():
        zones = zones.iloc[1:]
    return normalize_mt5_zone_rows(zones)


@pandera_validate(allow_pandas_dataframe=True)
def normalize_mt5_zone_rows(zones: pd.DataFrame) -> pt.DataFrame[Zone]:
    """Apply visible LoadAllRawZones row filters before the typed frame boundary."""
    zones = zones.copy()
    date_text = zones["date"].str.strip()
    enabled = ~zones["enabled"].str.strip().str.lower().isin(["false", "0", "no", "off"])
    dates = pd.to_datetime(date_text, format="%Y.%m.%d", errors="coerce", utc=True)
    priority = zones["priority"].str.strip().str.lower()
    lower = pd.to_numeric(zones["lower"].str.strip(), errors="coerce")
    upper = pd.to_numeric(zones["upper"].str.strip(), errors="coerce")
    valid = (
        dates.notna()
        & dates.gt(pd.Timestamp(0, tz="UTC"))
        & dates.dt.strftime("%Y.%m.%d").eq(date_text)
        & priority.isin(["normal", "high"])
        & lower.gt(0)
        & upper.gt(0)
    )
    rejected = enabled & date_text.ne("") & ~valid
    if rejected.any():
        log_w(f"MT5 zone input: skipped {int(rejected.sum())} invalid enabled rows")
    keep = enabled & valid
    zones = zones.loc[keep].copy()
    zones["date"] = dates.loc[keep].astype(pd.DatetimeTZDtype(unit="ns", tz="UTC"))
    zones["lower"] = pd.concat([lower, upper], axis=1).min(axis=1).loc[keep].astype(float)
    zones["upper"] = pd.concat([lower, upper], axis=1).max(axis=1).loc[keep].astype(float)
    zones["priority"] = priority.loc[keep]
    zones["enabled"] = True
    zones["timeframe"] = "15min"
    return Zone.validate(zones.set_index(["timeframe", "date"]))
