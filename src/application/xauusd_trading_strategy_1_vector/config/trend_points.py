"""Number of preceding bar extrema that define the trend reference.

`TREND_POINTS_N` is the single setting that sizes the trend window. Every
definition, usage and validation point of the `trend_high_<i>` / `trend_low_<i>`
state columns is derived from it through the helpers below, so resizing the
window is a one-value change.
"""

from __future__ import annotations

TREND_POINTS_N: int = 3
TREND_SIDES: tuple[str, ...] = ("high", "low")
_TREND_SIDE_ALIASES: dict[str, str] = {"high": "trend_high", "low": "trend_low"}


def trend_point_count(points: int = TREND_POINTS_N) -> int:
    """Return the validated number of trend points."""
    if points < 1:
        raise ValueError(f"Trend points must be at least 1, got {points}")
    return points


def trend_columns(side: str, points: int = TREND_POINTS_N) -> list[str]:
    """Return the state column names of one trend side, oldest slot first."""
    if side not in _TREND_SIDE_ALIASES:
        raise ValueError(f"Unknown trend side {side!r}; expected one of {sorted(_TREND_SIDE_ALIASES)}")
    return [f"{_TREND_SIDE_ALIASES[side]}_{index}" for index in range(trend_point_count(points))]


def trend_row_columns(points: int = TREND_POINTS_N) -> list[str]:
    """Return every trend state column name, grouped by side."""
    return [column for side in TREND_SIDES for column in trend_columns(side, points)]


def trend_slot_positions(points: int = TREND_POINTS_N) -> list[int]:
    """Return the slot indexes used to gather preceding bar extrema."""
    return list(range(trend_point_count(points)))
