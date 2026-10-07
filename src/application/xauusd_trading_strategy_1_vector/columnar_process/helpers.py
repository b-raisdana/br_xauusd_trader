"""Index-aligned primitives shared by columnar state and event calculations."""

import pandas as pd

from application.xauusd_trading_strategy_1_vector.domain.columnar import SignalTable, SignalTickState, WindowTable
from br_pre_commit import pandera_validate
from domain.xau_usd.enums import XauSignalFamily


@pandera_validate(allow_pandas_dataframe=True)
def empty_table(
    model: type[SignalTable] | type[WindowTable] | type[SignalTickState], index: pd.MultiIndex
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            name: pd.Series(index=index[:0], dtype="str" if "string" in str(field.dtype) else str(field.dtype))
            for name, field in model.to_schema().columns.items()
            if not field.regex
        },
        index=index[:0],
    )


def _take(series: pd.Series, keys: pd.Series) -> pd.Series:
    return series.reindex(keys).set_axis(keys.index)


def _signal_rows(
    data: pd.DataFrame,
    mask: pd.Series,
    zone_id: str,
    direction: int,
    family: int,
    candidate_id: str | pd.Series,
    bar_id: str | pd.Series,
    entry: float | pd.Series,
    parent: str | pd.Series = "",
) -> pd.DataFrame:
    selected = data.loc[mask, ["stream_tick", "signal_time"]]
    for name, value in (
        ("candidate_id", candidate_id),
        ("bar_id", bar_id),
        ("entry_price", entry),
        ("parent_breakout_id", parent),
    ):
        selected[name] = value.loc[mask] if isinstance(value, pd.Series) else value
    selected["zone_id"] = zone_id
    selected["direction"] = direction
    selected["family"] = family
    selected["order_type"] = int(family == int(XauSignalFamily.PULLBACK))
    selected["_position"] = selected.index
    return selected
