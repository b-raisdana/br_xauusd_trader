from __future__ import annotations

from typing import Dict, List, Optional

from domain.xau_usd.models import XauZone
from domain.xau_usd.zone import build_merged_zones


class ZoneLoader:
    """
    Load and manage zone data for the vectorized strategy.

    This corresponds to the zone loading logic in MT5 (LoadGeneratedRawZones)
    and the zone merging logic (BuildMergedZones).
    """

    def __init__(self, zones_file_path: Optional[str] = None):
        """
        Initialize the zone loader.

        Args:
            zones_file_path: Path to the zones file (e.g., generated/DailyZones.mqh)
                           If None, uses default path
        """
        self.zones_file_path = zones_file_path or self._default_zones_path()
        self._cached_zones: Dict[str, List[XauZone]] = {}

    def _default_zones_path(self) -> str:
        """
        Get the default zones file path.

        This would typically point to the generated zones file.
        """
        # Default to the generated zones file in the MT5 directory
        return "mt5/generated/DailyZones.mqh"

    def load_zones_for_day(self, broker_day: str) -> List[XauZone]:
        """
        Load zones for a specific broker day.

        Args:
            broker_day: Day in format "YYYY-MM-DD" or "YYYY.MM.DD"

        Returns:
            List of merged zones for the day
        """
        # Check cache first
        if broker_day in self._cached_zones:
            return self._cached_zones[broker_day]

        # Try both date formats
        zones = self._load_zones_from_file(broker_day)
        if not zones:
            # Try MT5 format with dots
            mt5_format = broker_day.replace("-", ".")
            zones = self._load_zones_from_file(mt5_format)

        if zones:
            # Merge overlapping zones
            merged_zones = build_merged_zones(zones, broker_day.replace(".", "-"))
            self._cached_zones[broker_day] = merged_zones
            return merged_zones

        return []

    def _load_zones_from_file(self, broker_day: str) -> List[XauZone]:
        """
        Load raw zones from the zones file for a specific day.

        This is a simplified version - in a full implementation,
        this would parse the actual MT5 generated zones file.
        """
        # This is a placeholder for the actual file parsing logic
        # The MT5 implementation uses LoadGeneratedRawZones which reads
        # from the generated/DailyZones.mqh file

        # For now, return empty list
        # In a full implementation, this would:
        # 1. Read the zones file
        # 2. Parse zone definitions for the specific day
        # 3. Return list of XauZone objects

        return []

    def load_all_zones(self) -> Dict[str, List[XauZone]]:
        """
        Load zones for all available days.

        Returns:
            Dictionary mapping broker_day to list of merged zones
        """
        # This would scan the zones file and load all available days
        # For now, return empty dict
        return {}

    def preload_zones(self, days: List[str]) -> None:
        """
        Preload zones for specific days.

        Args:
            days: List of broker_day strings to preload
        """
        for day in days:
            self.load_zones_for_day(day)

    def clear_cache(self) -> None:
        """Clear the cached zones."""
        self._cached_zones.clear()
