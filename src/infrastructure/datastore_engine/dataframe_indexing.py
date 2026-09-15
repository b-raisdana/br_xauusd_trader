from typing import cast

import pandas as pd

from helper.pandera import pandera_validate


@pandera_validate(allow_pandas_dataframe=True)
def index_by_date(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    date_index = cast("pd.DatetimeIndex", df.index)
    if len(df) > 0 and date_index.tz is None:
        df.index = date_index.tz_localize("UTC")
    return df


@pandera_validate(allow_pandas_dataframe=True)
def add_timeframe_index(df: pd.DataFrame, data_frame_type: str) -> pd.DataFrame:
    if "multi_timeframe" in data_frame_type:
        df.set_index("timeframe", append=True, inplace=True)
        df = df.swaplevel()
    return df
