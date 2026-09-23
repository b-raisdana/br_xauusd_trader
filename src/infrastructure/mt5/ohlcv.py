import MetaTrader5 as mt5
import pandas as pd
from br_py_log_n_profile import log_exception

from domain.schemas.common.ohlcv import MultiTimeframeTicksSpreadOHLC
from helper.date_utils import normalize_timeframes, time_range
from helper.importer import pt
from helper.pandera import pandera_validate
from infrastructure.mt5.conversion import timeframe_to_mt5
from infrastructure.mt5.symbol import verify_symbol


@pandera_validate
async def get_ohlcv(symbol: str, time_range_str: str, timeframe: str) -> pt.DataFrame[MultiTimeframeTicksSpreadOHLC]:
    timeframe = normalize_timeframes((timeframe,))[0]
    start, end = time_range(time_range_str)
    symbol = await verify_symbol(symbol)
    mt5_timeframe = timeframe_to_mt5(timeframe)
    try:
        raw = mt5.copy_rates_range(symbol, mt5_timeframe, start, end)  # todo: conver to await asyncio.to_thread
    except Exception:
        code, message = mt5.last_error()
        log_exception(f"MT5 copy_rates_range failed ({code}: {message})", RuntimeError)
    if raw is None:
        code, message = mt5.last_error()
        log_exception(f"MT5 copy_rates_range failed ({code}: {message})", RuntimeError)
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(
        df.pop("time"),
        unit="s",
        utc=True,
    ).astype(pd.DatetimeTZDtype(unit="ns", tz="UTC"))
    df["volume"] = df.pop("real_volume")
    df["timeframe"] = timeframe
    df = df.set_index(["timeframe", "date"])
    return df
