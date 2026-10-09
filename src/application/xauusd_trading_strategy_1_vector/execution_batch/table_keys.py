"""Stable event keys and primitive output array conversion."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from numpy.typing import NDArray

if TYPE_CHECKING:
    pass


KINDS = np.array(
    ["SUBMIT", "FILL", "CLOSE", "REJECT", "CANCEL", "MODIFY", "CLOSE_REJECT", "CANCEL_REJECT", "MODIFY_REJECT"]
)
REASONS = np.array(
    [
        "",
        "SL",
        "TP",
        "SESSION_OR_RESTART",
        "POSITION_CAP",
        "PORTFOLIO_RISK",
        "WINDOW_EXPIRED",
        "DAILY_LOSS",
        "INVALID_PROTECTION",
        "DAY_ROLLOVER",
        "OPPOSITE_BREAKOUT",
        "PULLBACK_FILTER",
    ]
)
NAT = np.iinfo(np.int64).min


def numeric_rows(
    rows: Sequence[NDArray[np.generic]], width: int, dtype: type[np.int64] | type[np.float64]
) -> NDArray[np.generic]:
    """Export primitive arrays inside nopython code, including empty outputs."""
    from .outputs import float_rows, integer_rows

    return integer_rows(rows, width) if dtype is np.int64 else float_rows(rows, width)


def utc(values: NDArray[np.int64]) -> pd.DatetimeIndex:
    return pd.to_datetime(np.where(values < 0, NAT, values), utc=True)
