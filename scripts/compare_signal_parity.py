"""Compare Python causal signal counts with an inert MQL event-loop summary."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from xauusd.audit import AuditEventKind, AuditJournal  # noqa: E402
from xauusd.market_state import MarketState  # noqa: E402
from xauusd.replay import ReplayRunner, build_replay_days  # noqa: E402
from xauusd.tick_data import load_mt5_tick_bars  # noqa: E402
from xauusd.zones import load_zone_csv  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--zones", type=Path, default=Path("data/ranges.csv"))
    parser.add_argument("--broker-utc-offset-minutes", type=int, required=True)
    parser.add_argument("--expect-breakout", type=int, required=True)
    parser.add_argument("--expect-reversal", type=int, required=True)
    parser.add_argument("--expect-pullback", type=int, required=True)
    args = parser.parse_args()

    bars = load_mt5_tick_bars(
        args.ticks,
        broker_utc_offset=timedelta(minutes=args.broker_utc_offset_minutes),
    )
    days = build_replay_days(bars, load_zone_csv(args.zones))
    counts: Counter[str] = Counter()
    for day in days:
        result = ReplayRunner(MarketState(), AuditJournal()).run_day(day)
        counts.update(
            event.signal_family.value
            for event in result.events
            if event.kind is AuditEventKind.SIGNAL
        )

    expected = {
        "breakout": args.expect_breakout,
        "reversal": args.expect_reversal,
        "pullback": args.expect_pullback,
    }
    actual = {family: counts[family] for family in expected}
    if actual != expected:
        raise RuntimeError(f"Signal parity mismatch: Python={actual}; MQL={expected}")
    print(f"SIGNAL_PARITY_PASS bars={len(bars)} counts={actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
