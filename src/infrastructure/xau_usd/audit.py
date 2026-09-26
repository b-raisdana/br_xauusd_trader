from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from archive_not_used_trash.xauusd_trading_strategy_1 import XauExecutionProjection, XauOrderAuditEvent

from domain.xau_usd.enums import XauEntryRejection

from .execution import execution_request_id_valid, initialize_execution_projection

DEFAULT_AUDIT_ROOT = Path(__file__).resolve().parents[3] / "data" / "mt5"


def audit_text_valid(value: str) -> bool:
    return bool(value) and not any(character in value for character in '"\\\r\n')


def broker_timestamp(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return int(value.timestamp())
    return int(value.timestamp())


def serialize_order_audit(event: XauOrderAuditEvent) -> str | None:
    if (
        not audit_text_valid(event.event_id)
        or not execution_request_id_valid(event.request_id)
        or not audit_text_valid(event.zone_id)
        or not audit_text_valid(event.rule_ids)
        or event.broker_time is None
        or broker_timestamp(event.broker_time) is None
        or broker_timestamp(event.broker_time) <= 0
        or event.entry <= 0.0
    ):
        return None

    payload = {
        "schema_version": 1,
        "kind": "order",
        "event_id": event.event_id,
        "execution_request_id": event.request_id,
        "zone_id": event.zone_id,
        "rule_ids": event.rule_ids,
        "direction": int(event.direction),
        "order_type": int(event.order_type),
        "broker_time": broker_timestamp(event.broker_time),
        "entry": f"{event.entry:.10f}",
        "stop_loss": f"{event.stop_loss:.10f}",
        "take_profit": f"{event.take_profit:.10f}",
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _audit_path(path: str | Path) -> Path | None:
    candidate = Path(path)
    if ".." in candidate.parts:
        return None
    return candidate if candidate.is_absolute() else DEFAULT_AUDIT_ROOT / candidate


def append_audit_line(path: str | Path, line: str) -> bool:
    audit_path = _audit_path(path)
    if audit_path is None or not line:
        return False

    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(line + "\r\n")
            handle.flush()
        return True
    except OSError:
        return False


def append_order_then_project(
    audit_file: str | Path,
    decision: XauEntryRejection,
    event: XauOrderAuditEvent,
    projections: list[XauExecutionProjection],
) -> bool:
    if decision != XauEntryRejection.ALLOWED:
        return False

    projection = initialize_execution_projection(
        event.request_id,
        event.order_type,
        event.direction,
        event.entry,
        event.stop_loss,
        event.take_profit,
        event.broker_time,
    )
    line = serialize_order_audit(event)
    if projection is None or line is None or not append_audit_line(audit_file, line):
        return False

    projections.append(projection)
    return True
