"""Command-line entry point and compatibility exports for the vectorized strategy."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
import typer
from br_py_log_n_profile import log_e, log_exception

from application.xauusd_trading_strategy_1_vector.zone_loader import load_zones_from_file
from config import app_config
from domain.xau_usd.zone import build_merged_zones
from helper.date_utils import time_range_to_string
from infrastructure.mt5.ohlcv import get_ohlcv
from infrastructure.mt5.tick import get_ticks

from .reporting import (
    print_strategy_summary,
    save_results_to_file,
)
from .result_processing import (
    generate_order_management_columns,
    generate_position_tracking_columns,
    merge_results_with_candles,
)
from .strategy_runner import (
    get_strategy_internal_state,
    run_vectorized_strategy,
)

__all__ = [
    "run_vectorized_strategy",
    "get_strategy_internal_state",
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
) -> None:
    asyncio.run(main(symbol=symbol, zones=zones, output=output, debug=debug))


async def main(
    symbol: str = app_config.default_symbol,
    zones: Path = Path("ranges.zip"),
    output: str = "strategy_results.parquet",
    debug: bool = False,
) -> None:
    output_format = Path(output).suffix.lstrip(".").lower()
    if output_format not in {"csv", "parquet"}:
        log_e("Output must have a .csv or .parquet extension")
        raise ValueError("Output must have a .csv or .parquet extension")
    print("Loading data ...")

    zones_df = await load_zones_from_file(zones)
    datetime_of_first_zone = zones_df.index.get_level_values("date")[0]
    next_day_after_first_zone = zones_df.index.get_level_values("date")[0] + pd.Timedelta(days=1)
    zones_df = zones_df[
        (
            (datetime_of_first_zone <= zones_df.index.get_level_values("date"))
            & (zones_df.index.get_level_values("date") < next_day_after_first_zone)
        )
    ]

    if zones_df.empty:
        log_exception("Zone input must contain at least one day", ValueError)
    start = zones_df.index.get_level_values("date").min().normalize()
    end = zones_df.index.get_level_values("date").max().normalize() + pd.Timedelta(days=1)
    time_range_str = time_range_to_string(start=start, end=end)
    tick_data = await get_ticks(time_range_str=time_range_str, symbol=symbol)
    tick_times = tick_data.index.get_level_values("datetime")

    out_of_boundary_ticks = tick_data.loc[~((tick_times >= start) & (tick_times < end))]
    assert out_of_boundary_ticks.empty

    if tick_data.empty:
        log_e("No ticks returned for the requested zone days")
        raise ValueError("No ticks returned for the requested zone days")

    candle_15min_df = await get_ohlcv(symbol, time_range_str=time_range_str, timeframe="15min")

    candle_15min_df = candle_15min_df.reset_index().rename(columns={"date": "bar_time"})

    result = run_vectorized_strategy(tick_df=tick_data, candle_df=candle_15min_df, zones_df=zones_df, debug=debug)

    save_results_to_file(
        result,
        output,
    )

    print_strategy_summary(result)

    print(f"\nExecution completed successfully. Results saved to {output}")


if __name__ == "__main__":
    app()
