from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pandas as pd
from br_py_log_n_profile import log_e
from pyiceberg.catalog import Catalog
from pyiceberg.catalog.sql import SqlCatalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.expressions import And, BooleanExpression, GreaterThanOrEqual, In, LessThanOrEqual
from pyiceberg.table import Table
from pyiceberg.table.upsert_util import create_match_filter
from pyiceberg.types import (
    BooleanType,
    DoubleType,
    FloatType,
    IcebergType,
    IntegerType,
    LongType,
    StringType,
    TimestamptzType,
)

from helper.date_utils import time_range
from helper.importer import pa, pya
from helper.pandera import pandera_validate
from infrastructure.datastore_engine.duckdb_cache_registry import DatastoreRegistry
from infrastructure.datastore_engine.paths import dataset_db_root

__cached_catalogs: dict[str, Catalog] = {}
__catalog_lock = threading.Lock()

# Iceberg spec property names for row-level write strategy. Declared here so tables are configured
# for merge-on-read from creation. NOTE: pyiceberg 0.11.1's own write path does not implement
# merge-on-read yet — Transaction.upsert() always rewrites matched data files via overwrite(), and
# Transaction.delete() explicitly warns "Merge on read is not yet supported, falling back to
# copy-on-write" when this property is set (verified against the installed version's source). Setting
# it anyway is still correct: it's the properly-declared intent for any engine that does implement it
# (e.g. Spark), and costs nothing today beyond pyiceberg's own writes staying copy-on-write in practice.
_MERGE_ON_READ_PROPERTIES = {
    "write.delete.mode": "merge-on-read",
    "write.update.mode": "merge-on-read",
    "write.merge.mode": "merge-on-read",
}

_JOIN_COLS = ["date", "timeframe"]


def _catalog_cache_key(datastore: DatastoreRegistry) -> str:
    return f"{datastore.value}:{_catalog_root(datastore)}"


def _catalog_root(datastore: DatastoreRegistry) -> Path:
    root: Path = dataset_db_root() / datastore.value
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_iceberg_catalog(datastore: DatastoreRegistry) -> Catalog:
    key = _catalog_cache_key(datastore)
    with __catalog_lock:
        if key not in __cached_catalogs:
            root = _catalog_root(datastore)
            (root / "warehouse").mkdir(parents=True, exist_ok=True)
            __cached_catalogs[key] = SqlCatalog(
                datastore.value,
                uri=f"sqlite:///{root / 'catalog.db'}",
                warehouse=f"file://{root / 'warehouse'}",
            )
        return __cached_catalogs[key]


def _with_microsecond_timestamp(frame: pd.DataFrame) -> pd.DataFrame:
    # Iceberg has no nanosecond timestamp type; pandas/pyarrow default to datetime64[ns], which
    # pyiceberg's schema conversion rejects outright (UnsupportedPyArrowTypeException) rather than
    # silently truncating -- downcast explicitly before it ever reaches pyarrow/pyiceberg.
    frame = frame.copy()
    frame["date"] = frame["date"].astype("datetime64[us, UTC]")
    return frame


def _ensure_table(catalog: Catalog, identifier: str, sample_frame: pd.DataFrame) -> Table:
    catalog.create_namespace_if_not_exists(identifier.rsplit(".", 1)[0])
    pa_schema = pya.Table.from_pandas(sample_frame.iloc[0:0], preserve_index=False).schema
    return catalog.create_table_if_not_exists(identifier, schema=pa_schema, properties=_MERGE_ON_READ_PROPERTIES)


_PA_TO_ICEBERG = {
    pya.float64(): DoubleType(),
    pya.float32(): FloatType(),
    pya.int64(): LongType(),
    pya.int32(): IntegerType(),
    pya.bool_(): BooleanType(),
}


def _arrow_to_iceberg_type(pa_type: pya.DataType) -> IcebergType:
    """Map a PyArrow type to the corresponding Iceberg type for schema evolution."""
    if pya.types.is_string(pa_type) or pya.types.is_large_string(pa_type):
        return StringType()
    if pya.types.is_timestamp(pa_type):
        return TimestamptzType()
    iceberg_type = _PA_TO_ICEBERG.get(pa_type)
    if iceberg_type is None:
        raise ValueError(f"Unsupported PyArrow type for schema evolution: {pa_type}")
    return iceberg_type


def _evolve_schema(iceberg_table: Table, frame: pd.DataFrame) -> bool:
    """Add columns from *frame* that are missing from the Iceberg table schema.

    Returns True when the schema was changed (callers may want to refresh)."""
    if not isinstance(iceberg_table, Table):
        return False
    existing = set(iceberg_table.schema().column_names)
    new_cols = [c for c in frame.columns if c not in existing]
    if not new_cols:
        return False
    arrow_schema = pya.Table.from_pandas(frame.iloc[:0], preserve_index=False).schema
    update = iceberg_table.update_schema()
    for col in sorted(new_cols):
        pa_type = arrow_schema.field(col).type
        iceberg_type = _arrow_to_iceberg_type(pa_type)
        update = update.add_column(col, iceberg_type)
    update.commit()
    return True


def _write_gap(
    datastore_registry: DatastoreRegistry,
    #    table: str,
    frame: pd.DataFrame,
) -> None:
    """Persist a gap-fill frame to Iceberg with schema evolution and a column-safe
    merge/upsert.

    * New columns (e.g. ``atr_255``) are added to the table schema via Iceberg
      schema evolution -- existing columns are never removed.
    * Rows are replaced with copy-on-write semantics: matched rows are deleted
      (retired by Iceberg) and the new rows appended, so previously-written
      column values survive as long as the *frame* carries them.
    * ``overwrite`` is used instead of ``upsert`` because pyiceberg's upsert
      internally casts the scanned target (physical files without the evolved
      column) to the source schema, which raises when new columns were just
      added.  ``overwrite`` sidesteps this by deleting-by-predicate then
      appending."""
    frame = _with_microsecond_timestamp(frame)
    catalog = get_iceberg_catalog(datastore_registry)
    # identifier = _table_identifier(table)
    identifier = datastore_registry.get_auto_table_name()
    iceberg_table = _ensure_table(catalog, identifier, frame)
    if _evolve_schema(iceberg_table, frame):
        iceberg_table = iceberg_table.refresh()
    # Fill in any table columns the frame lacks (values are unknown for this gap window)
    # so the pa.Table cast and the overwrite both carry the full column set.
    table_cols = iceberg_table.schema().column_names
    for col in table_cols:
        if col not in frame.columns:
            frame[col] = np.nan
    pa_frame = pya.Table.from_pandas(frame, schema=iceberg_table.schema().as_arrow(), preserve_index=False)
    overwrite_filter = create_match_filter(pa_frame, _JOIN_COLS)
    iceberg_table.overwrite(pa_frame, overwrite_filter=overwrite_filter)


def _append_gap(
    datastore_registry: DatastoreRegistry,
    frame: pd.DataFrame,
) -> None:
    frame = _with_microsecond_timestamp(frame)
    catalog = get_iceberg_catalog(datastore_registry)
    identifier = datastore_registry.get_auto_table_name()
    iceberg_table = _ensure_table(catalog, identifier, frame)
    pa_frame = pya.Table.from_pandas(frame, schema=iceberg_table.schema().as_arrow(), preserve_index=False)
    iceberg_table.append(pa_frame)


@pandera_validate(allow_pandas_dataframe=True)
def iceberg_fetch_from_datastore(
    datastore_registry: DatastoreRegistry,
    time_range_str: str,
    timeframes: tuple[str, ...],
    schema_model: type[pa.DataFrameModel],
) -> pd.DataFrame:
    schema = schema_model.to_schema()
    index_names = [index.name for index in schema.index.indexes]
    selected_fields = (*index_names, *schema.columns)

    @pandera_validate(allow_pandas_dataframe=True)
    def empty_result() -> pd.DataFrame:
        storage_columns = {name: pd.Series(dtype=str(column.dtype)) for name, column in schema.columns.items()}
        for index in schema.index.indexes:
            storage_columns[index.name] = pd.Series(dtype=str(index.dtype))
        return schema_model.validate(pd.DataFrame(storage_columns).set_index(index_names), lazy=True)

    catalog = get_iceberg_catalog(datastore_registry)
    identifier = datastore_registry.get_auto_table_name()
    try:
        iceberg_table = catalog.load_table(identifier)
    except NoSuchTableError:
        return empty_result()

    start, end = time_range(time_range_str)
    # mypy resolves these pydantic-model constructors against their synthesized field-order __init__
    # (term, type, value) instead of the actual, custom __init__(term, literal, **kwargs) pyiceberg
    # defines and runs at import time -- confirmed live (unit tests exercise this exact call) and
    # against pyiceberg's own source (pyiceberg/expressions/__init__.py LiteralPredicate.__init__).
    row_filter: BooleanExpression = And(
        GreaterThanOrEqual("date", start.isoformat()),  # type: ignore[call-arg,arg-type]
        LessThanOrEqual("date", end.isoformat()),  # type: ignore[call-arg,arg-type]
    )
    if timeframes:
        row_filter = And(row_filter, In("timeframe", timeframes))  # type: ignore[call-arg,arg-type]

    try:
        rows = iceberg_table.scan(row_filter=row_filter, selected_fields=selected_fields).to_pandas()
    except Exception as err:
        log_e(f"iceberg_base: fetch from {identifier!r} failed: {err}")
        return empty_result()
    if rows.empty:
        return empty_result()
    rows["date"] = pd.to_datetime(rows["date"], utc=True)
    rows["date"] = rows["date"].astype("datetime64[ns, UTC]")
    return schema_model.validate(rows.set_index(index_names), lazy=True)
