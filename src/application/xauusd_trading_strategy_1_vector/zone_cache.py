from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import pandas as pd
from br_py_log_n_profile import profile_it

from domain.schemas.zone import Zone
from domain.xau_usd.models import XauZone
from helper.importer import pt
from helper.pandera import pandera_validate


class ZoneCache:
    """Daily merged zones prepared from supplied data, with no I/O or lazy loading."""

    @pandera_validate
    def __init__(self, zone_data: pt.DataFrame[Zone]) -> None:
        zones = Zone.validate(zone_data.copy(deep=True))
        days = zones.index.get_level_values("date").strftime("%Y-%m-%d")
        self._cached_zones: dict[str, list[XauZone]] = {}
        for day, daily in zones.groupby(days, sort=False):
            raw = [
                XauZone(
                    id="",
                    low=min(row.lower, row.upper),
                    high=max(row.lower, row.upper),
                    priority=int(row.priority == "high"),
                )
                for number, row in enumerate(daily.loc[daily["enabled"]].itertuples(), start=1)
            ]
            for i in range(len(raw) - 1):
                for j in range(i + 1, len(raw)):
                    if raw[j].low < raw[i].low:
                        raw[i], raw[j] = raw[j], raw[i]
            merged: list[XauZone] = []
            for number, zone in enumerate(raw, start=1):
                zone.id = f"R{number}"
                if merged and zone.low - merged[-1].high < 1.5:
                    previous = merged[-1]
                    previous.low = min(previous.low, zone.low)
                    previous.high = max(previous.high, zone.high)
                    previous.priority = max(previous.priority, zone.priority)
                    previous.id += "&" + zone.id
                else:
                    merged.append(zone)
            self._cached_zones[day] = merged

    @profile_it
    def get_zones_for_day(
        self,
        broker_day: datetime | str,
    ) -> list[XauZone]:
        day = pd.Timestamp(broker_day).strftime("%Y-%m-%d")
        return deepcopy(self._cached_zones.get(day, []))


ZoneCache = ZoneCache
