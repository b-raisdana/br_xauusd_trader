"""Per-symbol file work behind the `migrate-ohlcv` job (orchestrated by
`application.datastore_engine.migrate_ohlcv`): discover the legacy source layout, read + normalize +
dedup one symbol's OHLCV cache files, and append the result to the Iceberg `unified_no_nan` store.

Source layout (`iter_ohlcv_roots`): `<source_root>/<exchange>/<market>/<symbol>/ohlcv.*.parquet` and
`ohlcv.*.zip` (CSV-zip), `source_root` defaulting to `app_config.path_of_data`. This is the flat
per-symbol cache that predates `@duckdb_cache`; it is a different tree from `dataset_db/`, which the
`parquet_housekeeping` jobs handle.

Per symbol (`migrate_ohlcv_symbol`): concat every source file, coerce the time column to a UTC
`date` (accepts a `date` column or index), drop duplicate dates, add a
`timeframe` column set to `BASE_TIMEFRAME`, keep the canonical OHLCV columns, and `_append_gap()` the
frame to that `market/symbol/exchange` namespace's Iceberg table. `_append_gap` is a plain append
with no upsert/existing-row check, so calling this twice for one symbol duplicates its rows.

Full guide: app/application/datastore_engine/README.md.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
from br_py_log_n_profile import log_i, log_w

from br_pre_commit import pandera_validate
from config import BASE_TIMEFRAME, app_config
from infrastructure.datastore_engine.duckdb_cache_registry import DatastoreRegistry
from infrastructure.datastore_engine.iceberg_base import _append_gap

_READ_WORKERS = 8


def _default_source_root() -> Path:
    return Path(app_config.path_of_data).resolve()


def iter_ohlcv_roots(source_root: Path | None = None) -> list[tuple[str, str, str, Path]]:
    """Discover every (market, symbol, exchange, exchange_dir) under the source OHLCV root."""
    source_root = source_root if source_root is not None else _default_source_root()
    if not source_root.is_dir():
        return []
    result: list[tuple[str, str, str, Path]] = []
    for exchange_dir in source_root.iterdir():
        if not exchange_dir.is_dir():
            continue
        exchange = exchange_dir.name
        for market_dir in exchange_dir.iterdir():
            if not market_dir.is_dir():
                continue
            market = market_dir.name
            for symbol_dir in market_dir.iterdir():
                if not symbol_dir.is_dir():
                    continue
                symbol = symbol_dir.name
                result.append((market, symbol, exchange, symbol_dir))
    return result


def _normalize_ohlcv_frame(df: pd.DataFrame, source: Path) -> pd.DataFrame | None:
    """Coerce a raw OHLCV frame to a UTC-`date` frame, or None when it has no usable date column."""
    if df is None or df.empty:
        return None
    if df.index.name == "date" or "date" not in df.columns:
        df = df.reset_index()
    if "date" not in df.columns:
        log_w(f"migrate_ohlcv: no 'date' in {source}, skipping")
        return None
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


def _read_ohlcv_parquet(pf: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(pf)
    except Exception as e:
        log_w(f"migrate_ohlcv: skipping unreadable {pf}: {e}")
        return None
    return _normalize_ohlcv_frame(df, pf)


def _read_legacy_zip(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path, compression="zip")
    except BadZipFile as e:
        log_w(f"migrate_ohlcv: bad zip {path}: {e}")
        return None
    except Exception as e:
        log_w(f"migrate_ohlcv: unreadable zip {path}: {e}")
        return None
    return _normalize_ohlcv_frame(df, path)


@pandera_validate(allow_pandas_dataframe=True)
def read_ohlcv_source_files(symbol_dir: Path) -> pd.DataFrame | None:
    """Read and concatenate every OHLCV cache file under symbol_dir into one deduplicated DataFrame."""
    parquet_files = sorted(symbol_dir.glob("ohlcv.*.parquet"))
    zip_files = sorted(symbol_dir.glob("ohlcv.*.zip"))
    if not parquet_files and not zip_files:
        return None
    log_i(f"migrate_ohlcv: reading {len(parquet_files)} parquet + {len(zip_files)} zip from {symbol_dir}")
    frames: list[pd.DataFrame] = []
    for pf in parquet_files:
        frame = _read_ohlcv_parquet(pf)
        if frame is not None:
            frames.append(frame)
    with ThreadPoolExecutor(max_workers=_READ_WORKERS) as executor:
        futures = {executor.submit(_read_legacy_zip, zf): zf for zf in zip_files}
        for future in as_completed(futures):
            frame = future.result()
            if frame is not None:
                frames.append(frame)
    if not frames:
        return None
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["date"], keep="first")
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def migrate_ohlcv_symbol(market: str, symbol: str, exchange: str, source_root: Path | None = None) -> int:
    """Migrate one symbol's OHLCV cache into the unified_no_nan Iceberg store. Returns rows written."""
    app_config.under_process_market = market
    app_config.under_process_symbol = symbol
    app_config.under_process_exchange = exchange

    source_root = source_root if source_root is not None else _default_source_root()
    symbol_dir = source_root / exchange / market / symbol
    if not symbol_dir.is_dir():
        return 0

    combined = read_ohlcv_source_files(symbol_dir)
    if combined is None:
        return 0

    storage = combined.copy()
    storage["timeframe"] = BASE_TIMEFRAME
    for col in ("open", "high", "low", "close", "volume"):
        if col not in storage.columns:
            storage[col] = float("nan")
    storage = storage[["date", "timeframe", "open", "high", "low", "close", "volume"]].copy()

    _append_gap(DatastoreRegistry.UnifiedNoNAN, storage)
    return len(storage)
