import asyncio
from functools import lru_cache

import MetaTrader5 as mt5
from br_py_log_n_profile import log_exception

from config import app_config
from domain.schema import tick
from helper.date_utils import time_range, yesterday
from helper.importer import pt


@lru_cache
def mt5_initialize():
    if not mt5.initialize(
        app_config.get("mt5_exe_path", ""),
        login=int(app_config.get("default_broker_login", 0)),
        password=app_config.get("default_broker_password", ""),
        server=app_config.get("default_broker_server", ""),
        timeout=int(app_config.get("mt5_init_timeout", 0)),
        portable=bool(app_config.get("mt5_is_portable", False)),
    ):
        code, message = mt5.last_error()
        log_exception(f"MT5 initialization failed ({code}: {message})", RuntimeError)


@lru_cache
def verify_symbol(
    symbol: str | None = None,
) -> str:
    mt5_initialize()
    symbol = symbol if symbol else app_config.default_symbol
    all_symbols = mt5.symbols_get(group=app_config.get("mt5_symbols_group", ""))
    if symbol in [s.name for s in all_symbols]:
        return symbol
    log_exception(f"Symbol {symbol} not found", RuntimeError)


# @duckdb_cache(DatastoreRegistry.Tick, nan_means='not-cached', freqs=('1s',))
async def get_ticks(
    time_range_str: str,
    symbol: str | None = None,
    freqs: tuple[str] = ("1second",),
) -> pt.DataFrame[tick.Tick]:
    assert len(freqs) == 1
    freq = freqs[0]
    start, end = time_range(time_range_str)
    symbol = verify_symbol(symbol)
    raw = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
    ticks = tick.Tick.from_ndarray(raw, freq)
    return ticks


if __name__ == "__main__":
    asyncio.run(get_ticks(yesterday()))
