import asyncio

import MetaTrader5 as mt5
from br_py_log_n_profile import log_exception, profile_it

from br_pre_commit import pandera_validate
from domain.schemas import tick
from helper.date_utils import time_range, yesterday
from helper.importer import pt
from infrastructure.mt5.symbol import verify_symbol


@profile_it
# @duckdb_cache(DatastoreRegistry.Tick, nan_means='not-cached', freqs=('1s',))
@pandera_validate
async def get_ticks(
    time_range_str: str,
    symbol: str | None = None,
    freqs: tuple[str] = ("1s",),
) -> pt.DataFrame[tick.Tick]:
    assert freqs == ("1s",)

    start, end = time_range(time_range_str)
    symbol = await verify_symbol(symbol)
    raw = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
    if raw is None:
        code, message = mt5.last_error()
        log_exception(f"MT5 copy_ticks_range failed ({code}: {message})", RuntimeError)
    ticks = tick.Tick.from_ndarray(
        raw,
        symbol=symbol,
    )
    return ticks


if __name__ == "__main__":
    asyncio.run(get_ticks(yesterday()))
