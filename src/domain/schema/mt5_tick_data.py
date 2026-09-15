from __future__ import annotations

from typing import NamedTuple, TypedDict, get_type_hints

import numpy as np
import pandas as pd
import pandera.pandas as pa


class MetaTickDf(pa.DataFrameModel):
    time: int
    bid: float
    ask: float
    last: float
    volume: int
    time_msc: int
    flags: int
    volume_real: float
    datetime: pd.Timestamp

    @classmethod
    def from_ndarray(cls, data: np.ndarray) -> pd.DataFrame:
        df = pd.DataFrame(data)

        df["datetime"] = pd.to_datetime(
            df["time_msc"],
            unit="ms",
            utc=True,
        )

        return cls.validate(df)

    @classmethod
    def get_typed_dict(cls) -> type:
        return TypedDict(
            cls.__name__.removesuffix("Data"),
            get_type_hints(cls),
        )

    @classmethod
    def get_named_tuple(cls) -> type[NamedTuple]:
        all_hints = get_type_hints(cls)
        own_fields = cls.__dict__.get("__annotations__", {})
        field_hints = [(k, all_hints[k]) for k in own_fields if k in all_hints]
        return NamedTuple(cls.__name__.removesuffix("Data"), field_hints)


MetaTickRow = MetaTickDf.get_named_tuple()


def test_f(i: MetaTickRow):
    return i.time + i.bid
