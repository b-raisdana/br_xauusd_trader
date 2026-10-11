import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from pandera.errors import SchemaErrors
from vectorized_fixtures import calculate_manifest, candles_from_ticks, with_native_bootstrap

from application.xauusd_trading_strategy_1_vector.domain.replay import LinearReplayEconomics, ReplayConfig
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy
from domain.xau_usd.models import XauZone


class Zones:
    def get_zones_for_day(self, day):
        return [XauZone("z", 100, 102)]


def inputs(symbol="XAUUSD!", offset=0.0):
    times = pd.date_range("2026-09-18", periods=4, freq="5min", tz="UTC").as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [["test"] * len(times), [symbol] * len(times), times.normalize(), times],
        names=["broker", "symbol", "date", "precise_time"],
    )
    prices = np.array([99.0, 100.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0]) + offset
    prices = np.array([99.0, 100.0, 103.0, 104.0]) + offset
    ticks = pd.DataFrame({
        "bid": prices,
        "ask": prices + 0.2,
        "last": prices,
        "volume": np.zeros(len(times), dtype=np.uint64),
        "flags": np.zeros(len(times), dtype=np.uint32),
        "volume_real": np.zeros(len(times)),
    }, index=index.reorder_levels(["symbol", "broker", "date", "precise_time"]),
    )
    ticks = VectorizedXauUsdStrategy.add_bar_time_n_broker_day(ticks)
    candles = with_native_bootstrap(candles_from_ticks(ticks))
    return ticks, candles
    from application.xauusd_trading_strategy_1_vector.domain.columnar import SignalTickState
    from application.xauusd_trading_strategy_1_vector.runner import run_vectorized_strategy

    a, ca = inputs()
    b, cb = inputs("SECOND", 100.0)
    dates = pd.DatetimeIndex(["2026-09-18"], tz="UTC").as_unit("ns")
    zones = pd.DataFrame(
        {"lower": [100.0], "upper": [102.0], "priority": ["high"], "enabled": [True]},
        index=pd.MultiIndex.from_arrays([["15min"], dates], names=["timeframe", "date"]),
    )
    manifest = run_vectorized_strategy(pd.concat([a, b]), pd.concat([ca, cb]), zones)
    result = manifest.read_daily_signal_state(pd.Timestamp("2026-09-18", tz="UTC"))
    SignalTickState.validate(result)
    second = result.xs("SECOND", level="symbol")
    assert second.bar_open.min() >= 199.0


def test_main_runs_with_fetch_shaped_inputs_and_writes_parquet(monkeypatch, tmp_path):
    import asyncio

    from application.xauusd_trading_strategy_1_vector import __main__ as entry
    from config import app_config

    monkeypatch.setattr(app_config, "path_of_data", tmp_path)

    ticks, candles = inputs()
    raw_ticks = ticks.drop(columns=["bar_time", "broker_day"])
    raw_candles = (
        candles.reset_index()
        .drop(columns=["broker", "symbol", "date", "timeframe"])
        .rename(columns={"bar_time": "date"})
        .set_index("date")
    )
    dates = pd.DatetimeIndex(["2026-09-18"], tz="UTC").as_unit("ns")
    zones = pd.DataFrame(
        {"lower": [100.0], "upper": [102.0], "priority": ["high"], "enabled": [True]},
        index=pd.MultiIndex.from_arrays([["15min"], dates], names=["timeframe", "date"]),
    )

    async def fetch_ticks(*args, **kwargs):
        return raw_ticks

    async def fetch_candles(*args, **kwargs):
        return raw_candles

    async def fetch_zones(*args, **kwargs):
        return zones

    monkeypatch.setattr(entry, "get_ticks", fetch_ticks)
    monkeypatch.setattr(entry, "get_ohlcv", fetch_candles)
    monkeypatch.setattr(entry, "load_zones_from_file", fetch_zones)
    (tmp_path / "ranges.zip").write_text("dummy")
    output = "results.parquet"
    asyncio.run(entry.main(output_file=output, backtest=False))
    saved = pd.read_parquet(tmp_path / output)
    assert len(saved) == len(ticks)
    assert saved.bid.tolist() == ticks.bid.tolist()
    assert {"stream_tick", "breakout_sequence", "pullback_active"} <= set(saved)
    assert not {"orders", "positions", "breakout_signals"}.intersection(saved)
    assert pd.read_parquet((tmp_path / output).with_name("results_signals.parquet")).family.isin([0, 1, 2]).all()
    assert (tmp_path / output).with_name("results_windows.parquet").exists()



