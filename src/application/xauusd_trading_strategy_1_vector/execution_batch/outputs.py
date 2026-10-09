"""Compiled export of event/state lists to contiguous primitive arrays."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from numpy.typing import NDArray

if TYPE_CHECKING:
    pass


import numpy as np
from numba import njit


@njit(cache=True)
def integer_rows(rows: Sequence[NDArray[np.int64]], width: int) -> NDArray[np.int64]:
    count = 0
    for row in rows:
        if len(row) == width:
            count += 1
    result = np.empty((count, width), dtype=np.int64)
    at = 0
    for row in rows:
        if len(row) == width:
            result[at] = row
            at += 1
    return result


@njit(cache=True)
def float_rows(rows: Sequence[NDArray[np.float64]], width: int) -> NDArray[np.float64]:
    count = 0
    for row in rows:
        if len(row) == width:
            count += 1
    result = np.empty((count, width), dtype=np.float64)
    at = 0
    for row in rows:
        if len(row) == width:
            result[at] = row
            at += 1
    return result
