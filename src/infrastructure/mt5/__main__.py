import asyncio
import datetime

import MetaTrader5 as mt5
from br_py_log_n_profile import log_d


async def test_initialize(login_id: int = 0, password: str = "", server: str = ""):
    mt5_client = mt5.initialize(login=login_id, password=password, server=server)
    if mt5_client:
        log_d("MetaTrader5 client initialized successfully")
    else:
        log_d(f"Failed to initialize MetaTrader5 client: {mt5.last_error()}")
    return mt5_client


async def sample_copy_ticks_range():
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        quit()
    ticks = mt5.copy_ticks_range(
        "XAUUSD",
        datetime.datetime(2026, 9, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
        datetime.datetime(2026, 9, 15, 12, 0, 0, microsecond=10000, tzinfo=datetime.timezone.utc),
        mt5.COPY_TICKS_ALL,
    )

    print("ticks:", ticks)
    print("error:", mt5.last_error())
    pass


async def sample_copy_rates_from():
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        quit()
    rates = mt5.copy_rates_from(
        "XAUUSD",
        mt5.TIMEFRAME_M1,
        datetime.datetime(2026, 9, 15, 12, 0, 0, tzinfo=datetime.timezone.utc),
        10,
    )

    print("rates:", rates)
    print("error:", mt5.last_error())
    pass


async def symbols_get():
    if not mt5.initialize():
        raise RuntimeError(mt5.last_error())

    symbols = mt5.symbols_get(group="*GC*")

    for s in symbols:
        print(s.name, s.description, s.exchange, s.path)

    mt5.shutdown()


asyncio.run(symbols_get())
