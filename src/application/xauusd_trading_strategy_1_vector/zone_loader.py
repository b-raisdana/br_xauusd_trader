from pathlib import Path

import pandas as pd
from br_py_log_n_profile import profile_it

from config import app_config
from domain.schemas.zone import Zone
from helper.importer import pt
from helper.pandera import pandera_validate


@profile_it
@pandera_validate
async def load_zones_from_file(file_relative_path: Path) -> pt.DataFrame[Zone]:
    zones = pd.read_csv(app_config.path_of_data / file_relative_path, compression="infer", parse_dates=["date"])
    zones["date"] = pd.to_datetime(zones["date"], utc=True).astype(pd.DatetimeTZDtype(unit="ns", tz="UTC"))
    zones["timeframe"] = "15min"
    zones = zones.astype({"lower": float, "upper": float})
    return Zone.validate(zones.set_index(["timeframe", "date"]))
