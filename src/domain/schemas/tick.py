from __future__ import annotations

import numpy as np
import pandas as pd
from pandera.typing import Series

from config import app_config
from domain.schemas.common.base_dataframe import TickMultiBrokerSymbolTimeseries
from helper.importer import pt


class Tick(TickMultiBrokerSymbolTimeseries):
    class Config:
        multiindex_ordered = False

    bid: Series[float]
    ask: Series[float]
    last: Series[float]
    volume: Series[np.uint64]
    flags: Series[np.uint32]
    volume_real: Series[float]

    @classmethod
    def from_ndarray(
        cls,
        data: np.ndarray,
        *,
        symbol: str | None = None,
        broker: str | None = None,
        # date_index_freq: str = "1s",
    ) -> pt.DataFrame["Tick"]:
        broker = broker if broker else app_config.default_broker
        symbol = symbol if symbol else app_config.default_symbol
        df = pd.DataFrame(data)

        df.insert(0, "symbol", symbol)
        df.insert(1, "broker", broker)
        df["precise_time"] = pd.to_datetime(
            df.pop("time_msc"),
            unit="ms",
            utc=True,
        ).astype(pd.DatetimeTZDtype(unit="ns", tz="UTC"))
        df["date"] = df["precise_time"].dt.floor(freq="1s")
        df = df.set_index(["symbol", "broker", "date", "precise_time"])

        return cls.validate(df)


#     @classmethod
#     def get_typed_dict(cls) -> type:
#         return TypedDict(
#             cls.__name__.removesuffix("Data"),
#             get_type_hints(cls),
#         )
#
#     @classmethod
#     def get_named_tuple(cls) -> type[NamedTuple]:
#         all_hints = get_type_hints(cls)
#         own_fields = cls.__dict__.get("__annotations__", {})
#         field_hints = [(k, all_hints[k]) for k in own_fields if k in all_hints]
#         return type(NamedTuple(cls.__name__.removesuffix("Data"), field_hints))
#
#
# MetaTickRow = MetaTickDf.get_named_tuple()
#
#
# def test_f(i: MetaTickRow):
#     i.a
#     return i.time + i.bid
