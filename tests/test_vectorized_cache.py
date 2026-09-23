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


# def test_strategy_runs_with_only_preloaded_data():
#     ticks = create_sample_tick_data(start_time="2026-09-18 00:00:00", end_time="2026-09-18 00:02:00")
#     original = ticks.copy(deep=True)
#     result = VectorizedXauUsdStrategy(ZoneCache(zones())).process_tick_data(ticks, candles_from_ticks(ticks))
#     assert result.index.equals(ticks.index)
#     pd.testing.assert_frame_equal(ticks, original)


# def test_strategy_requires_explicit_cache():
#     with pytest.raises(TypeError):
#         VectorizedXauUsdStrategy()


# def test_entrypoint_fetches_all_inputs_before_cache_construction(monkeypatch):
#     from application.xauusd_trading_strategy_1_vector import __main__ as entry
#     from application.xauusd_trading_strategy_1_vector import strategy_runner as runner

#     events = []
#     tick_frame = create_sample_tick_data(start_time="2026-09-18 00:00:00", end_time="2026-09-18 00:02:00")
#     candle_frame = pd.DataFrame(
#         {"open": [2000.0], "high": [2001.0], "low": [1999.0], "close": [2000.0]},
#         index=pd.MultiIndex.from_arrays(
#             [["15min"], pd.DatetimeIndex(["2026-09-18"], tz="UTC")],
#             names=["timeframe", "date"],
#         ),
#     )

#     async def fetch_zones(*args, **kwargs):
#         events.append("zones")
#         return zones()

#     async def fetch_ticks(*args, **kwargs):
#         events.append("ticks")
#         return tick_frame

#     async def fetch_candles(*args, **kwargs):
#         events.append("candles")
#         return candle_frame

#     def cache(data):
#         assert events == ["zones", "ticks", "candles"]
#         events.append("cache")
#         return ZoneCache(data)

#     monkeypatch.setattr(entry, "load_zones_from_file", fetch_zones)
#     monkeypatch.setattr(entry, "get_ticks", fetch_ticks)
#     monkeypatch.setattr(entry, "get_ohlcv", fetch_candles)
#     monkeypatch.setattr(runner, "ZaoneCache", cache)
#     monkeypatch.setattr(entry, "save_results_to_file", lambda *args: None)
#     monkeypatch.setattr(entry, "print_strategy_summary", lambda *args: None)
#     asyncio.run(entry.main())
#     assert events == ["zones", "ticks", "candles", "cache"]
