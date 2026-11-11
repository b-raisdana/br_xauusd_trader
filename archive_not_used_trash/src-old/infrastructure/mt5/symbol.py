import MetaTrader5 as mt5
from async_lru import alru_cache
from br_py_log_n_profile import log_exception

from config import app_config
from infrastructure.mt5.init import initialize


@alru_cache
async def verify_symbol(
    symbol: str | None = None,
) -> str:
    await initialize()
    symbol = symbol if symbol else app_config.default_symbol
    all_symbols = mt5.symbols_get(
        group=app_config.get("mt5_symbols_group", "")
    )  # todo: conver to await asyncio.to_thread
    if symbol in [s.name for s in all_symbols]:
        return symbol
    log_exception(f"Symbol {symbol} not found", RuntimeError)
