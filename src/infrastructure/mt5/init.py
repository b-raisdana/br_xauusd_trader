import MetaTrader5 as mt5
from async_lru import alru_cache
from br_py_log_n_profile import log_exception

from config import app_config


@alru_cache
async def initialize():
    if not mt5.initialize(  # todo: conver to await asyncio.to_thread
        app_config.get("mt5_exe_path", ""),
        login=int(app_config.get("default_broker_login", 0)),
        password=app_config.get("default_broker_password", ""),
        server=app_config.get("default_broker_server", ""),
        timeout=int(app_config.get("mt5_init_timeout", 0)),
        portable=bool(app_config.get("mt5_is_portable", False)),
    ):
        code, message = mt5.last_error()
        log_exception(f"MT5 initialization failed ({code}: {message})", RuntimeError)
