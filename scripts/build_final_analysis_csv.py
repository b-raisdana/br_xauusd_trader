"""Build durable daily and event-level CSV evidence from the final MT5 run."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from xauusd.zones import load_zone_csv

ROOT = Path(__file__).resolve().parents[1]
TERMINAL_ID = "D0E8209F77C8CF37AD8BF550E51FF075"
LOG_PATH = (
    Path.home() / "AppData/Roaming/MetaQuotes/Terminal" / TERMINAL_ID / "Tester/logs/20260911.log"
)
AUDIT_PATH = (
    Path.home()
    / "AppData/Roaming/MetaQuotes/Tester"
    / TERMINAL_ID
    / "Agent-127.0.0.1-3000/MQL5/Files/XAUUSD_Current/orders.jsonl"
)
OUTPUT_DIR = ROOT / "artifacts/v1_stabilized"
RUN_ID = "V1_STABILIZED_23D_REAL_TICK_200"
SOURCE_HASH = "70AA7E782EC3E6AE364B88551C9810D77DD490460BCBCF7FCBC945F611569077"
COMPILED_HASH = "0C932D89CD8113EF98BBBA90BDB6FE3D1E896B6ABA1422B78E0B887F214AAD5A"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def payload(line: str) -> str:
    marker = "\tCore 1\t"
    return line.split(marker, 1)[1] if marker in line else ""


def broker_parts(message: str) -> tuple[str, str]:
    match = re.match(r"(\d{4}\.\d{2}\.\d{2}) (\d{2}:\d{2}:\d{2})\s+(.*)", message)
    if not match:
        return "", message
    stamp = datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y.%m.%d %H:%M:%S")
    return stamp.strftime("%Y-%m-%dT%H:%M:%S"), match.group(3)


def final_segment(lines: list[str]) -> list[tuple[int, str]]:
    start_pattern = (
        "testing of Experts\\XAUUSD_Current\\XAUUSD_MVP.ex5 "
        "from 2026.07.29 00:00 to 2026.08.29 00:00 started with inputs:"
    )
    starts = [index for index, line in enumerate(lines) if start_pattern in line]
    if not starts:
        raise RuntimeError("Final multi-day MT5 run start not found")
    start = starts[-1]
    end = next(
        index for index in range(start, len(lines)) if "CURRENT_EVENT_LOOP_DONE" in lines[index]
    )
    return [(index + 1, lines[index]) for index in range(start, end + 1)]


def family(rule_ids: str) -> str:
    if rule_ids.startswith("BREAKOUT"):
        return "breakout"
    if rule_ids.startswith("PULLBACK"):
        return "pullback"
    if rule_ids.startswith("REVERSAL"):
        return "reversal"
    return ""


@dataclass
class Position:
    position_ticket: str
    request_id: str
    zone_id: str
    zone_priority: str
    signal_family: str
    rule_ids: str
    direction: str
    volume: Decimal
    entry_time: str
    entry_price: Decimal
    order_ticket: str
    deal_ticket: str


EVENT_FIELDS = [
    "run_id",
    "event_sequence",
    "source_log_line",
    "broker_time",
    "broker_day",
    "event_type",
    "status",
    "signal_family",
    "rule_ids",
    "event_id",
    "execution_request_id",
    "zone_id",
    "zone_priority",
    "direction",
    "order_type",
    "order_ticket",
    "deal_ticket",
    "position_ticket",
    "volume_lots",
    "requested_entry",
    "fill_price",
    "position_entry_price",
    "stop_loss",
    "take_profit",
    "close_reason",
    "realized_pnl_usd",
    "daily_cumulative_pnl_usd",
    "run_cumulative_pnl_usd",
    "retcode",
    "source_kind",
    "raw_evidence",
    "ea_source_sha256",
    "ea_compiled_sha256",
    "config_path",
    "model",
]


def empty_event(line_no: int, stamp: str, event_type: str, raw: str) -> dict[str, str]:
    return {field: "" for field in EVENT_FIELDS} | {
        "run_id": RUN_ID,
        "source_log_line": str(line_no),
        "broker_time": stamp,
        "broker_day": stamp[:10],
        "event_type": event_type,
        "source_kind": "MT5_NATIVE_LOG",
        "raw_evidence": raw,
        "ea_source_sha256": SOURCE_HASH,
        "ea_compiled_sha256": COMPILED_HASH,
        "config_path": "config/mt5/tester_multiday_200.ini",
        "model": "Every Tick Based on Real Ticks",
    }


def add_audit(event: dict[str, str], audit: dict[str, Any], priority: str) -> None:
    direction = "buy" if int(audit["direction"]) == 0 else "sell"
    order_type = "market" if int(audit["order_type"]) == 0 else "pending_stop"
    event.update(
        {
            "signal_family": family(str(audit["rule_ids"])),
            "rule_ids": str(audit["rule_ids"]),
            "event_id": str(audit["event_id"]),
            "execution_request_id": str(audit["execution_request_id"]),
            "zone_id": str(audit["zone_id"]),
            "zone_priority": priority,
            "direction": direction,
            "order_type": order_type,
            "requested_entry": str(audit["entry"]),
            "stop_loss": str(audit["stop_loss"]),
            "take_profit": str(audit["take_profit"]),
            "volume_lots": "0.01",
        }
    )


def build_events(
    segment: list[tuple[int, str]], audits: list[dict[str, Any]]
) -> list[dict[str, str]]:
    zones = load_zone_csv(ROOT / "data/ranges.csv")
    priorities = {zone.zone_id: zone.priority.value for day in zones.values() for zone in day}
    events: list[dict[str, str]] = []
    audit_index = 0
    pending_orders: list[dict[str, Any]] = []
    positions: dict[str, Position] = {}
    deal_context: dict[str, Any] | None = None

    attempt_re = re.compile(
        r"^(failed )?(market (buy|sell)|(buy|sell) stop) 0\.01 XAUUSD(?!, close)"
    )
    deal_re = re.compile(
        r"^deal #(\d+) (buy|sell) ([0-9.]+) XAUUSD at ([0-9.]+) done \(based on order #(\d+)\)"
    )
    pending_trigger_re = re.compile(
        r"^order \[#(\d+) (buy|sell) stop ([0-9.]+) XAUUSD at ([0-9.]+)\] triggered"
    )
    close_trigger_re = re.compile(
        r"^(stop loss|take profit) triggered #(\d+) (buy|sell) ([0-9.]+) XAUUSD "
    )
    market_close_re = re.compile(r"^market (buy|sell) ([0-9.]+) XAUUSD, close #(\d+)")
    modify_re = re.compile(
        r"^position modified \[#(\d+) (buy|sell) ([0-9.]+) XAUUSD ([0-9.]+) "
        r"sl: ([0-9.]+) tp: ([0-9.]+)\]"
    )
    cancel_re = re.compile(
        r"^order canceled \[#(\d+) (buy|sell) stop ([0-9.]+) XAUUSD at ([0-9.]+)\]"
    )

    for line_no, line in segment:
        message = payload(line)
        if not message:
            continue
        stamp, text = broker_parts(message)
        if not stamp:
            continue

        attempt = attempt_re.match(text)
        if attempt:
            if audit_index >= len(audits):
                raise RuntimeError("Native attempts exceed durable audit records")
            audit = audits[audit_index]
            audit_index += 1
            event = empty_event(line_no, stamp, "ENTRY_ATTEMPT", text)
            add_audit(event, audit, priorities[str(audit["zone_id"])])
            failed = bool(attempt.group(1))
            event["status"] = "rejected" if failed else "broker_accepted"
            if failed:
                event["event_type"] = "ENTRY_REJECT"
                reason = text.rsplit("[", 1)[-1].rstrip("]") if "[" in text else ""
                event["close_reason"] = reason
            elif event["order_type"] == "market":
                deal_context = {"kind": "open", "audit": audit, "priority": event["zone_priority"]}
            else:
                pending_orders.append({"audit": audit, "priority": event["zone_priority"]})
            events.append(event)
            continue

        pending_trigger = pending_trigger_re.match(text)
        if pending_trigger:
            direction = pending_trigger.group(2)
            entry = Decimal(pending_trigger.group(4))
            match_index = next(
                index
                for index, item in enumerate(pending_orders)
                if ("buy" if int(item["audit"]["direction"]) == 0 else "sell") == direction
                and Decimal(str(item["audit"]["entry"])) == entry
            )
            item = pending_orders.pop(match_index)
            deal_context = {
                "kind": "open",
                "audit": item["audit"],
                "priority": item["priority"],
                "order_ticket": pending_trigger.group(1),
            }
            event = empty_event(line_no, stamp, "PENDING_TRIGGER", text)
            add_audit(event, item["audit"], str(item["priority"]))
            event.update({"status": "triggered", "order_ticket": pending_trigger.group(1)})
            events.append(event)
            continue

        close_trigger = close_trigger_re.match(text)
        if close_trigger:
            deal_context = {
                "kind": "close",
                "position_ticket": close_trigger.group(2),
                "reason": "stop_loss" if close_trigger.group(1) == "stop loss" else "take_profit",
            }
            pos = positions[close_trigger.group(2)]
            event = empty_event(line_no, stamp, "CLOSE_TRIGGER", text)
            event.update(
                {
                    "status": "triggered",
                    "signal_family": pos.signal_family,
                    "rule_ids": pos.rule_ids,
                    "execution_request_id": pos.request_id,
                    "zone_id": pos.zone_id,
                    "zone_priority": pos.zone_priority,
                    "direction": pos.direction,
                    "position_ticket": pos.position_ticket,
                    "volume_lots": str(pos.volume),
                    "position_entry_price": str(pos.entry_price),
                    "close_reason": str(deal_context["reason"]),
                }
            )
            events.append(event)
            continue

        market_close = market_close_re.match(text)
        if market_close:
            position_ticket = market_close.group(3)
            deal_context = {
                "kind": "close",
                "position_ticket": position_ticket,
                "reason": "market_close",
            }
            pos = positions[position_ticket]
            event = empty_event(line_no, stamp, "CLOSE_REQUEST", text)
            event.update(
                {
                    "status": "broker_accepted",
                    "signal_family": pos.signal_family,
                    "rule_ids": pos.rule_ids,
                    "execution_request_id": pos.request_id,
                    "zone_id": pos.zone_id,
                    "zone_priority": pos.zone_priority,
                    "direction": pos.direction,
                    "position_ticket": pos.position_ticket,
                    "volume_lots": str(pos.volume),
                    "position_entry_price": str(pos.entry_price),
                    "close_reason": "market_close",
                }
            )
            events.append(event)
            continue

        deal = deal_re.match(text)
        if deal and deal_context:
            deal_ticket, deal_direction, volume, fill_price, order_ticket = deal.groups()
            if deal_context["kind"] == "open":
                audit = deal_context["audit"]
                priority = str(deal_context["priority"])
                position_ticket = str(deal_context.get("order_ticket", order_ticket))
                pos = Position(
                    position_ticket=position_ticket,
                    request_id=str(audit["execution_request_id"]),
                    zone_id=str(audit["zone_id"]),
                    zone_priority=priority,
                    signal_family=family(str(audit["rule_ids"])),
                    rule_ids=str(audit["rule_ids"]),
                    direction=deal_direction,
                    volume=Decimal(volume),
                    entry_time=stamp,
                    entry_price=Decimal(fill_price),
                    order_ticket=order_ticket,
                    deal_ticket=deal_ticket,
                )
                positions[position_ticket] = pos
                event = empty_event(line_no, stamp, "ENTRY_FILL", text)
                add_audit(event, audit, priority)
                event.update(
                    {
                        "status": "filled",
                        "order_ticket": order_ticket,
                        "deal_ticket": deal_ticket,
                        "position_ticket": position_ticket,
                        "fill_price": fill_price,
                        "position_entry_price": fill_price,
                        "volume_lots": volume,
                    }
                )
            else:
                position_ticket = str(deal_context["position_ticket"])
                pos = positions.pop(position_ticket)
                exit_price = Decimal(fill_price)
                sign = Decimal("1") if pos.direction == "buy" else Decimal("-1")
                pnl = (exit_price - pos.entry_price) * pos.volume * Decimal("100") * sign
                event = empty_event(line_no, stamp, "POSITION_CLOSE", text)
                event.update(
                    {
                        "status": "closed",
                        "signal_family": pos.signal_family,
                        "rule_ids": pos.rule_ids,
                        "execution_request_id": pos.request_id,
                        "zone_id": pos.zone_id,
                        "zone_priority": pos.zone_priority,
                        "direction": pos.direction,
                        "order_ticket": order_ticket,
                        "deal_ticket": deal_ticket,
                        "position_ticket": position_ticket,
                        "volume_lots": volume,
                        "fill_price": fill_price,
                        "position_entry_price": str(pos.entry_price),
                        "close_reason": str(deal_context["reason"]),
                        "realized_pnl_usd": f"{pnl:.2f}",
                    }
                )
            events.append(event)
            deal_context = None
            continue

        modify = modify_re.match(text)
        if modify:
            position_ticket = modify.group(1)
            pos = positions[position_ticket]
            event = empty_event(line_no, stamp, "POSITION_MODIFY", text)
            event.update(
                {
                    "status": "modified",
                    "signal_family": pos.signal_family,
                    "rule_ids": pos.rule_ids,
                    "execution_request_id": pos.request_id,
                    "zone_id": pos.zone_id,
                    "zone_priority": pos.zone_priority,
                    "direction": pos.direction,
                    "position_ticket": position_ticket,
                    "volume_lots": modify.group(3),
                    "position_entry_price": modify.group(4),
                    "stop_loss": modify.group(5),
                    "take_profit": modify.group(6),
                }
            )
            events.append(event)
            continue

        cancel = cancel_re.match(text)
        if cancel:
            direction = cancel.group(2)
            entry = Decimal(cancel.group(4))
            match_index = next(
                index
                for index, item in enumerate(pending_orders)
                if ("buy" if int(item["audit"]["direction"]) == 0 else "sell") == direction
                and Decimal(str(item["audit"]["entry"])) == entry
            )
            item = pending_orders.pop(match_index)
            event = empty_event(line_no, stamp, "PENDING_CANCEL", text)
            add_audit(event, item["audit"], str(item["priority"]))
            event.update({"status": "cancelled", "order_ticket": cancel.group(1)})
            events.append(event)
            continue

        event_type = ""
        if "CURRENT_EVENT_LOOP_READY" in text:
            event_type = "DAY_START"
        elif "CURRENT_EVENT_LOOP_CLOSE" in text:
            event_type = "BAR_CLOSE_SIGNAL_SUMMARY"
        elif "TESTER_SESSION_FLAT" in text:
            event_type = "SESSION_FLAT"
        elif "CURRENT_EVENT_LOOP_DONE" in text:
            event_type = "RUN_SUMMARY"
        elif "TESTER_BROKER_REJECT" in text:
            event_type = "BROKER_REJECT_CODE"
        if event_type:
            event = empty_event(line_no, stamp, event_type, text)
            event["status"] = "observed"
            retcode = re.search(r"retcode=(\d+)", text)
            if retcode:
                event["retcode"] = retcode.group(1)
            events.append(event)

    if audit_index != len(audits):
        raise RuntimeError(f"Consumed {audit_index} of {len(audits)} audit records")
    if pending_orders or positions or deal_context:
        raise RuntimeError(
            f"Unresolved lifecycle state: pending={len(pending_orders)} positions={len(positions)}"
        )

    daily: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    cumulative = Decimal("0")
    for sequence, event in enumerate(events, start=1):
        event["event_sequence"] = str(sequence)
        if event["event_type"] == "POSITION_CLOSE":
            pnl = Decimal(event["realized_pnl_usd"])
            daily[event["broker_day"]] += pnl
            cumulative += pnl
        event["daily_cumulative_pnl_usd"] = f"{daily[event['broker_day']]:.2f}"
        event["run_cumulative_pnl_usd"] = f"{cumulative:.2f}"
    if daily["2026-08-28"] != Decimal("-16.73"):
        raise RuntimeError("Derived final-day PnL does not match native TESTER_RISK_DONE")
    return events


def write_events(path: Path, events: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDS)
        writer.writeheader()
        writer.writerows(events)


DAILY_FIELDS = [
    "broker_day",
    "scenario_id",
    "scenario_phase",
    "scenario_class",
    "is_final_version",
    "capital_usd",
    "daily_net_pnl_usd",
    "final_daily_net_pnl_usd",
    "final_minus_scenario_usd",
    "closed_trades",
    "wins",
    "losses",
    "breakeven",
    "gross_profit_usd",
    "gross_loss_usd",
    "entry_attempts",
    "entry_fills",
    "entry_rejects",
    "breakout_attempts",
    "reversal_attempts",
    "pullback_attempts",
    "zone_normal_attempts",
    "zone_high_attempts",
    "source_file",
    "comparison_note",
    "ea_source_sha256",
    "ea_compiled_sha256",
]


def final_daily_rows(events: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    days = sorted({event["broker_day"] for event in events if event["event_type"] == "DAY_START"})
    by_day: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        by_day[event["broker_day"]].append(event)
    result: dict[str, dict[str, str]] = {}
    for day in days:
        rows = by_day[day]
        closes = [row for row in rows if row["event_type"] == "POSITION_CLOSE"]
        attempts = [row for row in rows if row["event_type"] in {"ENTRY_ATTEMPT", "ENTRY_REJECT"}]
        fills = [row for row in rows if row["event_type"] == "ENTRY_FILL"]
        pnls = [Decimal(row["realized_pnl_usd"]) for row in closes]
        result[day] = {
            "broker_day": day,
            "scenario_id": RUN_ID,
            "scenario_phase": "V1_STABILIZED_FREEZE",
            "scenario_class": "current_native_mt5",
            "is_final_version": "true",
            "capital_usd": "200.00",
            "daily_net_pnl_usd": f"{sum(pnls, Decimal('0')):.2f}",
            "final_daily_net_pnl_usd": f"{sum(pnls, Decimal('0')):.2f}",
            "final_minus_scenario_usd": "0.00",
            "closed_trades": str(len(closes)),
            "wins": str(sum(pnl > 0 for pnl in pnls)),
            "losses": str(sum(pnl < 0 for pnl in pnls)),
            "breakeven": str(sum(pnl == 0 for pnl in pnls)),
            "gross_profit_usd": f"{sum((p for p in pnls if p > 0), Decimal('0')):.2f}",
            "gross_loss_usd": f"{-sum((p for p in pnls if p < 0), Decimal('0')):.2f}",
            "entry_attempts": str(len(attempts)),
            "entry_fills": str(len(fills)),
            "entry_rejects": str(sum(row["event_type"] == "ENTRY_REJECT" for row in attempts)),
            "breakout_attempts": str(sum(row["signal_family"] == "breakout" for row in attempts)),
            "reversal_attempts": str(sum(row["signal_family"] == "reversal" for row in attempts)),
            "pullback_attempts": str(sum(row["signal_family"] == "pullback" for row in attempts)),
            "zone_normal_attempts": str(sum(row["zone_priority"] == "normal" for row in attempts)),
            "zone_high_attempts": str(sum(row["zone_priority"] == "high" for row in attempts)),
            "source_file": "artifacts/v1_stabilized/v1_event_ledger.csv",
            "comparison_note": (
                "Canonical final native MT5 result; realized PnL reconciles to final balance."
            ),
            "ea_source_sha256": SOURCE_HASH,
            "ea_compiled_sha256": COMPILED_HASH,
        }
    return result


def historical_rows(final_rows: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    sources = [
        ROOT / "legacy_reference/PREVIOUS_TECHNICAL_BUNDLE/results/DAILY_MATRIX_FINALIST_MT5.csv",
        ROOT / "legacy_reference/PREVIOUS_TECHNICAL_BUNDLE/results/DAILY_MATRIX_AR_RISK_01.csv",
        ROOT / "legacy_reference/PREVIOUS_TECHNICAL_BUNDLE/results/DAILY_MATRIX_AR_OPS_01.csv",
    ]
    rows: list[dict[str, str]] = []
    for source in sources:
        with source.open(newline="", encoding="utf-8-sig") as handle:
            for old in csv.DictReader(handle):
                day = datetime.strptime(old["date"], "%Y.%m.%d").strftime("%Y-%m-%d")
                if day not in final_rows:
                    continue
                final_pnl = Decimal(final_rows[day]["daily_net_pnl_usd"])
                old_pnl = Decimal(old["net_pnl"])
                capital_match = re.search(r"(200|300)", old["run_id"])
                row = {field: "" for field in DAILY_FIELDS}
                row.update(
                    {
                        "broker_day": day,
                        "scenario_id": old["run_id"],
                        "scenario_phase": old["phase"],
                        "scenario_class": "legacy_regression_scenario",
                        "is_final_version": "false",
                        "capital_usd": capital_match.group(1) if capital_match else "",
                        "daily_net_pnl_usd": f"{old_pnl:.2f}",
                        "final_daily_net_pnl_usd": f"{final_pnl:.2f}",
                        "final_minus_scenario_usd": f"{final_pnl - old_pnl:.2f}",
                        "closed_trades": old["trades"],
                        "source_file": str(source.relative_to(ROOT)).replace("\\", "/"),
                        "comparison_note": (
                            "Descriptive comparison only: legacy scenarios use superseded "
                            "rules and are not a controlled A/B against the final version."
                        ),
                        "ea_source_sha256": SOURCE_HASH,
                        "ea_compiled_sha256": COMPILED_HASH,
                    }
                )
                rows.append(row)
    return rows


def write_daily(path: Path, events: list[dict[str, str]]) -> None:
    final_rows = final_daily_rows(events)
    rows = list(final_rows.values()) + historical_rows(final_rows)
    rows.sort(
        key=lambda row: (row["broker_day"], row["is_final_version"] != "true", row["scenario_id"])
    )
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=DAILY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if sha256(ROOT / "src/mt5/XAUUSD_MVP.mq5") != SOURCE_HASH:
        raise RuntimeError("Current EA source hash differs from frozen final evidence")
    evidence = json.loads((OUTPUT_DIR / "evidence.json").read_text(encoding="utf-8"))
    if evidence["provenance"]["compiled_sha256"].upper() != COMPILED_HASH:
        raise RuntimeError("Frozen V1 compiled hash differs from structured evidence")
    lines = LOG_PATH.read_text(encoding="utf-16", errors="strict").splitlines()
    segment = final_segment(lines)
    audits = [json.loads(line) for line in AUDIT_PATH.read_text(encoding="ascii").splitlines()]
    if len(audits) != 249:
        raise RuntimeError(f"Expected 249 durable audit entries, found {len(audits)}")
    events = build_events(segment, audits)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_events(OUTPUT_DIR / "v1_event_ledger.csv", events)
    write_daily(OUTPUT_DIR / "v1_daily_performance_comparison.csv", events)
    total = sum(
        Decimal(event["realized_pnl_usd"])
        for event in events
        if event["event_type"] == "POSITION_CLOSE"
    )
    print(f"events={len(events)} pnl={total:.2f} outputs={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
