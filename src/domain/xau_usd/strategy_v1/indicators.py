import pandas as pd
import pandas_ta as ta

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.strategy_v1 import ZeroLagMacdResult
from helper.importer import pt

from ._time_index import utc_times
from .config import StrategyV1Config


def _validated_close(close: pd.Series) -> pd.Series:
    utc_times(close.index)
    if close.empty or close.isna().any() or not pd.api.types.is_numeric_dtype(close.dtype):
        raise ValueError("close must contain only numeric, non-null values")
    if close.isin([float("inf"), float("-inf")]).any():
        raise ValueError("close must contain only finite values")
    prices = close.astype("float64")
    if isinstance(prices.index, pd.MultiIndex):
        prices.index = prices.index.set_levels(
            prices.index.levels[prices.index.names.index("date")].astype("datetime64[ns, UTC]"),
            level="date",
        )
    else:
        prices.index = utc_times(prices.index).astype("datetime64[ns, UTC]")
    return prices


def rsi(close: pd.Series, config: StrategyV1Config) -> pd.Series:
    prices = _validated_close(close)
    values = ta.rsi(prices, length=config.rsi_period, mamode="rma", talib=False)
    return values.mask(prices.expanding().count().le(config.rsi_period))


def _dema(series: pd.Series, period: int) -> pd.Series:
    values = ta.dema(series, length=period, talib=False)
    return series.mul(float("nan")) if values is None else values


@pandera_validate
def zero_lag_macd(close: pd.Series, config: StrategyV1Config) -> pt.DataFrame[ZeroLagMacdResult]:
    prices = _validated_close(close)
    macd_line = _dema(prices, config.zero_lag_macd_fast_period) - _dema(prices, config.zero_lag_macd_slow_period)
    signal_line = _dema(macd_line, config.zero_lag_macd_signal_period)
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
            "histogram_previous": histogram.shift(1),
        },
        index=prices.index,
    )
