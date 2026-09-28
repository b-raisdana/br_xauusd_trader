"""Lossless parquet encoding for the strategy's nested audit values."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import IntEnum
from pathlib import Path

import pandas as pd

from application.xauusd_trading_strategy_1_vector.domain.schema import PullbackFeedback
from domain.xau_usd.enums import XauDirection, XauSignalFamily
from domain.xau_usd.models import XauPullbackWindowState, XauSignalCandidate, XauZone

_CLASSES = {cls.__name__: cls for cls in (PullbackFeedback, XauPullbackWindowState, XauSignalCandidate, XauZone)}
_ENUMS = {cls.__name__: cls for cls in (XauDirection, XauSignalFamily)}
_PREFIX = "xau-json:"


def _encode(value):
    if isinstance(value, IntEnum):
        return {"$enum": type(value).__name__, "value": int(value)}
    if isinstance(value, datetime):
        return {"$datetime": value.isoformat()}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "$class": type(value).__name__,
            "fields": {f.name: _encode(getattr(value, f.name)) for f in fields(value)},
        }
    if isinstance(value, tuple):
        return {"$tuple": [_encode(item) for item in value]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return value


def _decode(value):
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "$datetime" in value:
        return pd.Timestamp(value["$datetime"])
    if "$enum" in value:
        enum = _ENUMS.get(value["$enum"])
        return enum(value["value"]) if enum else value["value"]
    if "$tuple" in value:
        return tuple(_decode(item) for item in value["$tuple"])
    if "$class" in value:
        return _CLASSES[value["$class"]](**{key: _decode(item) for key, item in value["fields"].items()})
    return {key: _decode(item) for key, item in value.items()}


def write_parquet(df: pd.DataFrame, name: str, folder_to_save: Path) -> Path:
    folder_to_save.mkdir(parents=True, exist_ok=True)
    path = folder_to_save / (name if name.endswith(".parquet") else f"{name}.parquet")
    encoded = df.copy(deep=True)
    for column in encoded.select_dtypes(include="object", exclude="str"):
        encoded[column] = encoded[column].map(lambda value: _PREFIX + json.dumps(_encode(value)))
    encoded.to_parquet(path, engine="pyarrow", index=True)
    return path


def read_parquet(path: Path) -> pd.DataFrame:
    decoded = pd.read_parquet(path, engine="pyarrow")
    for column in decoded.select_dtypes(include=["object", "str", "string"]):
        values = decoded[column]
        if values.map(lambda value: isinstance(value, str) and value.startswith(_PREFIX)).any():
            decoded[column] = values.map(
                lambda value: (
                    _decode(json.loads(value[len(_PREFIX) :]))
                    if isinstance(value, str) and value.startswith(_PREFIX)
                    else value
                )
            ).astype(object)
    return decoded
