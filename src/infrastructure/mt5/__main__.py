import MetaTrader5 as mt5
from br_py_log_n_profile import log_d


async def get_client(login_id: int, password: str, server: str):
    mt5_client = mt5.initialize(login=login_id, password=password, server=server)
    if mt5_client:
        log_d("MetaTrader5 client initialized successfully")
    else:
        log_d(f"Failed to initialize MetaTrader5 client: {mt5.last_error()}")
    return mt5_client
