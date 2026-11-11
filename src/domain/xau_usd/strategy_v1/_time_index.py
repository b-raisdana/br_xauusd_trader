import pandas as pd


def utc_times(index: pd.Index) -> pd.DatetimeIndex:
    if isinstance(index, pd.MultiIndex):
        if "date" not in index.names:
            raise ValueError("MultiIndex must contain a date level")
        if "timeframe" in index.names and index.get_level_values("timeframe").nunique() != 1:
            raise ValueError("input must contain a single timeframe")
        times = index.get_level_values("date")
    elif isinstance(index, pd.DatetimeIndex):
        times = index
    else:
        raise ValueError("index must be a DatetimeIndex or a single-timeframe index with a date level")

    if times.tz is None or str(times.tz) != "UTC":
        raise ValueError("timestamps must be UTC-aware")
    if not times.is_monotonic_increasing or not times.is_unique:
        raise ValueError("timestamps must be strictly increasing and unique")
    return times
