from __future__ import annotations

from datetime import datetime
from typing import Protocol

from domain.xau_usd.models import XauVisualMarker, XauZone


class ChartObjectBackend(Protocol):
    def find(self, chart_id: int, name: str) -> int: ...
    def create(self, chart_id: int, name: str, object_type: str, time: datetime, price: float) -> bool: ...
    def set_integer(self, chart_id: int, name: str, property_name: str, value: int | bool) -> bool: ...
    def set_string(self, chart_id: int, name: str, property_name: str, value: str) -> bool: ...
    def move(self, chart_id: int, name: str, index: int, time: datetime, price: float) -> bool: ...


def zone_color(priority: int) -> str:
    return "gold" if priority == 1 else "dodger_blue"


def marker_tooltip(marker: XauVisualMarker, digits: int) -> str:
    if marker.broker_time is None:
        return ""
    time_text = marker.broker_time.strftime("%Y.%m.%d %H:%M:%S")
    return (
        f"Time={time_text} | Zone={marker.zone_id} | Entry={marker.entry:.{digits}f} | "
        f"SL={marker.stop_loss:.{digits}f} | TP={marker.take_profit:.{digits}f} | Event={marker.event_id}"
    )


def draw_xau_zone(
    backend: ChartObjectBackend,
    chart_id: int,
    zone: XauZone,
    from_time: datetime,
    to_time: datetime,
) -> bool:
    if from_time is None or to_time is None or to_time <= from_time or zone.high < zone.low:
        return False

    name = f"XAU_ZONE_{zone.id}"
    if backend.find(chart_id, name) < 0 and not backend.create(chart_id, name, "RECTANGLE", from_time, zone.low):
        return False

    return (
        backend.set_integer(chart_id, name, "COLOR", zone_color(zone.priority))
        and backend.set_integer(chart_id, name, "FILL", True)
        and backend.set_integer(chart_id, name, "BACK", True)
        and backend.set_integer(chart_id, name, "SELECTABLE", False)
        and backend.set_integer(chart_id, name, "HIDDEN", True)
        and backend.move(chart_id, name, 0, from_time, zone.low)
        and backend.move(chart_id, name, 1, to_time, zone.high)
    )


def draw_xau_audit_marker(
    backend: ChartObjectBackend,
    chart_id: int,
    marker: XauVisualMarker,
    digits: int,
) -> bool:
    if (
        marker.broker_time is None
        or marker.entry <= 0.0
        or not marker.event_id
        or not marker.zone_id
        or not marker.label
    ):
        return False

    name = f"XAU_EVENT_{marker.event_id}"
    if backend.find(chart_id, name) < 0 and not backend.create(
        chart_id,
        name,
        "TEXT",
        marker.broker_time,
        marker.entry,
    ):
        return False

    return (
        backend.set_string(chart_id, name, "TEXT", marker.label)
        and backend.set_string(chart_id, name, "TOOLTIP", marker_tooltip(marker, digits))
        and backend.set_integer(chart_id, name, "COLOR", zone_color(marker.zone_priority))
        and backend.set_integer(chart_id, name, "ANCHOR", 0)
        and backend.set_integer(chart_id, name, "SELECTABLE", False)
        and backend.set_integer(chart_id, name, "HIDDEN", True)
        and backend.move(chart_id, name, 0, marker.broker_time, marker.entry)
    )
