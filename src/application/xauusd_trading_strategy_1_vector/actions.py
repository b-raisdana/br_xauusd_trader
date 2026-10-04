"""Action generation utilities for the vectorized XAUUSD strategy.

Extracted from the_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

import pandas as pd

from application.xauusd_trading_strategy_1_vector.domain.replay import ReplayConfig
from application.xauusd_trading_strategy_1_vector.domain.schema import PerTickState, VectorizedTick
from application.xauusd_trading_strategy_1_vector.replay import ExecutionReplay
from br_pre_commit import pandera_validate
from domain.xau_usd.models import XauZone
from helper.importer import pt


@pandera_validate(allow_pandas_dataframe=True)
def generate_actions(
    ticks: pt.DataFrame[VectorizedTick],
    per_tick_state: pt.DataFrame[PerTickState],
    zones: list[XauZone],
    config: ReplayConfig,
    replay: ExecutionReplay | None = None,
) -> pt.DataFrame[PerTickState]:
    """Compatibility replay of supplied candidates, without native candle/signal parity.

    Use VectorizedXauUsdStrategy.process_tick_data for the canonical market flow.
    """
    if not ticks.index.equals(per_tick_state.index):
        raise ValueError("Execution ticks and state must have identical ordered indexes")
    if replay is not None and replay.config != config:
        raise ValueError("Execution replay and supplied configuration must match")
    times = per_tick_state.index.get_level_values("precise_time")
    result = per_tick_state

    if not times.is_monotonic_increasing:
        raise ValueError("Execution ticks must be chronological")
    streams = result.index.droplevel(["precise_time", "date"]).unique()
    if len(streams) > 1:
        raise ValueError("Execution partition must contain one broker/symbol")
    if replay is None:
        replay = ExecutionReplay(config, repr(streams[0]) if len(streams) else "empty")
    records = []
    rows = zip(
        times,
        ticks["broker_day"],
        ticks["bar_time"],
        result["bar_open"],
        ticks["bid"],
        ticks["ask"],
        result["pullback_windows_opened"],
        result["breakout_signals"],
        result.get("reversal_signals", [()] * len(result)),
        strict=True,
    )
    for time, day, bar, bar_open, bid, ask, openings, breakouts, reversals in rows:
        records.append(
            replay.step(time, day.strftime("%Y-%m-%d"), bar, bar_open, bid, ask, zones, openings, breakouts, reversals)
        )
    payload = pd.DataFrame.from_records(records, index=result.index)
    for column in payload:
        result[column] = payload[column]
    result["mt5_state"] = "{}"
    return result
