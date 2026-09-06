"""Normalize exported MT5 UTC ticks into explicit Broker-time M15 replay bars."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from xauusd.replay import ReplayBar, ReplayTick
from xauusd.trend import Candle
from xauusd.zones import price


def load_mt5_tick_bars(path: Path, *, broker_utc_offset: timedelta) -> tuple[ReplayBar, ...]:
    if abs(broker_utc_offset) > timedelta(hours=14):
        raise ValueError("Broker UTC offset is outside the supported range")
    if broker_utc_offset.total_seconds() % 60:
        raise ValueError("Broker UTC offset must use whole minutes")
    broker_zone = timezone(broker_utc_offset)
    grouped: dict[datetime, list[ReplayTick]] = defaultdict(list)

    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not {"time_msc", "bid"}.issubset(reader.fieldnames or ()):
            raise ValueError("MT5 tick CSV requires time_msc and bid columns")
        previous_msc: int | None = None
        for line_number, row in enumerate(reader, start=2):
            try:
                time_msc = int(row["time_msc"])
                bid = price(row["bid"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid MT5 tick row {line_number}") from exc
            if previous_msc is not None and time_msc < previous_msc:
                raise ValueError(f"MT5 tick time moves backward at row {line_number}")
            previous_msc = time_msc
            utc_time = datetime.fromtimestamp(time_msc / 1000, tz=timezone.utc)
            broker_time = utc_time.astimezone(broker_zone).replace(tzinfo=None)
            bar_open = broker_time.replace(
                minute=(broker_time.minute // 15) * 15, second=0, microsecond=0
            )
            grouped[bar_open].append(ReplayTick(broker_time=broker_time, bid=bid))

    bars: list[ReplayBar] = []
    for bar_open in sorted(grouped):
        ticks = tuple(grouped[bar_open])
        bids = tuple(tick.bid for tick in ticks)
        candle = Candle.from_values(
            broker_day=bar_open.date(),
            open=bids[0],
            high=max(bids),
            low=min(bids),
            close=bids[-1],
        )
        bars.append(
            ReplayBar(
                bar_id=bar_open.isoformat(timespec="minutes"),
                open_time=bar_open,
                close_time=bar_open + timedelta(minutes=15),
                open_bid=bids[0],
                candle=candle,
                ticks=ticks,
            )
        )
    return tuple(bars)
