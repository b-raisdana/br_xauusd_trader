"""Price-encoding helpers for the cTrader integer price encoding.

cTrader transmits prices as integers. The decimal position is the symbol's
``digits`` count, so a price is recovered as ``raw / 10**digits`` (e.g. an
EURUSD tick with ``digits=5`` and raw ``108543`` decodes to ``1.08543``).
"""

from __future__ import annotations


def decode_price(raw: int, digits: int) -> float:
    """Convert a raw cTrader integer price to a floating-point price."""
    if digits < 0:
        raise ValueError("digits must be non-negative")
    return raw / (10**digits)


def pip_size(pip_position: int) -> float:
    """Size of one pip given its decimal position (e.g. 4 -> 0.0001)."""
    if pip_position < 0:
        raise ValueError("pip_position must be non-negative")
    return 10**-pip_position


def point(digits: int) -> float:
    """Size of the smallest quoted price step for ``digits`` decimal places."""
    if digits < 0:
        raise ValueError("digits must be non-negative")
    return 10**-digits
