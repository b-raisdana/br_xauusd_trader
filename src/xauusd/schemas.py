"""Pandera schemas for external tabular inputs."""

from __future__ import annotations

import pandera.pandas as pa
from pandera import typing as pt


class ZoneCsvSchema(pa.DataFrameModel):
    class Config:
        coerce = False
        strict = False

    date: pt.Series[str]
    lower: pt.Series[str]
    upper: pt.Series[str]
    priority: pt.Series[str]
    enabled: pt.Series[str]
