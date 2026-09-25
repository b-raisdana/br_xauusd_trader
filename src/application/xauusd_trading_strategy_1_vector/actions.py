"""Action generation utilities for the vectorized XAUUSD strategy.

Extracted from the_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

import pandas as pd

from application.xauusd_trading_strategy_1_vector.domain.replay import ReplayConfig
from application.xauusd_trading_strategy_1_vector.domain.schema import PerTickBaseState
from application.xauusd_trading_strategy_1_vector.replay import ExecutionReplay
from domain.xau_usd.models import XauZone
from helper.importer import pt
from helper.pandera import pandera_validate


@pandera_validate(allow_pandas_dataframe=True)
def generate_actions(
    per_tick_state: pt.DataFrame[PerTickBaseState],
    zones: list[XauZone],
    config: ReplayConfig,
    replay: ExecutionReplay | None = None,
) -> pt.DataFrame[PerTickBaseState]:
    """Replay one chronological broker/symbol partition using explicit economics."""
    result = per_tick_state.copy()
    times = result.index.get_level_values("datetime")
    if not times.is_monotonic_increasing:
        raise ValueError("Execution ticks must be chronological")
    streams = result.index.droplevel(["datetime", "date"]).unique()
    if len(streams) > 1:
        raise ValueError("Execution partition must contain one broker/symbol")
    if replay is None:
        replay = ExecutionReplay(config, repr(streams[0]) if len(streams) else "empty")
    records = []
    rows = zip(
        times,
        result["broker_day"],
        result["bar_time"],
        result["bar_open"],
        result["bid"],
        result["ask"],
        result["pullback_windows_opened"],
        result["breakout_signals"],
        result.get("reversal_signals", [()] * len(result)),
        strict=True,
    )
    for time, day, bar, bar_open, bid, ask, openings, breakouts, reversals in rows:
        records.append(replay.step(time, day, bar, bar_open, bid, ask, zones, openings, breakouts, reversals))
    payload = pd.DataFrame.from_records(records, index=result.index)
    for column in payload:
        result[column] = payload[column].to_numpy()
    return result
