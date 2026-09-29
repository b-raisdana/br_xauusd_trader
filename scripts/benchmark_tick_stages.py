"""Profile the per-stream vectorized stages at production-like tick counts.

Set `DLF_ENVIRONMENT=production` to time the same path with the pandera
validation decorators bypassed, which isolates validation cost from
computation cost.

Usage: python scripts/benchmark_tick_stages.py --rows 200000
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Annotated, Any, Callable

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application.xauusd_trading_strategy_1_vector.config.core_vectors import core_vectors  # noqa: E402
from application.xauusd_trading_strategy_1_vector.config.strategy_config import strategy_config  # noqa: E402
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy  # noqa: E402
from config import app_config  # noqa: E402

app = typer.Typer(add_completion=False)


def synthetic_ticks(rows: int) -> pd.DataFrame:
    times = pd.date_range("2026-09-18", periods=rows, freq="1s", tz="UTC").as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [
            pd.Index(["test"] * rows, dtype="str"),
            pd.Index(["XAUUSD"] * rows, dtype="str"),
            times,
            times.normalize(),
        ],
        names=["broker", "symbol", "precise_time", "date"],
    )
    prices = 2000.0 + np.cumsum(np.random.default_rng(0).normal(0, 0.05, rows))
    ticks = pd.DataFrame(
        {
            "bid": prices,
            "ask": prices + 0.2,
            "last": prices,
            "volume": np.zeros(rows, dtype=np.uint64),
            "flags": np.zeros(rows, dtype=np.uint32),
            "volume_real": np.zeros(rows),
        },
        index=index,
    )
    return VectorizedXauUsdStrategy.add_bar_time_n_broker_day(ticks)


def candles_from_ticks(ticks: pd.DataFrame) -> pd.DataFrame:
    keys = ["broker", "symbol", "bar_time"]
    candles = (
        ticks.reset_index()
        .groupby(keys, sort=False)
        .agg(
            open=("bid", "first"),
            high=("bid", "max"),
            low=("bid", "min"),
            close=("bid", "last"),
            volume=("bid", "size"),
        )
        .reset_index()
    )
    candles["date"] = candles["bar_time"].dt.normalize()
    candles["timeframe"] = "15min"
    return candles.set_index(["date", "timeframe", "broker", "symbol", "bar_time"])


class NoZones:
    def get_zones_for_day(self, day: object) -> list:
        return []


def time_step(stage: str, call: Callable[[], Any]) -> tuple[Any, float]:
    start = time.perf_counter()
    result = call()
    elapsed = time.perf_counter() - start
    print(f"  {stage:<26} {elapsed:8.3f}s")
    return result, elapsed


@app.command()
def main(
    rows: Annotated[int, typer.Option(help="Synthetic tick rows per stream.")] = 200_000,
    repeat: Annotated[int, typer.Option(help="Timed repetitions; the fastest run is reported.")] = 1,
) -> None:
    ticks = synthetic_ticks(rows)
    candles = candles_from_ticks(ticks)
    strategy = VectorizedXauUsdStrategy(NoZones())  # type: ignore[arg-type]
    print(f"rows={rows} environment={app_config.environment}")

    with core_vectors.use(), strategy_config.use():
        best: dict[str, float] = {}
        for _ in range(repeat):

            def run() -> dict[str, float]:
                timings: dict[str, float] = {}
                state, timings["initialize_state"] = time_step(
                    "initialize_state", lambda: strategy._initialize_per_tick_temp_state(ticks)
                )
                state, timings["day_boundaries"] = time_step(
                    "day_boundaries", lambda: strategy._process_day_boundaries(state)
                )
                boundaries, timings["bar_boundaries"] = time_step(
                    "bar_boundaries", lambda: strategy._process_bar_boundaries(ticks, state, candles)
                )
                state = boundaries[0]
                _, timings["tick_operations"] = time_step(
                    "tick_operations", lambda: strategy._process_tick_operations(ticks, state)
                )
                return timings

            candidate = run()
            if not best or sum(candidate.values()) < sum(best.values()):
                best = candidate
        for stage, elapsed in best.items():
            print(f"  {stage:<26} {elapsed:8.3f}s")
        print(f"  {'total':<26} {sum(best.values()):8.3f}s")


if __name__ == "__main__":
    app()
