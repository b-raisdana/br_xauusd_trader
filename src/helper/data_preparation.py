from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

import pandas as pd
import pytz
from br_py_log_n_profile import log_d, log_e, log_exception, log_w
from pandas import DatetimeIndex, Timestamp
from pandera import typing as pt

from config import app_config
from domain.schemas.common.base_dataframe import (
    MultiTimeframeTimeseries_Type,
    Timeseries,
    Timeseries_Type,
    has_single_timeframe,
)
from helper.date_utils import get_floor, time_range, timeframe_to_grouper_freq
from helper.pandera import pandera_validate


@pandera_validate(allow_pandas_dataframe=True)
def single_timeframe_datetime_indices(
    multi_timeframe_data: pd.DataFrame,
    timeframe: str,
) -> DatetimeIndex:
    if "timeframe" not in multi_timeframe_data.index.names:
        raise RuntimeError(
            f'multi_timeframe_data expected to have "timeframe" in indexes:[{multi_timeframe_data.index.names}]'
        )
    if timeframe not in app_config.timeframes:
        raise RuntimeError(f"timeframe:{timeframe} is not in supported timeframes:{app_config.timeframes}")
    if multi_timeframe_data.index.names.index("timeframe") != 0:
        raise AssertionError("multi_timeframe_data.index.names.index('timeframe') != 0")
    return pd.DatetimeIndex(
        multi_timeframe_data.loc[pd.IndexSlice[timeframe, :]].index,
        tz="UTC",
    )


@pandera_validate(allow_pandas_dataframe=True)
def single_timeframe(
    multi_timeframe_data: pd.DataFrame,
    timeframe: str,
    keep_timeframe: bool = False,
    sort: bool = True,
    index_only: bool = False,
) -> pd.DataFrame:
    if index_only:
        log_exception("Use single_timeframe_datetime_indices", ValueError)
    if "timeframe" not in multi_timeframe_data.index.names:
        raise RuntimeError(
            f'multi_timeframe_data expected to have "timeframe" in indexes:[{multi_timeframe_data.index.names}]'
        )
    if timeframe not in app_config.timeframes:
        raise RuntimeError(f"timeframe:{timeframe} is not in supported timeframes:{app_config.timeframes}")
    if multi_timeframe_data.index.names.index("timeframe") != 0:
        raise AssertionError("multi_timeframe_data.index.names.index('timeframe') != 0")

    if not keep_timeframe:
        single_timeframe_data = multi_timeframe_data.loc[pd.IndexSlice[timeframe, :]]
        assert isinstance(single_timeframe_data, pd.DataFrame)

        validate_no_timeframe(cast(pt.DataFrame[Timeseries], single_timeframe_data))
    else:
        single_timeframe_data = multi_timeframe_data.loc[pd.IndexSlice[[timeframe], :]]
    if sort:
        return single_timeframe_data.sort_index(level="date")
    else:
        return single_timeframe_data


def to_timeframe(
    time: DatetimeIndex | datetime | Timestamp,
    timeframe: str,
    ignore_cached_times: bool = False,
    do_not_warn: bool = False,
) -> datetime | DatetimeIndex:
    """
    Round down the given datetime or DatetimeIndex to the nearest time based on the specified timeframe.

    This function adjusts a datetime or each datetime in a DatetimeIndex to align with the start of a
    specified timeframe, such as '1min', '5min', '1H', etc. It is particularly useful for aligning
    timestamps to regular intervals.

    Parameters:
        time (Union[DatetimeIndex, datetime, Timestamp]): The datetime or DatetimeIndex to be rounded.
        timeframe (str): The desired timeframe to round to (e.g., '1min', '5min', '1H', etc.).
        ignore_cached_times (bool): If True, bypasses checking the time against a global cache of valid times.

    Returns:
        Union[datetime, DatetimeIndex]: The rounded datetime or DatetimeIndex, where each datetime value
        is adjusted to the start of the nearest interval as specified by the timeframe.

    Raises:
        Exception: If time types are incompatible, or if rounding requirements are not met.
        :param do_not_warn: Set it true if you are sure about using this method.
    """
    if not do_not_warn:
        log_w("Try not to use to_timeframe and use pd.merge_asof(...) instead")

    def round_single_datetime(dt: datetime | Timestamp) -> datetime | Timestamp:
        if timeframe == "1W":
            floored: pd.Timestamp = get_floor(pd.Timestamp(dt), "1W")
            return floored
        rounded_timestamp = (dt.timestamp() // seconds_in_timeframe) * seconds_in_timeframe
        if isinstance(dt, datetime):
            rounded_dt = datetime.fromtimestamp(rounded_timestamp, tz=dt.tzinfo)
        else:  # isinstance(dt, Timestamp)
            rounded_dt = pd.Timestamp(rounded_timestamp * 10**9, tz=dt.tzinfo)
        return rounded_dt

    # Calculate the timedelta for the specified timeframe
    timeframe_timedelta = pd.to_timedelta(timeframe)
    seconds_in_timeframe = timeframe_timedelta.total_seconds()

    if pd.to_timedelta(timeframe) >= timedelta(minutes=30) and getattr(time, "tzinfo", None) is None:
        raise RuntimeError("To round times to timeframes > 30 minutes, timezone is significant")
    rounded_time: datetime | DatetimeIndex
    if isinstance(time, (datetime, Timestamp)):
        rounded_time = round_single_datetime(time)
    elif isinstance(time, DatetimeIndex):
        rounded_time = pd.DatetimeIndex(time.to_series().apply(round_single_datetime))
    else:
        raise RuntimeError(f"Invalid type of time: {type(time)}")

    if not ignore_cached_times:
        check_time_in_cache(rounded_time, timeframe)

    return rounded_time


def check_time_in_cache(time: DatetimeIndex | pd.Series | datetime | Timestamp, timeframe: str) -> None:
    cache_key = f"valid_times_{timeframe}"
    if cache_key not in app_config.GLOBAL_CACHE:
        raise RuntimeError(f"{cache_key} not initialized in config.GLOBAL_CACHE")
    cache_set: set[pd.Timestamp] = set(app_config.GLOBAL_CACHE[cache_key])
    if isinstance(time, (DatetimeIndex, pd.Series)):
        if not time.isin(cache_set).all():
            raise RuntimeError(f"Some times: {time} not found in config.GLOBAL_CACHE[valid_times_{timeframe}]!")
    elif time not in cache_set:
        raise RuntimeError(f"time {time} not found in config.GLOBAL_CACHE[valid_times_{timeframe}]!")


# pandera-validate: ignore[typevar]
def validate_no_timeframe(data: pt.DataFrame[Timeseries_Type]) -> pt.DataFrame[Timeseries_Type]:
    if "timeframe" in data.index.names:
        raise RuntimeError(f"timeframe found in Data(indexes:{data.index.names}, columns:{data.columns.names}")
    return data


# pandera-validate: ignore[typevar]
def validate_single_timeframe(
    data: pt.DataFrame[MultiTimeframeTimeseries_Type],
) -> pt.DataFrame[MultiTimeframeTimeseries_Type]:
    if not has_single_timeframe(data):
        msg = "Single Timeframe requires to have all rows with a single timeframe!"
        log_e(msg)
        raise RuntimeError(msg)
    return data


def _raise_or_log(message: str, return_bool: bool) -> bool:
    if return_bool:
        log_d(message)
        return False
    raise ValueError(message)


def _check_missing_times(
    expected_times: set[pd.Timestamp],
    actual_times: set[pd.Timestamp],
    time_range_str: str,
    timeframe: str,
    return_bool: bool,
) -> bool | None:
    missing_times = expected_times - actual_times
    if missing_times:
        message = f"Some times in {time_range_str}@{timeframe} are missing in the DataFrame's index:" + ", ".join(
            [str(time) for time in missing_times]
        )
        log_e(message)
        if return_bool:
            return False
        raise ValueError(message)
    return None


def _check_excess_times(
    expected_times: set[pd.Timestamp],
    actual_times: set[pd.Timestamp],
    time_range_str: str,
    timeframe: str,
    return_bool: bool,
) -> bool:
    excess_times = actual_times - expected_times
    if excess_times:
        message = f"Some times in {time_range_str}@{timeframe} are excessive in the DataFrame's index:" + ", ".join(
            [str(time) for time in excess_times]
        )
        return _raise_or_log(message, return_bool)
    return True


@pandera_validate(allow_pandas_dataframe=True)
def times_tester(
    df: pd.DataFrame,
    time_range_str: str,
    timeframe: str,
    return_bool: bool = False,
    limit_to_under_process_range: bool = True,
    processing_time_range: str | None = None,
    exact_match: bool = False,
) -> bool | None:
    expected_times = set(
        times_in_time_range(time_range_str, timeframe, limit_to_under_process_range, processing_time_range)
    )
    actual_times = set(df.index) if len(df.index) > 0 else set()

    if len(expected_times) == 0:
        if not actual_times:
            return True
        return _raise_or_log(
            f"No times in {time_range_str}@{timeframe} fall within the processing range, "
            "but the DataFrame's index is not empty",
            return_bool,
        )

    _check_missing_times(expected_times, actual_times, time_range_str, timeframe, return_bool)

    if exact_match:
        return _check_excess_times(expected_times, actual_times, time_range_str, timeframe, return_bool)
    return True


@pandera_validate
def multi_timeframe_times_tester(
    multi_timeframe_df: pt.DataFrame[MultiTimeframeTimeseries_Type],
    time_range_str: str,
    return_bool: bool = False,
    ignore_processing_time_range: bool = True,
    processing_time_range: str | None = None,
) -> bool | None:
    result: bool | None = True
    for timeframe in app_config.timeframes:
        _timeframe_df = single_timeframe(multi_timeframe_df, timeframe)
        _result = times_tester(
            _timeframe_df,
            time_range_str,
            timeframe,
            return_bool,
            ignore_processing_time_range,
            processing_time_range,
        )
        if _result is None:
            result = None
        elif result is not None:
            result = result & _result
    return result


def map_symbol(symbol: str, map_dictionary: dict[str, str]) -> str:
    upper_symbol = symbol.upper()
    if upper_symbol in map_dictionary.values():
        return symbol.upper()
    return map_dictionary[upper_symbol]


@pandera_validate(allow_pandas_dataframe=True)
def trim_to_time_range(time_range_str: str, df: pd.DataFrame, ignore_duplicate_index: bool = False) -> pd.DataFrame:
    start, end = time_range(time_range_str)
    date_indexes = df.index.get_level_values(level="date")
    df = df[(date_indexes >= start) & (date_indexes <= end)]
    duplicate_indices = df.index[df.index.duplicated()].unique()
    if not ignore_duplicate_index and len(duplicate_indices) != 0:
        raise ValueError("len(duplicate_indices) != 0")
    return df


def after_under_process_time(time_range_str: str) -> bool:
    start, _ = time_range(time_range_str)
    _, end = time_range(app_config.processing_time_range)
    return start > end


def times_in_time_range(
    time_range_str: str,
    timeframe: str,
    ignore_out_of_process_range: bool = True,
    processing_time_range: str | None = None,
) -> DatetimeIndex:
    start, end = time_range(time_range_str)
    if ignore_out_of_process_range:
        if processing_time_range is None:
            processing_time_range = app_config.processing_time_range
        under_process_scope_start, under_process_scope_end = time_range(processing_time_range)
        end = min(end, under_process_scope_end)
        start = max(start, under_process_scope_start)
    in_timeframe_start_date = to_timeframe(start, timeframe, ignore_cached_times=True, do_not_warn=True)
    if (
        isinstance(start, datetime)
        and isinstance(in_timeframe_start_date, datetime)
        and in_timeframe_start_date < start
    ):
        in_timeframe_start_date += pd.to_timedelta(timeframe)
    if (
        isinstance(start, DatetimeIndex)
        and isinstance(in_timeframe_start_date, DatetimeIndex)
        and (in_timeframe_start_date < start).any()
    ):
        in_timeframe_start_date = in_timeframe_start_date + pd.to_timedelta(timeframe)
    if start < end:
        return pd.date_range(start=in_timeframe_start_date, end=end, freq=timeframe_to_grouper_freq(timeframe))  # type: ignore[arg-type]
    return pd.DatetimeIndex([], tz=pytz.utc)


def _fill_na_columns(df: pd.DataFrame, na_columns: pd.Series, source: pd.DataFrame) -> None:  # type: ignore[explicit-any]
    for column, d_type in na_columns.items():
        if column not in source.columns:
            df[column] = pd.Series(dtype=d_type)
        else:
            df[column] = source[column]


@pandera_validate(allow_pandas_dataframe=True)
def concat(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
    left_empty = left.empty or left.isna().all().all()
    right_empty = right.empty or right.isna().all().all()

    if left_empty:
        return right.copy() if not right_empty else pd.DataFrame()
    if right_empty:
        return left

    left = pd.concat([left.dropna(axis=1, how="all"), right.dropna(axis=1, how="all")])
    _fill_na_columns(left, left.dtypes[left.isna().all()], right)
    _fill_na_columns(left, right.dtypes[right.isna().all()], left)
    return left
