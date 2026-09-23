from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import app_config
from domain.schemas.zone import Zone
from helper import pandera
from helper.importer import pt


class ZoneCache:
    """
    Load and manage zone data for the vectorized strategy.

    This corresponds to the zone loading logic in MT5 (LoadGeneratedRawZones)
    and the zone merging logic (BuildMergedZones).
    """

    _cached_zones: pt.DataFrame[Zone]

    def __init__(self, zone_data: pt.DataFrame[Zone]) -> None:
        """
        Initialize the zone loader.

        Args:
            zones_file_relative_path: Path to the zones file (e.g., generated/DailyZones.mqh)
                           If None, uses default path
        """
        # self.zones_file_path = app_config.path_of_data / zones_file_relative_path
        # or self._default_zones_path()
        self._cached_zones = zone_data

    # def _default_zones_path(self) -> str:
    #     """
    #     Get the default zones file path.
    #
    #     This would typically point to the generated zones file.
    #     """
    #     # Default to the generated zones file in the MT5 directory
    #     return app_config.path_of_data / app_config["zones_file_path"]

    @pandera.pandera_validate
    def get_zones_for_day(self, broker_day: str) -> pt.DataFrame[Zone]:
        """
        Load zones for a specific broker day.

        Args:
            broker_day: Day in format "YYYY-MM-DD" or "YYYY.MM.DD"

        Returns:
            List of merged zones for the day
        """
        # # Check cache first
        # if broker_day in self._cached_zones:
        #     return self._cached_zones[broker_day]

        # Try both date formats
        # zones = await self._load_zones_from_file(broker_day)
        day = pd.Timestamp(broker_day, tz="UTC")
        dates = self._cached_zones.index.get_level_values("date")
        day_zones = self._cached_zones.loc[(dates >= day) & (dates < day + pd.Timedelta(days=1))].copy()
        return day_zones
        # if not zones:
        #     # Try MT5 format with dots
        #     mt5_format = broker_day.replace("-", ".")
        #     zones = self._load_zones_from_file(mt5_format)

        # if zones:
        #     # Merge overlapping zones
        #     merged_zones = build_merged_zones(zones, broker_day.replace(".", "-"))
        #     self._cached_zones[broker_day] = merged_zones
        #     return merged_zones
        #
        # return []

    # @pandera.pandera_validate
    # async def _load_zones_from_file(self, broker_day: str) -> pt.DataFrame[Zone]:
    #     """
    #     Load raw zones from the zones file for a specific day.
    #
    #     This is a simplified version - in a full implementation,
    #     this would parse the actual MT5 generated zones file.
    #     """
    #     all_zones = await self.load_all_zones()
    #     day = pd.to_datetime(broker_day).date()
    #     day_zones = all_zones[
    #         day <= all_zones.index.get_level_values("date") < (day + timedelta(days=1))
    #         ]
    #     return day_zones

    # async def load_all_zones(self, file_relative_path: Path | None = None) -> pt.DataFrame[Zone]:
    #     full_path = (
    #         str(app_config.path_of_data / file_relative_path) if file_relative_path else self.zones_file_path
    #     )
    #     zones = pd.read_csv(full_path, compression="zip", parse_dates=["date"])  # todo: implement async-to-thread
    #     assert isinstance(zones, pd.DataFrame)
    #
    #     zones["date"] = pd.to_datetime(zones["date"], utc=True).astype(pd.DatetimeTZDtype(unit="ns", tz="UTC"))
    #     zones["timeframe"] = "15min"
    #     zones = zones.astype(
    #         {
    #             "enabled": bool,
    #             "lower": float,
    #             "upper": float,
    #         }
    #     )
    #     zones.set_index(["timeframe", "date"], inplace=True)
    #
    #     return zones

    # def preload_zones(self, days: List[str]) -> None:
    #     """
    #     Preload zones for specific days.
    #
    #     Args:
    #         days: List of broker_day strings to preload
    #     """
    #     for day in days:
    #         self.get_zones_for_day(day)

    # def clear_cache(self) -> None:
    #     """Clear the cached zones."""
    #     self._cached_zones.clear()


@pandera.pandera_validate
async def load_zones_from_file(file_relative_path: Path) -> pt.DataFrame[Zone]:
    zones = pd.read_csv(str(app_config.path_of_data / file_relative_path), compression="zip", parse_dates=["date"])
    assert isinstance(zones, pd.DataFrame)

    zones["date"] = pd.to_datetime(zones["date"], utc=True).astype(pd.DatetimeTZDtype(unit="ns", tz="UTC"))
    zones["timeframe"] = "15min"
    zones = zones.astype(
        {
            "enabled": bool,
            "lower": float,
            "upper": float,
        }
    )
    zones.set_index(["timeframe", "date"], inplace=True)

    # full_path = (
    #     str(app_config.path_of_data / file_relative_path) if file_relative_path else self.zones_file_path
    # )
    # zones = pd.read_csv(full_path, compression="zip", parse_dates=["date"])  # todo: implement async-to-thread
    # assert isinstance(zones, pd.DataFrame)
    #
    # zones["date"] = pd.to_datetime(zones["date"], utc=True).astype(pd.DatetimeTZDtype(unit="ns", tz="UTC"))
    # zones["timeframe"] = "15min"
    # zones = zones.astype(
    #     {
    #         "enabled": bool,
    #         "lower": float,
    #         "upper": float,
    #     }
    # )
    # zones.set_index(["timeframe", "date"], inplace=True)

    # zl = ZoneCache(file_relative_path)
    # zones = await zl.load_all_zones()

    return zones
