"""Generate presentation reports from deterministic replay results."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from xauusd.audit import AuditEventKind, AuditJournal
from xauusd.market_state import MarketState
from xauusd.replay import ReplayDay, ReplayResult, ReplayRunner, build_replay_days
from xauusd.tick_data import load_mt5_tick_bars
from xauusd.zones import load_zone_csv


def compute_summary(result: ReplayResult, days: tuple[ReplayDay, ...]) -> dict[str, Any]:
    """Compute summary statistics from replay results."""
    events = result.events
    expiries = result.pullback_expiries

    signal_counts: dict[str, int] = {}
    for event in events:
        if event.kind is AuditEventKind.SIGNAL:
            family = event.signal_family.value if event.signal_family else "unknown"
            signal_counts[family] = signal_counts.get(family, 0) + 1

    filled = [event for event in events if event.kind is AuditEventKind.FILL]
    rejected = [event for event in events if event.kind is AuditEventKind.REJECT]

    close_events = [e for e in events if e.kind is AuditEventKind.CLOSE]
    tp_hits = [
        e
        for e in close_events
        if "tp" in (e.reason or "").lower() or "take_profit" in (e.reason or "").lower()
    ]
    sl_hits = [
        e
        for e in close_events
        if "sl" in (e.reason or "").lower() or "stop_loss" in (e.reason or "").lower()
    ]
    session_closes = [e for e in close_events if "session" in (e.reason or "").lower()]
    other_closes = [
        e for e in close_events if e not in tp_hits and e not in sl_hits and e not in session_closes
    ]

    total_bars = sum(len(day.bars) for day in days)
    total_ticks = sum(sum(len(bar.ticks) for bar in day.bars) for day in days)

    return {
        "days_processed": len(days),
        "total_bars": total_bars,
        "total_ticks": total_ticks,
        "signal_counts": signal_counts,
        "executions": {
            "filled": len(filled),
            "rejected": len(rejected),
            "total": len(filled) + len(rejected),
        },
        "closes": {
            "take_profit": len(tp_hits),
            "stop_loss": len(sl_hits),
            "session_end": len(session_closes),
            "other": len(other_closes),
            "total": len(close_events),
        },
        "pullback_expiries": len(expiries),
        "audit_events_total": len(events),
    }


def format_text_report(
    summary: dict[str, Any], days: tuple[ReplayDay, ...], result: ReplayResult
) -> str:
    """Format summary as human-readable text report."""
    lines = [
        "=" * 60,
        "XAUUSD M15 PRICE-ACTION REPLAY REPORT",
        "=" * 60,
        f"Generated: {datetime.now().isoformat()}",
        f"Days processed: {summary['days_processed']}",
        f"Total M15 bars: {summary['total_bars']}",
        f"Total ticks: {summary['total_ticks']}",
        "",
        "SIGNALS GENERATED:",
        "-" * 40,
    ]
    for family, count in sorted(summary["signal_counts"].items()):
        lines.append(f"  {family.capitalize():12s}: {count}")

    lines.extend(
        [
            "",
            "EXECUTION OUTCOMES:",
            "-" * 40,
            f"  Filled   : {summary['executions']['filled']}",
            f"  Rejected : {summary['executions']['rejected']}",
            f"  Total    : {summary['executions']['total']}",
            "",
            "POSITION CLOSES:",
            "-" * 40,
            f"  Take Profit : {summary['closes']['take_profit']}",
            f"  Stop Loss   : {summary['closes']['stop_loss']}",
            f"  Session End : {summary['closes']['session_end']}",
            f"  Other       : {summary['closes']['other']}",
            f"  Total       : {summary['closes']['total']}",
            "",
            "PULLBACK EXPIRIES:",
            "-" * 40,
            f"  Expired pullback candidates: {summary['pullback_expiries']}",
            "",
            "AUDIT EVENTS:",
            "-" * 40,
            f"  Total immutable events: {summary['audit_events_total']}",
            "",
            "DAILY BREAKDOWN:",
            "-" * 40,
        ]
    )

    for day in days:
        day_signals = sum(
            1
            for event in result.events
            if event.kind is AuditEventKind.SIGNAL and event.broker_time.date() == day.broker_day
        )
        day_bars = len(day.bars)
        day_ticks = sum(len(bar.ticks) for bar in day.bars)
        lines.append(
            f"  {day.broker_day.isoformat()}: "
            f"{day_bars} bars, {day_ticks} ticks, {day_signals} signals"
        )

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def format_json_report(
    summary: dict[str, Any], days: tuple[ReplayDay, ...], result: ReplayResult
) -> dict[str, Any]:
    """Format summary as structured JSON."""
    return {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "days_processed": summary["days_processed"],
        },
        "summary": summary,
        "daily_breakdown": [
            {
                "date": day.broker_day.isoformat(),
                "bars": len(day.bars),
                "ticks": sum(len(bar.ticks) for bar in day.bars),
                "zones": len(day.zones),
                "seed_candles": len(day.seed_candles),
            }
            for day in days
        ],
        "events": [
            {
                "kind": event.kind.value,
                "broker_time": event.broker_time.isoformat() if event.broker_time else None,
                "zone_id": event.zone_id,
                "signal_family": event.signal_family.value if event.signal_family else None,
                "direction": event.direction.value if event.direction else None,
                "entry": str(event.entry) if event.entry else None,
                "rule_ids": list(event.rule_ids) if event.rule_ids else [],
            }
            for event in result.events
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate presentation reports from replay results"
    )
    parser.add_argument("--ticks", type=Path, required=True, help="Path to MT5 tick CSV file")
    parser.add_argument(
        "--zones", type=Path, default=Path("data/ranges.csv"), help="Path to zones CSV"
    )
    parser.add_argument(
        "--broker-utc-offset-minutes", type=int, required=True, help="Broker UTC offset in minutes"
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--output", type=Path, help="Output file path (stdout if omitted)")
    args = parser.parse_args()

    from datetime import timedelta

    bars = load_mt5_tick_bars(
        args.ticks,
        broker_utc_offset=timedelta(minutes=args.broker_utc_offset_minutes),
    )
    days = build_replay_days(bars, load_zone_csv(args.zones))

    state = MarketState()
    journal = AuditJournal()
    runner = ReplayRunner(state, journal)

    all_results: list[ReplayResult] = []
    for day in days:
        result = runner.run_day(day)
        all_results.append(result)

    combined_events = tuple(event for r in all_results for event in r.events)
    combined_expiries = tuple(expiry for r in all_results for expiry in r.pullback_expiries)

    combined_result = ReplayResult(events=combined_events, pullback_expiries=combined_expiries)
    summary = compute_summary(combined_result, days)

    if args.format == "json":
        output = json.dumps(format_json_report(summary, days, combined_result), indent=2)
    else:
        output = format_text_report(summary, days, combined_result)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
