import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.strategy_v1 import IndicatorConfirmationResult
from helper.importer import pt

from .config import StrategyV1Config
from .indicators import rsi, zero_lag_macd


@pandera_validate
def indicator_confirmations(
    close: pd.Series,
    config: StrategyV1Config,
) -> pt.DataFrame[IndicatorConfirmationResult]:
    rsi_values = rsi(close, config)
    macd_values = zero_lag_macd(close, config)
    rsi_recent = rsi_values.rolling(
        window=config.rsi_confirmation_candles,
        min_periods=config.rsi_confirmation_candles,
    )
    buy_macd = (
        macd_values["signal"].le(config.zero_lag_macd_buy_signal_max)
        & macd_values["histogram"].gt(macd_values["histogram_previous"])
        & macd_values["histogram"].gt(config.zero_lag_macd_buy_histogram_min)
    )
    sell_macd = (
        macd_values["signal"].ge(config.zero_lag_macd_sell_signal_min)
        & macd_values["histogram"].lt(macd_values["histogram_previous"])
        & macd_values["histogram"].lt(config.zero_lag_macd_sell_histogram_max)
    )
    result = pd.DataFrame(
        {
            "rsi_buy_ready": rsi_recent.min().le(config.rsi_buy_max),
            "rsi_sell_ready": rsi_recent.max().ge(config.rsi_sell_min),
            "macd_buy_confirmed": buy_macd,
            "macd_sell_confirmed": sell_macd,
        },
        index=rsi_values.index,
    )
    return result
