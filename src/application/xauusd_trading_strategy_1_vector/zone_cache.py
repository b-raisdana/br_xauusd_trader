from __future__ import annotations

from copy import deepcopy

import pandas as pd
from br_py_log_n_profile import profile_it

from domain.schemas.zone import Zone
from domain.xau_usd.models import XauZone
from domain.xau_usd.zone import build_merged_zones
from helper.importer import pt
from helper.pandera import pandera_validate


class ZoneCache:
    """Daily merged zones prepared from supplied data, with no I/O or lazy loading."""

    @pandera_validate
    def __init__(self, zone_data: pt.DataFrame[Zone]):
        zones = Zone.validate(zone_data.copy(deep=True))
        days = zones.index.get_level_values("date").strftime("%Y-%m-%d")
        self._cached_zones = {}
        for day, daily in zones.groupby(days, sort=False):
            raw = [
                XauZone(id=f"{day}:R{number}", low=row.lower, high=row.upper, priority=int(row.priority == "high"))
                for number, row in enumerate(daily.loc[daily["enabled"]].itertuples(), start=1)
            ]
            self._cached_zones[day] = build_merged_zones(raw, day)

    @profile_it
    def get_zones_for_day(self, broker_day: str) -> list[XauZone]:
        day = pd.Timestamp(broker_day).strftime("%Y-%m-%d")
        return deepcopy(self._cached_zones.get(day, []))


ZoneCache = ZoneCache
