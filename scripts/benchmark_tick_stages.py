"""Time the active controller path with correctness and honest statistics.

Measures the public entry point `VectorizedXauUsdStrategy.process_native_stream`
rather than its private stage helpers, so the number describes a path that
actually ships and does not silently change meaning when internals move.

Reports the median of N repetitions plus warm and cold timings, and verifies
that every repetition produced identical output. An optimization claim without
that equivalence evidence is not a claim.

`DLF_ENVIRONMENT=production` times the same path with the pandera validation
decorators bypassed, which isolates validation cost from computation cost. It
also disables `Config.check_assertions`, so it is a diagnostic mode only and
must never be used to validate correctness.

Usage:
    python scripts/dev.py benchmark --rows 20000 --repeat 5
    python scripts/benchmark_tick_stages.py --rows 20000 --repeat 5
"""

from __future__ import annotations

import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
# The pinned br_pre_commit submodule provides the pandera_validate decorator that
# the domain schemas import at module load time.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Shared synthetic fixtures, so benchmark inputs match the regression suite.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from vectorized_fixtures import candles_from_ticks, with_native_bootstrap  # noqa: E402

from application.xauusd_trading_strategy_1_vector.config.core_vectors import core_vectors  # noqa: E402
from application.xauusd_trading_strategy_1_vector.config.strategy_config import strategy_config  # noqa: E402
from application.xauusd_trading_strategy_1_vector.market import MarketState  # noqa: E402
from application.xauusd_trading_strategy_1_vector.the_strategy import VectorizedXauUsdStrategy  # noqa: E402
from config import app_config  # noqa: E402

app = typer.Typer(add_completion=False)


def synthetic_ticks(rows: int) -> pd.DataFrame:
    """Deterministic ticks: fixed seed, so repeated runs are comparable."""
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


def candles_covering(ticks: pd.DataFrame) -> pd.DataFrame:
    """M15 candles covering every observed bar, plus closed bootstrap bars.

    Reuses the shared test fixture module so the benchmark and the regression
    suite build identical candles. A benchmark on different inputs than the
    tests cannot support an equivalence claim.
    """
    return with_native_bootstrap(candles_from_ticks(ticks))


class NoZones:
    """Isolates compute from zone acquisition; zones are I/O, not the hot path."""

    def get_zones_for_day(self, day: object) -> list:
        return []


def fingerprint(*frames: pd.DataFrame) -> str:
    """Stable digest of the produced frames, to prove repetitions agree."""
    import hashlib

    digest = hashlib.sha256()
    for frame in frames:
        digest.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
        digest.update("|".join(map(str, frame.columns)).encode())
    return digest.hexdigest()[:16]


def run_once(strategy: VectorizedXauUsdStrategy, ticks: pd.DataFrame, candles: pd.DataFrame) -> tuple[Any, float]:
    start = time.perf_counter()
    market = MarketState(strategy.inputs, None)
    result = strategy.process_native_stream(ticks, candles, market)
    return result, time.perf_counter() - start


@app.command()
def main(
    rows: Annotated[int, typer.Option(help="Synthetic tick rows per stream.")] = 20_000,
    repeat: Annotated[int, typer.Option(help="Timed repetitions; median and spread are reported.")] = 5,
    memory: Annotated[bool, typer.Option(help="Also report peak traced memory for one run.")] = False,
) -> None:
    ticks = synthetic_ticks(rows)
    candles = candles_covering(ticks)
    strategy = VectorizedXauUsdStrategy(NoZones())  # type: ignore[arg-type]

    print(f"rows={rows} repeat={repeat} environment={app_config.environment}")
    print(f"python={sys.version.split()[0]} pandas={pd.__version__} numpy={np.__version__}")

    with core_vectors.use(), strategy_config.use():
        cold_result, cold = run_once(strategy, ticks, candles)
        timings = [cold]
        digests = {fingerprint(*cold_result)}

        for _ in range(max(0, repeat - 1)):
            result, elapsed = run_once(strategy, ticks, candles)
            timings.append(elapsed)
            digests.add(fingerprint(*result))

    peak = ""
    if memory:
        tracemalloc.start()
        with core_vectors.use(), strategy_config.use():
            run_once(strategy, ticks, candles)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak = f"  peak_traced={peak_bytes / 1024 / 1024:8.1f}MiB"

    spread = f"{min(timings):.3f}-{max(timings):.3f}s" if len(timings) > 1 else "n/a"
    print(f"  cold (first call)      {cold:8.3f}s")
    print(f"  warm runs              {len(timings) - 1}")
    print(f"  median                 {statistics.median(timings):8.3f}s")
    print(f"  min/max                {spread}")
    print(f"  rows_per_second        {rows / statistics.median(timings):,.0f}")
    if peak:
        print(peak)

    if len(digests) == 1:
        print(f"  correctness            OK (all runs identical, digest {next(iter(digests))})")
        return
    print(f"  correctness            FAILED: {len(digests)} distinct outputs across runs: {sorted(digests)}")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
