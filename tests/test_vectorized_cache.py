import pandas as pd

from application.xauusd_trading_strategy_1_vector import ZoneCache


def zones():
    return pd.DataFrame(
        {"lower": [2000.0, 2002.0], "upper": [2001.0, 2003.0], "priority": ["normal", "high"], "enabled": [True, True]},
        index=pd.MultiIndex.from_arrays(
            [["15min"] * 2, pd.DatetimeIndex(["2026-09-18"] * 2, tz="UTC").as_unit("ns")],
            names=["timeframe", "date"],
        ),
    )


def test_cache_merges_zones_and_isolates_mutations():
    source = zones()
    cache = ZoneCache(source)
    source.loc[:, "lower"] = 0.0
    result = cache.get_zones_for_day("2026.09.18")
    assert [(z.low, z.high, z.priority) for z in result] == [(2000.0, 2003.0, 1)]
    result[0].low = 0.0
    assert cache.get_zones_for_day("2026-09-18")[0].low == 2000.0
    assert cache.get_zones_for_day("2026-09-19") == []
