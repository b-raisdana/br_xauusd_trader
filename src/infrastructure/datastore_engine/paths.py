from pathlib import Path

from config import app_config


def symbol_data_path(
    path_of_data: str | None = None,
    exchange: str | None = None,
    market: str | None = None,
    trading_pair: str | None = None,
) -> str:
    if path_of_data is None:
        path_of_data = str(app_config.path_of_data)
    if exchange is None:
        exchange = app_config.under_process_exchange
    if market is None:
        market = app_config.under_process_market
    if trading_pair is None:
        trading_pair = app_config.under_process_symbol
    return str(Path(path_of_data) / exchange / market / trading_pair)


def dataset_db_root(path_of_data: str | None = None) -> Path:
    if path_of_data is None:
        path_of_data = str(app_config.path_of_data)
    return Path(path_of_data) / "dataset_db"
