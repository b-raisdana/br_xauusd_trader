"""Decimal-compatible price quantization for the numeric kernel."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


import numpy as np
from numba import njit


@njit(cache=True)
def decimal_price(value: float, digits: int) -> float:
    """Quantize the shortest round-tripping decimal, with half ties away from zero.

    The scalar contract quantizes Decimal(str(value)), not the binary float.
    Searching significant decimal coefficients avoids bankers' rounding and
    binary multiplication moving values such as 1.005 below their decimal tie.
    """
    magnitude = abs(value)
    if magnitude == 0:
        return value
    exponent = int(np.floor(np.log10(magnitude)))
    for significant in range(1, 18):
        scale_exponent = significant - 1 - exponent
        scale = 10.0**scale_exponent
        coefficient = np.rint(magnitude * scale)
        if coefficient / scale == magnitude:
            adjustment = digits - scale_exponent
            if adjustment >= 0:
                result = coefficient * (10.0**adjustment)
            else:
                divisor = 10.0 ** (-adjustment)
                result = np.floor(coefficient / divisor + 0.5)
            return np.copysign(result / (10.0**digits), value)
    return np.copysign(np.floor(magnitude * (10.0**digits) + 0.5) / (10.0**digits), value)
