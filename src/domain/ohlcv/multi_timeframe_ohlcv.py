import datetime

import pandas as pd
from br_py_log_n_profile import log_e
from pandera import typing as pt

from config import BASE_TIMEFRAME, app_config
from domain.schemas.common.ohlcv import OHLCV, MultiTimeframeOHLCV
from helper.data_preparation import concat, trim_to_time_range
from helper.date_utils import normalize_timeframes, timeframe_to_grouper_freq, timeframe_to_pandas_freq
from helper.pandera import pandera_validate


@pandera_validate
def aggregate_ohlcv(
    ohlcv: pt.DataFrame[OHLCV], frequency: str, *, offset: pd.Timedelta | None = None
) -> pt.DataFrame[OHLCV]:
    """Aggregate OHLCV candles into open-time-labelled frequency bins."""
    if offset is None:
        grouper = pd.Grouper(freq=frequency, closed="left", label="left")
    else:
        grouper = pd.Grouper(
            freq=frequency,
            origin="start_day",
            offset=offset,
            closed="left",
            label="left",
        )
    aggregated_ohlcv = ohlcv.groupby(grouper).agg(
        {
            "open": "first",
            "close": "last",
            "low": "min",
            "high": "max",
            "volume": "sum",
        }
    )
    aggregated_ohlcv["close"] = aggregated_ohlcv["close"].ffill()
    for price_column in ("open", "high", "low"):
        aggregated_ohlcv[price_column] = aggregated_ohlcv[price_column].fillna(aggregated_ohlcv["close"])
    aggregated_ohlcv.index = aggregated_ohlcv.index.astype("datetime64[ns, UTC]")
    return OHLCV.validate(aggregated_ohlcv)


@pandera_validate
def aggregate_multi_timeframe_ohlcv(
    ohlcv: pt.DataFrame[OHLCV], time_range_str: str, freqs: list[str] | tuple[str, ...] | None = None
) -> pt.DataFrame[MultiTimeframeOHLCV]:
    """
    Resamples a base-timeframe OHLCV DataFrame into every configured higher timeframe
    (`app_config.timeframes[1:]`) via calendar-aligned `pd.Grouper` aggregation. Pure transform, no
    I/O: the caller is responsible for actually fetching/generating the base-timeframe `ohlcv`.
    """

    multi_timeframe_ohlcv = ohlcv.copy()
    multi_timeframe_ohlcv.insert(0, "timeframe", app_config.timeframes[0])
    multi_timeframe_ohlcv = multi_timeframe_ohlcv.set_index("timeframe", append=True)
    multi_timeframe_ohlcv = multi_timeframe_ohlcv.swaplevel()
    non_base_timeframes = normalize_timeframes(timeframes=freqs, freqs_to_drop=(BASE_TIMEFRAME,), all_if_empty=True)
    for timeframe in non_base_timeframes:
        frequency = timeframe_to_grouper_freq(timeframe)
        # Exchanges label a candle by its OPEN time (a weekly candle is the Monday it starts on,
        # covering Mon 00:00 .. Sun 23:59). pandas defaults anchored offsets like "W-MON" to
        # closed/label "right", which would label by the *closing* Monday and push the Monday
        # 00:00 base row into the previous week -- force open-time bins for every timeframe.
        _timeframe_ohlcv = aggregate_ohlcv(ohlcv, frequency)
        # pd.Grouper materializes a row for every calendar bin in span, including ones with zero
        # underlying base-timeframe rows (real low-liquidity gaps) — forward-fill those as flat
        # zero-volume candles instead of leaving non-nullable OHLC columns NaN.
        if len(_timeframe_ohlcv.index) > 0:
            _timeframe_ohlcv.insert(0, "timeframe", timeframe)
            _timeframe_ohlcv = _timeframe_ohlcv.set_index("timeframe", append=True)
            _timeframe_ohlcv = _timeframe_ohlcv.swaplevel()
            multi_timeframe_ohlcv = concat(multi_timeframe_ohlcv, _timeframe_ohlcv)  # type: ignore[assignment]
    multi_timeframe_ohlcv = trim_to_time_range(time_range_str, multi_timeframe_ohlcv)  # type: ignore[assignment]
    multi_timeframe_ohlcv = multi_timeframe_ohlcv.sort_index(level="date")
    # assert multi_timeframe_times_tester(multi_timeframe_ohlcv, time_range_str)
    return MultiTimeframeOHLCV.validate(multi_timeframe_ohlcv)


@pandera_validate
def aggregate_to_quadrant_freq(
    trading_ohlcv: pt.DataFrame[OHLCV],
    offset_minutes: int,
    trading_timeframe_minutes: int = 5,
    quadrant_timeframe: str = "15min",
) -> pt.DataFrame[OHLCV]:
    """Aggregate 5-minute OHLCV candles into 15-minute candles anchored at ``offset_minutes``.

    An offset of 1 produces open-time indexes ``00:01``, ``00:16``, ... and aggregates each
    corresponding 15-minute interval. See the implementation appendix, "Future windows."
    """
    trading_timeframe_n_minutes = pd.to_timedelta(timeframe_to_pandas_freq(quadrant_timeframe)) // datetime.timedelta(
        minutes=1
    )
    if offset_minutes not in range(1, trading_timeframe_n_minutes):
        msg = f"offset_minutes must be in [1, {trading_timeframe_minutes - 1}], got {offset_minutes}"
        log_e(msg)
        raise ValueError(msg)
    _offset = pd.Timedelta(minutes=offset_minutes)
    assert isinstance(_offset, pd.Timedelta)
    result = aggregate_ohlcv(
        trading_ohlcv,
        frequency=quadrant_timeframe,
        offset=_offset,
    )
    return OHLCV.validate(result)
