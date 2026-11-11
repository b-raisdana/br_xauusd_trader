from datetime import datetime
from functools import lru_cache
from typing import Annotated

import pandas as pd
from br_py_log_n_profile import log_d


def _as_tz_aware(value: datetime, convert: bool = False) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if not convert:
        assert ts.tzinfo
        return ts
    log_d("Not tested")
    out = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    assert isinstance(out, pd.Timestamp)
    return out


TZAware = Annotated[pd.Timestamp, "timezone-aware"]


@lru_cache
def timeframe_to_period(timeframe: str) -> pd.Timedelta:
    """Fixed duration of one `timeframe` candle. All configured timeframes are fixed-length
    (crypto trades 24/7, no DST), so a plain Timedelta is exact -- including "1W" -> 7 days."""
    _t = pd.Timedelta(days=7) if timeframe == "1W" else pd.Timedelta(timeframe)
    assert isinstance(_t, pd.Timedelta)
    return _t


@lru_cache(maxsize=1024 * 1024)
def fix_tz(timestamp: pd.Timestamp) -> TZAware:
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp
