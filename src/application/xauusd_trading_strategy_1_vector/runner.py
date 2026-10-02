from __future__ import annotations

from br_py_log_n_profile import profile_it

from application.xauusd_trading_strategy_1_vector.domain.schema import StrategyCandles, VectorizedTick
from br_pre_commit import pandera_validate
from domain.schemas.zone import Zone
from helper.importer import pt
from infrastructure.result_processing.__main__ import (
    generate_order_management_columns,
    generate_position_tracking_columns,
    merge_results_with_candles,
)
from infrastructure.result_processing.io import ResultFilesManifest

from .config.core_vectors import core_vectors
from .config.strategy_config import strategy_config
from .domain.replay import ReplayConfig
from .the_strategy import VectorizedXauUsdStrategy
from .zone_cache import ZoneCache


@profile_it
@pandera_validate
def run_vectorized_strategy(
    tick_df: pt.DataFrame[VectorizedTick],
    candle_df: pt.DataFrame[StrategyCandles],
    zones_df: pt.DataFrame[Zone],
    *,
    debug: bool = False,
    execution: ReplayConfig | None = None,
) -> ResultFilesManifest:
    """Persist source frames once, then hand off only the manifest between stages."""
    with core_vectors.use(), strategy_config.use():
        manifest = ResultFilesManifest()
        try:
            for day, ticks in tick_df.groupby("broker_day", sort=False):
                times = candle_df.index.get_level_values("bar_time")
                candles = candle_df.loc[times <= ticks.bar_time.max()]
                manifest.save_daily_ticks(day, ticks)
                manifest.save_daily_candles(day, candles)
            strategy = VectorizedXauUsdStrategy(ZoneCache(zones_df), execution)
            manifest = strategy.process_tick_data(manifest)
            manifest = merge_results_with_candles(manifest)
            manifest = generate_order_management_columns(manifest)
            manifest = generate_position_tracking_columns(manifest)
            manifest.wait_for_writes()
            return manifest
        finally:
            manifest.close()
