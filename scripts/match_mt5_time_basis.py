"""Match an inert MQL server-time/Bid probe against MT5 UTC tick history."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path


def server_to_utc(server_time: datetime, offset_minutes: int) -> datetime:
    if server_time.tzinfo is not None:
        raise ValueError("server probe time must be naive")
    return (server_time - timedelta(minutes=offset_minutes)).replace(tzinfo=timezone.utc)


def bid_sequence(value: str) -> tuple[float, ...]:
    bids = tuple(float(item) for item in value.split(","))
    if not bids:
        raise argparse.ArgumentTypeError("at least one Bid is required")
    return bids


def contains_bid_sequence(actual: list[float], expected: tuple[float, ...]) -> bool:
    width = len(expected)
    return any(
        all(abs(actual[start + index] - bid) <= 1e-9 for index, bid in enumerate(expected))
        for start in range(len(actual) - width + 1)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--server-time", type=datetime.fromisoformat, required=True)
    parser.add_argument("--bids", type=bid_sequence, required=True)
    args = parser.parse_args()

    import MetaTrader5 as mt5

    if not mt5.initialize(path=str(args.terminal)):
        code, message = mt5.last_error()
        raise RuntimeError(f"MT5 initialization failed ({code}: {message})")
    try:
        matches: list[int] = []
        for offset in range(-14 * 60, 14 * 60 + 1, 30):
            center = server_to_utc(args.server_time, offset)
            ticks = mt5.copy_ticks_range(
                args.symbol,
                center - timedelta(seconds=1),
                center + timedelta(seconds=1),
                mt5.COPY_TICKS_ALL,
            )
            actual = [] if ticks is None else [float(tick["bid"]) for tick in ticks]
            if contains_bid_sequence(actual, args.bids):
                matches.append(offset)
        if len(matches) != 1:
            raise RuntimeError(f"Expected one matching UTC offset; found {len(matches)}")
        print(f"VERIFIED_BROKER_UTC_OFFSET_MINUTES={matches[0]}")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
