import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.strategy_v1 import M15TrendCandles, M15TrendResult
from helper.importer import pt

from ._time_index import utc_times
from .config import StrategyV1Config


@pandera_validate
def m15_trend(candles: pt.DataFrame[M15TrendCandles], config: StrategyV1Config) -> pt.DataFrame[M15TrendResult]:
    times = utc_times(candles.index)

    day = pd.Series(times.floor("D"), index=candles.index)
    grouped_high = candles["high"].groupby(day, sort=False)
    grouped_low = candles["low"].groupby(day, sort=False)
    oldest_high = grouped_high.shift(config.trend_reference_candles - 1)
    oldest_low = grouped_low.shift(config.trend_reference_candles - 1)
    newer_high = grouped_high.shift(1)
    newer_low = grouped_low.shift(1)

    up_c2 = newer_high.gt(oldest_high) & newer_low.gt(oldest_low)
    down_c2 = newer_high.lt(oldest_high) & newer_low.lt(oldest_low)
    up_c3 = candles["high"].gt(oldest_high) & candles["low"].gt(oldest_low)
    down_c3 = candles["high"].lt(oldest_high) & candles["low"].lt(oldest_low)
    up = up_c2 | up_c3
    down = down_c2 | down_c3
    closed_count = candles["high"].groupby(day, sort=False).cumcount().add(1)
    eligible = closed_count.ge(config.minimum_closed_m15_candles)
    trend = pd.Series(0, index=candles.index, dtype="int8")
    trend = trend.mask(up & ~down, 1).mask(down & ~up, -1)

    return pd.DataFrame(
        {"trend": trend.where(eligible, 0), "eligible": eligible},
        index=candles.index,
    )
