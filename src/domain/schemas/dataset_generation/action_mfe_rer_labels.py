"""Pandera models for the staged action/MFE/RER label calculation."""

from typing import cast

import pandas as pd
import pandera.pandas as pa
from br_py_log_n_profile import log_e
from pandera import typing as pt

from domain.schemas.common.base_dataframe import MultiTimeframeTimeseries
from domain.schemas.common.ohlcv import MultiTimeframeOHLC
from helper.pandera import pandera_validate

FUTURE_QUADRANTS_N = 8
_REQUIRED_QUADRANT_COLUMNS = "required_quadrant_columns"


def _quadrant_field(suffix: str, quadrants: int = FUTURE_QUADRANTS_N) -> pt.Series[float]:
    return cast(
        pt.Series[float],
        pa.Field(
            alias=rf"q[1-{quadrants}]_{suffix}",
            regex=True,
            nullable=True,
            metadata={_REQUIRED_QUADRANT_COLUMNS: tuple(f"q{q}_{suffix}" for q in range(1, quadrants + 1))},
        ),
    )


class RequiredQuadrantColumns(MultiTimeframeOHLC):
    """Require every concrete column represented by inherited quadrant regex fields."""

    @pa.dataframe_check
    @classmethod
    @pandera_validate(allow_pandas_dataframe=True)
    def has_all_quadrant_columns(cls, data: pd.DataFrame) -> bool:
        required = {
            column_name
            for column in cls.to_schema().columns.values()
            for column_name in (column.metadata or {}).get(_REQUIRED_QUADRANT_COLUMNS, ())
        }
        if not required.issubset(data.columns):
            log_e(f"Missing required quadrant columns: {required - set(data.columns)}")
        return required.issubset(data.columns)


class QuadrantHighLow(RequiredQuadrantColumns):
    """Trading candles augmented with the next eight quadrant extrema."""

    q_high: pt.Series[float] = _quadrant_field("high")
    q_low: pt.Series[float] = _quadrant_field("low")


class QuadrantBestEntries(MultiTimeframeTimeseries):
    """Quadrant rows with the selected long and short entry prices."""

    best_long_entry: pt.Series[float] = pa.Field(nullable=True)
    best_short_entry: pt.Series[float] = pa.Field(nullable=True)


class QuadrantEntryFees(MultiTimeframeTimeseries):
    """Entry rows with estimated per-direction trading fees."""

    long_trading_fee: pt.Series[float] = pa.Field(nullable=True)
    short_trading_fee: pt.Series[float] = pa.Field(nullable=True)


class QuadrantExcursionPrice(MultiTimeframeTimeseries):
    """Entry rows with the extrema and ATR needed to calculate excursions."""

    q_long_max_favored_price: pt.Series[float] = _quadrant_field("long_max_favored_price")
    q_short_min_favored_price: pt.Series[float] = _quadrant_field("short_min_favored_price")
    q_long_min_adverse_price: pt.Series[float] = _quadrant_field("long_min_adverse_price")
    q_short_max_adverse_price: pt.Series[float] = _quadrant_field("short_max_adverse_price")


class QuadrantExcursionPriceWithATR(MultiTimeframeTimeseries):
    atr_255: pt.Series[float] = pa.Field(nullable=True)


class QuadrantExcursions(MultiTimeframeTimeseries):
    """Entry rows with q1-q4 favored/adverse excursions for both directions."""

    q_long_max_favored_excursion: pt.Series[float] = _quadrant_field("long_max_favored_excursion")
    q_short_max_favored_excursion: pt.Series[float] = _quadrant_field("short_max_favored_excursion")
    q_long_max_adverse_excursion: pt.Series[float] = _quadrant_field("long_max_adverse_excursion")
    q_short_max_adverse_excursion: pt.Series[float] = _quadrant_field("short_max_adverse_excursion")


class QuadrantRer(MultiTimeframeTimeseries):
    """Excursion rows with q1-q8 RER values for both directions."""

    q_long_rer: pt.Series[float] = _quadrant_field("long_rer")
    q_short_rer: pt.Series[float] = _quadrant_field("short_rer")


class BiActionRank(MultiTimeframeTimeseries):
    """Quadrant RER rows with the chosen rank per direction."""

    long_chosen_rank: pt.Series[pa.Int16] = pa.Field(nullable=True)
    short_chosen_rank: pt.Series[pa.Int16] = pa.Field(nullable=True)


class ChosenRank(MultiTimeframeTimeseries):
    """Quadrant RER rows with the chosen q1-q4 rank per direction."""

    q_rank: pt.Series[pa.Int8] = pa.Field(nullable=True)


class BestMfe(MultiTimeframeTimeseries):
    """Quadrant RER rows with the best value for each direction."""

    mfe: pt.Series[float] = pa.Field(nullable=True)


# class BiActionMfe(MultiTimeframeTimeseries):
#     """Quadrant RER rows with the chosen q1-q4 rank per direction."""

#     long_mfe: pt.Series[float] = pa.Field(nullable=True)
#     short_mfe: pt.Series[float] = pa.Field(nullable=True)


class BestRer(MultiTimeframeTimeseries):
    """Quadrant RER rows with the best value for each direction."""

    best_long_rer: pt.Series[float] = pa.Field(nullable=True)
    best_short_rer: pt.Series[float] = pa.Field(nullable=True)


# class BiActionRer(MultiTimeframeTimeseries):
#     """Quadrant RER rows with the chosen q1-q4 rank per direction."""

#     long_chosen_rank: pt.Series[float] = pa.Field(nullable=True)
#     short_chosen_rank: pt.Series[float] = pa.Field(nullable=True)


class AnchorAction(MultiTimeframeTimeseries):
    """Best-RER rows with the selected anchor action."""

    action_long: pt.Series[pa.Float32] = pa.Field(nullable=True)
    action_short: pt.Series[pa.Float32] = pa.Field(nullable=True)
    action_none: pt.Series[pa.Float32] = pa.Field(nullable=True)


class ActionMfeRerDiagnostics(
    QuadrantBestEntries,
    QuadrantExcursionPrice,
    QuadrantExcursions,
    QuadrantRer,
    BiActionRank,
    BestRer,
    AnchorAction,
):
    """Plot-facing label intermediates before final schema filtering."""


class ActionMfeRerLabels(BestMfe, AnchorAction):
    """Final OHLCV rows plus action-head and MFE/RER targets."""

    rer: pt.Series[float] = pa.Field(nullable=True)

    class Config:
        strict = "filter"
