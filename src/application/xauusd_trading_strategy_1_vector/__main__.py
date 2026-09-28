"""Command-line entry point and compatibility exports for the vectorized strategy."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import typer
from br_py_log_n_profile import log_d, log_e, log_exception, profile_it

from application.xauusd_trading_strategy_1_vector import VectorizedXauUsdStrategy
from application.xauusd_trading_strategy_1_vector.zone_loader import load_zones_from_file
from config import app_config
from domain.xau_usd.zone import build_merged_zones
from helper.date_utils import EPSILON_TIME, time_range_to_string
from infrastructure.mt5.ohlcv import get_ohlcv
from infrastructure.mt5.tick import get_ticks
from infrastructure.result_processing.__main__ import (
    generate_order_management_columns,
    generate_position_tracking_columns,
    merge_results_with_candles,
)

from .reporting import (
    print_strategy_summary,
    save_results_to_file,
)
from .runner import run_vectorized_strategy

__all__ = [
    "run_vectorized_strategy",
    "merge_results_with_candles",
    "generate_order_management_columns",
    "generate_position_tracking_columns",
    "save_results_to_file",
    "print_strategy_summary",
    "main",
    "build_merged_zones",
]

app = typer.Typer(help="Vectorized XAUUSD Trading Strategy", add_completion=False)


@app.command()
def cli(
    symbol: str = typer.Option(app_config.default_symbol, help="The symbol to use"),
    zones: Path = typer.Option(Path("ranges.zip"), help="Path to zones CSV file"),
    output: str = typer.Option("strategy_results.parquet", help="Path to output file"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    backtest: bool = typer.Option(True, "--backtest", help="Run vectorbt backtest report after strategy execution"),
) -> None:
    asyncio.run(main(symbol=symbol, zones=zones, output=output, debug=debug, backtest=backtest))


@profile_it
async def main(
    symbol: str = app_config.default_symbol,
    zones: Path = Path("ranges.zip"),
    output: str = "strategy_results.parquet",
    debug: bool = False,
    backtest: bool = False,
) -> None:
    output_format = Path(output).suffix.lstrip(".").lower()
    if output_format not in {"csv", "parquet"}:
        log_e("Output must have a .csv or .parquet extension")
        raise ValueError("Output must have a .csv or .parquet extension")
    print("Loading data ...")

    zones_df = await load_zones_from_file(zones)
    # datetime_of_first_zone = zones_df.index.get_level_values("date")[0]
    # next_day_after_first_zone = zones_df.index.get_level_values("date")[0] + pd.Timedelta(days=1)
    # zones_df = zones_df[
    #     (
    #         (datetime_of_first_zone <= zones_df.index.get_level_values("date"))
    #         & (zones_df.index.get_level_values("date") < next_day_after_first_zone)
    #     )
    # ]

    if zones_df.empty:
        log_exception("Zone input must contain at least one day", ValueError)
    start = zones_df.index.get_level_values("date").min().normalize()
    end = zones_df.index.get_level_values("date").max().normalize() + pd.Timedelta(hours=2) - EPSILON_TIME
    time_range_str = time_range_to_string(start=start, end=end)
    tick_df = await get_ticks(time_range_str=time_range_str, symbol=symbol)
    tick_times = tick_df.index.get_level_values("precise_time")

    out_of_boundary_ticks = tick_df.loc[((tick_times < start) | (tick_times >= end))]
    assert out_of_boundary_ticks.empty

    if tick_df.empty:
        log_e("No ticks returned for the requested zone days")
        raise ValueError("No ticks returned for the requested zone days")

    candle_15min_df = await get_ohlcv(symbol, time_range_str=time_range_str, timeframe="15min")
    candle_15min_df = candle_15min_df.reset_index().rename(columns={"date": "bar_time"})
    candle_15min_df["bar_time"] = candle_15min_df["bar_time"].astype("datetime64[ns, UTC]")
    candle_15min_df["date"] = candle_15min_df["bar_time"].dt.normalize()
    candle_15min_df["broker"] = tick_df.index.get_level_values("broker")[0]
    candle_15min_df["symbol"] = symbol
    if "timeframe" not in candle_15min_df:
        candle_15min_df["timeframe"] = "15min"
    candle_15min_df = candle_15min_df.set_index(["date", "timeframe", "broker", "symbol", "bar_time"])

    tick_df = VectorizedXauUsdStrategy.add_bar_time_n_broker_day(tick_df)

    result = run_vectorized_strategy(tick_df=tick_df, candle_df=candle_15min_df, zones_df=zones_df, debug=debug)
    manifest = result

    save_results_to_file(
        manifest,
        output,
    )

    print_strategy_summary(manifest)

    if backtest:
        from .backtest import print_backtest_report, run_vectorbt_backtest, save_backtest_report, save_backtest_trades

        print("\n--- Running vectorbt backtest ---")
        print_backtest_report(manifest)
        portfolio = run_vectorbt_backtest(manifest)
        backtest_output = Path(output).with_suffix(".backtest_stats.parquet")
        save_backtest_report(portfolio, str(backtest_output))
        trades_output = Path(output).with_suffix(".backtest_trades.parquet")
        save_backtest_trades(portfolio, str(trades_output))

    print(f"\nExecution completed successfully. Results saved to {output}")


if __name__ == "__main__":
    log_dir = app_config.path_of_logs
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"runtime.{datetime.now():%y%m%dT%H%M%S}.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    log_d("Test log!")
    app()
