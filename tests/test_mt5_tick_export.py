from datetime import timezone

import pytest

from scripts.export_mt5_ticks import cache_output, utc_datetime


def test_tick_export_requires_utc_and_ignored_cache_output() -> None:
    parsed = utc_datetime("2026-08-28T00:00:00+00:00")
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
    with pytest.raises(Exception, match="UTC offset"):
        utc_datetime("2026-08-28T00:00:00")
    assert cache_output("data/cache/xauusd.csv").parts[-3:] == (
        "data",
        "cache",
        "xauusd.csv",
    )
    with pytest.raises(Exception, match="data/cache"):
        cache_output("data/xauusd.csv")
