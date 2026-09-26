import pandas as pd

from application.xauusd_trading_strategy_1_vector import __main__ as entry
from application.xauusd_trading_strategy_1_vector.reporting import print_strategy_summary

# from application.xauusd_trading_strategy_1_vector.sample_data import create_sample_tick_data

# def market_inputs():
#     ticks = create_sample_tick_data(end_time="2026-09-18 00:31:00", tick_interval_seconds=60)
#     ticks = ticks.reorder_levels(["symbol", "broker", "date", "precise_time"])
#     dates = pd.DatetimeIndex(["2026-09-18"], tz="UTC").as_unit("ns")
#     zones = pd.DataFrame(
#         {"lower": [2000.0], "upper": [2001.0], "priority": ["high"], "enabled": [True]},
#         index=pd.MultiIndex.from_arrays([["15min"], dates], names=["timeframe", "date"]),
#     )
#     candles = pd.DataFrame(
#         {"open": [2000.0], "high": [2001.0], "low": [1999.0], "close": [2000.5]},
#         index=zones.index,
#     )
#     return ticks, candles, zones


def mock_fetches(monkeypatch, ticks, candles, zones):
    async def fetch_zones(*args, **kwargs):
        return zones

    async def fetch_ticks(*args, **kwargs):
        return ticks

    async def fetch_candles(*args, **kwargs):
        return candles

    monkeypatch.setattr(entry, "load_zones_from_file", fetch_zones)
    monkeypatch.setattr(entry, "get_ticks", fetch_ticks)
    monkeypatch.setattr(entry, "get_ohlcv", fetch_candles)


# @pytest.mark.parametrize("format", ["csv", "parquet"])
# @pytest.mark.parametrize("debug", [False, True])
# def test_cli_writes_results_with_real_fetch_schemas(monkeypatch, tmp_path, format, debug):
#     ticks, candles, zones = market_inputs()
#     mock_fetches(monkeypatch, ticks, candles, zones)
#     output = tmp_path / "nested" / f"results.{format}"
#     args = ["--output", str(output)] + (["--debug"] if debug else [])
#     invocation = CliRunner().invoke(entry.app, args)
#     assert invocation.exit_code == 0, invocation.exception
#     saved = pd.read_csv(output) if format == "csv" else pd.read_parquet(output)
#     assert len(saved) == len(ticks)
#     assert not saved.columns.duplicated().any()
#     assert "candle_close" in saved
#     assert ("trend_count" in saved) == debug


# def test_candle_context_is_causal_and_preserves_duplicate_index():
#     ticks, candles, _ = market_inputs()
#     ticks = pd.concat([ticks.iloc[:1], ticks])
#     candles = candles.reset_index().rename(columns={"date": "bar_time"}).assign(broker="MT5", symbol="XAUUSD")
#     result = merge_results_with_candles(ticks, candles)
#     assert result.index.equals(ticks.index)
#     assert result.iloc[:16].candle_high.isna().all()
#     assert result.iloc[16:31].candle_high.eq(2001).all()
#     assert result.iloc[31:].candle_high.isna().all()
#     pd.testing.assert_frame_equal(result[ticks.columns], ticks)
#     changed = candles.assign(high=9999)
#     pd.testing.assert_frame_equal(result.iloc[:16], merge_results_with_candles(ticks, changed).iloc[:16])


# def test_duplicate_candles_are_rejected_without_multiplying_ticks():
#     ticks, candles, _ = market_inputs()
#     candles = candles.reset_index().rename(columns={"date": "bar_time"}).assign(broker="MT5", symbol="XAUUSD")
#     with pytest.raises(pd.errors.MergeError):
#         merge_results_with_candles(ticks, pd.concat([candles, candles]))


# def test_fetch_range_includes_last_minute_but_excludes_next_day(monkeypatch, tmp_path):
#     ticks, candles, zones = market_inputs()
#     ticks = create_sample_tick_data(
#         start_time="2026-09-18 23:59:00", end_time="2026-09-19 00:00:00", tick_interval_seconds=30
#     )
#     mock_fetches(monkeypatch, ticks, candles, zones)

#     async def fetch_ticks(*args, **kwargs):
#         start, end = time_range(kwargs["time_range_str"])
#         assert pd.Timestamp(start) == pd.Timestamp("2026-09-18", tz="UTC")
#         assert pd.Timestamp(end) == pd.Timestamp("2026-09-19", tz="UTC")
#         return ticks

#     monkeypatch.setattr(entry, "get_ticks", fetch_ticks)
#     output = tmp_path / "end.csv"
#     asyncio.run(entry.main(output=str(output)))
#     saved = pd.read_csv(output)
#     assert len(saved) == 2
#     assert saved.datetime.str.contains("23:59").all()


# def test_bad_output_extension_fails_before_fetch(monkeypatch):
#     async def unexpected(*args, **kwargs):
#         pytest.fail("Invalid output must fail before fetching market data")
#
#     monkeypatch.setattr(entry, "load_zones_from_file", unexpected)
#     with pytest.raises(ValueError, match="extension"):
#         asyncio.run(entry.main(output="result.txt"))


# @pytest.mark.parametrize("format", ["csv", "parquet"])
# def test_candidate_objects_export_as_json_without_mutation(tmp_path, format):
#     ticks, _, _ = market_inputs()
#     result = ticks.iloc[:2].copy()
#     candidate = XauSignalCandidate(
#         candidate_id="BO1",
#         parent_breakout_id="",
#         bar_id="bar",
#         zone_id="zone",
#         family=XauSignalFamily.BREAKOUT,
#         direction=XauDirection.BUY,
#         order_type=XauOrderType.MARKET,
#         signal_time=pd.Timestamp("2026-09-18", tz="UTC"),
#         entry_price=2002.0,
#     )
#     result["breakout_signals"] = pd.Series([(candidate,), ()], index=result.index, dtype=object)
#     original = result.copy(deep=True)
#     output = tmp_path / f"candidates.{format}"
#     save_results_to_file(result, str(output), format)
#     saved = pd.read_csv(output) if format == "csv" else pd.read_parquet(output)
#     assert json.loads(saved.breakout_signals.iloc[0])[0]["candidate_id"] == "BO1"
#     assert json.loads(saved.breakout_signals.iloc[1]) == []
#     pd.testing.assert_frame_equal(result, original)


def test_summary_counts_candidates_not_non_null_containers(capsys):
    print_strategy_summary(pd.DataFrame({"breakout_signals": [(), ("a", "b"), None]}))
    assert "Breakout signals: 2" in capsys.readouterr().out


# @pytest.mark.parametrize("empty_input", ["ticks", "zones"])
# def test_empty_market_input_fails_without_writing(monkeypatch, tmp_path, empty_input):
#     ticks, candles, zones = market_inputs()
#     if empty_input == "ticks":
#         ticks = ticks.iloc[:0]
#     else:
#         zones = zones.iloc[:0]
#     mock_fetches(monkeypatch, ticks, candles, zones)
#     output = tmp_path / "empty.csv"
#     with pytest.raises(ValueError):
#         asyncio.run(entry.main(output=str(output)))
#     assert not output.exists()


# def test_mt5_ticks_keep_requested_symbol(monkeypatch):
#     from infrastructure.mt5 import tick as source
#
#     raw = np.zeros(
#         1,
#         dtype=[
#             ("time", "int64"),
#             ("time_msc", "int64"),
#             ("bid", "float64"),
#             ("ask", "float64"),
#             ("last", "float64"),
#             ("volume", "uint64"),
#             ("flags", "uint32"),
#             ("volume_real", "float64"),
#         ],
#     )
#     raw["time_msc"] = 1_789_689_600_000
#     raw["bid"], raw["ask"] = 2000, 2000.2
#
#     async def verify(symbol):
#         return symbol
#
#     monkeypatch.setattr(source, "verify_symbol", verify)
#     monkeypatch.setattr(source.mt5, "copy_ticks_range", lambda *args: raw)
#     result = asyncio.run(source.get_ticks("26-09-18.00-00T26-09-19.00-00", symbol="XAUUSD.custom"))
#     assert result.index.get_level_values("symbol").tolist() == ["XAUUSD.custom"]


# @pytest.mark.parametrize("kind", ["tick", "ohlcv"])
# def test_mt5_none_response_reports_broker_error(monkeypatch, kind):
#     from infrastructure.mt5 import ohlcv, tick
#
#     source = tick if kind == "tick" else ohlcv
#
#     async def verify(symbol):
#         return symbol
#
#     monkeypatch.setattr(source, "verify_symbol", verify)
#     method = "copy_ticks_range" if kind == "tick" else "copy_rates_range"
#     monkeypatch.setattr(source.mt5, method, lambda *args: None)
#     monkeypatch.setattr(source.mt5, "last_error", lambda: (-1, "synthetic unavailable"))
#     coroutine = (
#         source.get_ticks("26-09-18.00-00T26-09-19.00-00", symbol="XAUUSD")
#         if kind == "tick"
#         else source.get_ohlcv("XAUUSD", "26-09-18.00-00T26-09-19.00-00", "15min")
#     )
#     with pytest.raises(RuntimeError, match="synthetic unavailable"):
#         asyncio.run(coroutine)
