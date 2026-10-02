from datetime import datetime, timedelta, timezone, tzinfo
from functools import lru_cache

import pandas as pd
import pytz
from br_py_log_n_profile import log_exception

from br_pre_commit import pandera_validate


def time_range_to_string(
    end: datetime | pd.Timestamp | None = None,
    days: float = 60,
    start: datetime | pd.Timestamp | None = None,
) -> str:
    if end is None:
        end = today_morning() if start is None else start + timedelta(days=days) - timedelta(minutes=1)
    if start is None:
        start = end - timedelta(days=days) + timedelta(minutes=1)
    time_range_str = f"{start.strftime('%y-%m-%d.%H-%M')}T{end.strftime('%y-%m-%d.%H-%M')}"
    if end < start:
        raise RuntimeError(
            f'End:"{end}" of requested_boundary:"{time_range_str}" should be later than it\'s Start:"{start}"'
        )
    return time_range_str


@lru_cache(maxsize=1024)
def time_range(time_range_str: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    try:
        start_string, end_date_string = time_range_str.split("T")
    except ValueError as e:
        log_exception(f"T not found in {time_range_str}. err:{str(e)}", ValueError)

    start = datetime.strptime(start_string, "%y-%m-%d.%H-%M")
    start = start.replace(tzinfo=pytz.utc)
    end = datetime.strptime(end_date_string, "%y-%m-%d.%H-%M")
    end = end.replace(tzinfo=pytz.utc)
    if end < start:
        log_exception(
            f'End:"{end}" of requested_boundary:"{time_range_str}" should be later than it\'s Start:"{start}"',
            RuntimeError,
        )
    start = pd.Timestamp(start)
    assert isinstance(start, pd.Timestamp)
    end = pd.Timestamp(end)
    assert isinstance(end, pd.Timestamp)
    return start, end


@pandera_validate(allow_pandas_dataframe=True)
def time_range_of_data(data: pd.DataFrame) -> str:
    """
    Generate a formatted date range string based on the first and last timestamps in the DataFrame's index.

    This function calculates and returns a formatted string representing the date range of the provided DataFrame.
    The string format is 'yy-mm-dd.HH-MMTyy-mm-dd.HH-MM', where the first timestamp corresponds to the start of the
    date range and the last timestamp corresponds to the end of the date range.

    Parameters:
        data (pd.DataFrame): The DataFrame for which to generate the date range string.

    Returns:
        str: The formatted date range string.

    Example:
        # Assuming you have a DataFrame 'data' with an index containing timestamps
        time_range = range_of_data(data)
        log_d(date_range)  # Output: 'yy-mm-dd.HH-MMTyy-mm-dd.HH-MM'
    """
    return (
        f"{data.index.get_level_values('date').min().strftime('%y-%m-%d.%H-%M')}T"
        f"{data.index.get_level_values('date').max().strftime('%y-%m-%d.%H-%M')}"
    )


EPSILON_TIME = timedelta(seconds=1)


def today_morning(tz: tzinfo = pytz.utc) -> datetime:
    return morning(datetime.now(tz)) - timedelta(minutes=1)


def morning(date_time: datetime, tz: tzinfo = pytz.utc) -> datetime:
    date_time = date_time.replace(tzinfo=tz) if date_time.tzinfo is None else date_time.astimezone(tz)
    return date_time.replace(hour=0, minute=0, second=0)


def yesterday(reference: datetime | None = None) -> str:
    if reference is None:
        reference = datetime.now(timezone.utc)
    start = pd.to_datetime(reference.replace(hour=0, minute=0, second=0, microsecond=0).date() - timedelta(days=1))
    end = start + timedelta(days=1) - EPSILON_TIME
    return time_range_to_string(start=start, end=end)
