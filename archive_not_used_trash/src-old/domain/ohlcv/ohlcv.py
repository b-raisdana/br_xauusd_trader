import pandas as pd
from pandera import typing as pt

from br_pre_commit import pandera_validate
from domain.schemas.common.ohlcv import OHLCV


@pandera_validate
def build_base_timeframe_ohlcv(
    raw_ohlcv: list[object], time_range_str: str, base_timeframe: str | None = None
) -> pt.DataFrame[OHLCV]:
    df = pd.DataFrame(raw_ohlcv, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], unit="ms", utc=True)
    df = df.set_index("date")
    df = df.drop(columns=["timestamp"])
    # OHLCV.validate(df)
    # if not after_under_process_time(time_range_str):
    #     if df.empty:
    #         log_exception('Unexpected empty dataset!', ValueError)
    return df
