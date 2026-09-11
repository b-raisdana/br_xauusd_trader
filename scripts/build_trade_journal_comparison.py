"""Build normalized trade-level comparison data for Final MVP vs legacy RISK200."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OLD = Path(r"C:\Users\b.dana\Desktop\XAUUSD test charts\RISK200_GROSS_15_journal.csv")
FINAL = ROOT / "artifacts/final_reporting/final_event_ledger.csv"
OUTPUT = ROOT / "outputs/20260910_trade_comparison/comparison_data.json"


def stamp(value: str, fmt: str) -> datetime:
    return datetime.strptime(value[:19], fmt)


def candle(value: datetime) -> str:
    return value.replace(minute=(value.minute // 15) * 15, second=0, microsecond=0).isoformat()


def old_trades() -> list[dict[str, Any]]:
    with OLD.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    fills = {row["position_ticket"]: row for row in rows if row["event"] == "ORDER_FILLED"}
    result = []
    for close in (row for row in rows if row["event"] == "POSITION_CLOSED"):
        fill = fills[close["position_ticket"]]
        opened = stamp(fill["server_time"], "%Y.%m.%d %H:%M:%S")
        closed = stamp(close["server_time"], "%Y.%m.%d %H:%M:%S")
        match = re.search(r"position_net=([-0-9.]+)", close["reason_error"])
        signal = fill["signal_type"]
        result.append(
            {
                "version": "RISK200_GROSS_15",
                "day": opened.date().isoformat(),
                "candle": candle(opened),
                "open_time": opened.isoformat(),
                "close_time": closed.isoformat(),
                "family": "pullback" if signal.startswith("PB") else "reversal",
                "direction": "buy" if signal.endswith("B") else "sell",
                "zone": fill["zone_id"],
                "priority": "high" if signal.startswith("R") else "",
                "entry": float(fill["fill_price"]),
                "sl": float(fill["sl"]),
                "tp": float(fill["tp"]),
                "pnl": float(match.group(1)) if match else 0.0,
            }
        )
    return result


def final_trades() -> list[dict[str, Any]]:
    with FINAL.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    fills = {row["execution_request_id"]: row for row in rows if row["event_type"] == "ENTRY_FILL"}
    result = []
    for close in (row for row in rows if row["event_type"] == "POSITION_CLOSE"):
        fill = fills[close["execution_request_id"]]
        opened = stamp(fill["broker_time"], "%Y-%m-%dT%H:%M:%S")
        closed = stamp(close["broker_time"], "%Y-%m-%dT%H:%M:%S")
        result.append(
            {
                "version": "FINAL_MVP",
                "day": opened.date().isoformat(),
                "candle": candle(opened),
                "open_time": opened.isoformat(),
                "close_time": closed.isoformat(),
                "family": fill["signal_family"],
                "direction": fill["direction"],
                "zone": fill["zone_id"],
                "priority": fill["zone_priority"],
                "entry": float(fill["fill_price"]),
                "sl": float(fill["stop_loss"]),
                "tp": float(fill["take_profit"]),
                "pnl": float(close["realized_pnl_usd"]),
            }
        )
    return result


def reason(final: dict[str, Any] | None, old: dict[str, Any] | None) -> tuple[str, str]:
    if final and old:
        return (
            "همتای همان کندل/خانواده/جهت؛ اختلاف PnL از Entry، SL/TP، "
            "مدیریت سود و اجرای متفاوت است.",
            "قطعی برای هم‌ترازی؛ Attribution علت PnL ترکیبی",
        )
    if final:
        if final["family"] == "breakout":
            return (
                "Final مستقیماً Breakout را معامله می‌کند؛ نسخه قدیمی Breakout را فقط "
                "والد Pullback می‌دانست.",
                "قطعی",
            )
        if final["family"] == "reversal" and final["priority"] == "normal":
            return (
                "Final Reversal ناحیه Normal را مجاز می‌کند؛ نسخه قدیمی Reversal را "
                "High-only کرده بود.",
                "قطعی",
            )
        return (
            "در Final Fill شده ولی در Journal قدیمی همتای همان کندل وجود ندارد؛ تفاوت "
            "Trend/Parent، FreeSpace15، usage یا ترتیب Entry محتمل است.",
            "علت منفرد در این ردیف قابل اثبات نیست",
        )
    return (
        "در نسخه قدیمی Fill شده ولی در Final همتای همان کندل وجود ندارد؛ تفاوت "
        "Trend Bootstrap، سقف یک Entry در کندل، Risk/usage یا lifecycle محتمل است.",
        "Final علت Block موردی را ثبت نکرده؛ علت منفرد قابل اثبات نیست",
    )


def main() -> None:
    old, final = old_trades(), final_trades()
    buckets: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in old:
        buckets[(trade["day"], trade["candle"], trade["family"], trade["direction"])].append(trade)
    details: list[dict[str, Any]] = []
    used: set[int] = set()
    for current in final:
        candidates = buckets[
            (current["day"], current["candle"], current["family"], current["direction"])
        ]
        available = [(i, item) for i, item in enumerate(candidates) if id(item) not in used]
        previous = (
            min(available, key=lambda pair: abs(float(pair[1]["entry"]) - float(current["entry"])))[
                1
            ]
            if available
            else None
        )
        if previous:
            used.add(id(previous))
        why, confidence = reason(current, previous)
        details.append(
            {
                "status": "matched" if previous else "final_only",
                "final": current,
                "old": previous,
                "pnl_delta_final_minus_old": round(
                    float(current["pnl"]) - float(previous["pnl"]), 2
                )
                if previous
                else float(current["pnl"]),
                "reason": why,
                "evidence": confidence,
            }
        )
    for previous in old:
        if id(previous) in used:
            continue
        why, confidence = reason(None, previous)
        details.append(
            {
                "status": "old_only",
                "final": None,
                "old": previous,
                "pnl_delta_final_minus_old": -float(previous["pnl"]),
                "reason": why,
                "evidence": confidence,
            }
        )
    details.sort(key=lambda row: ((row["final"] or row["old"])["open_time"], row["status"]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"old": old, "final": final, "details": details}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"old={len(old)} final={len(final)} comparison_rows={len(details)} output={OUTPUT}")


if __name__ == "__main__":
    main()
