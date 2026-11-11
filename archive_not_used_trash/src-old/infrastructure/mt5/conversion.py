import re

import MetaTrader5 as mt5


def timeframe_to_mt5(timeframe: str) -> int:
    timeframe_simplifier = {"min": "m"}
    timeframe_map: dict[str, tuple[list[int], str]] = {
        "m": ([1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30], "M"),
        "h": ([1, 2, 3, 4, 6, 8, 12], "H"),
        "d": ([1], "D"),
        "M": ([1], "MN"),
    }

    match = re.fullmatch(r"(\d+)([a-zA-Z\-]*)", timeframe)
    if match is None:
        raise ValueError(f"Invalid timeframe: {timeframe!r}")
    digit_part = int(match.group(1))
    char_part = match.group(2)

    if char_part in timeframe_simplifier:
        char_part = timeframe_simplifier[char_part]

    allowed_digits, mt5_prefix = timeframe_map[char_part]

    if digit_part not in allowed_digits:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}")

    mt5_timeframe = getattr(mt5, f"TIMEFRAME_{mt5_prefix}{digit_part}", None)

    if mt5_timeframe is None or not isinstance(mt5_timeframe, int):
        raise ValueError(f"MT5 timeframe not found for: {timeframe!r}")

    return mt5_timeframe
