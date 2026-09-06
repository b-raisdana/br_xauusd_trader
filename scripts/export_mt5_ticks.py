"""Export read-only MT5 UTC ticks into ignored local cache for later normalization."""

from __future__ import annotations

import argparse
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise argparse.ArgumentTypeError("timestamp must include an explicit UTC offset")
    return parsed


def cache_output(value: str) -> Path:
    repository = Path(__file__).resolve().parents[1]
    cache_root = (repository / "data" / "cache").resolve()
    output = (repository / value).resolve()
    if not output.is_relative_to(cache_root):
        raise argparse.ArgumentTypeError("output must be inside ignored data/cache")
    return output


def export_ticks(
    *, terminal: Path, symbol: str, start: datetime, end: datetime, output: Path
) -> tuple[int, str]:
    if not terminal.is_file():
        raise ValueError("terminal executable does not exist")
    if not symbol.strip():
        raise ValueError("symbol is required")
    if end <= start:
        raise ValueError("end must follow start")

    import MetaTrader5 as mt5  # type: ignore[import-untyped]

    if not mt5.initialize(path=str(terminal)):
        code, message = mt5.last_error()
        raise RuntimeError(f"MT5 initialization failed ({code}: {message})")
    try:
        if mt5.symbol_info(symbol) is None:
            raise RuntimeError("requested symbol is unavailable")
        ticks: Any = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
        if ticks is None:
            raise RuntimeError("MT5 tick query failed")
        output.parent.mkdir(parents=True, exist_ok=True)
        fields = ("time_msc", "bid", "ask", "last", "volume", "flags", "volume_real")
        with output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(fields)
            for tick in ticks:
                writer.writerow(tick[field] for field in fields)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        return len(ticks), digest
    finally:
        mt5.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--from-utc", dest="start", type=utc_datetime, required=True)
    parser.add_argument("--to-utc", dest="end", type=utc_datetime, required=True)
    parser.add_argument("--output", type=cache_output, required=True)
    args = parser.parse_args()
    count, digest = export_ticks(
        terminal=args.terminal,
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        output=args.output,
    )
    print(f"Exported {count} UTC ticks; SHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
