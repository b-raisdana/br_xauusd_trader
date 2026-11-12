from datetime import UTC, datetime

import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.strategy_v1 import ClosedCandles
from helper.importer import pt

from ._time_index import utc_times
from .config import StrategyV1Config


@pandera_validate
def closed_candles(
    candles: pt.DataFrame[ClosedCandles],
    as_of: datetime,
    timeframe_minutes: int,
    config: StrategyV1Config,
) -> pt.DataFrame[ClosedCandles]:
    if as_of.tzinfo is None or as_of.utcoffset() is None or as_of.utcoffset() != UTC.utcoffset(as_of):
        raise ValueError("as_of must be UTC-aware")
    if timeframe_minutes not in {config.m5_timeframe_minutes, config.m15_timeframe_minutes}:
        raise ValueError("timeframe_minutes must match the configured M5 or M15 timeframe")

    times = utc_times(candles.index)
    close_times = times + pd.Timedelta(minutes=timeframe_minutes)
    return candles.loc[close_times <= pd.Timestamp(as_of)]
