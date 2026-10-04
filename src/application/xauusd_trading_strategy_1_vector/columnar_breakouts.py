"""Closed-bar breakout events and daily sequence numbering."""

import pandas as pd

from domain.xau_usd.enums import XauDirection
from domain.xau_usd.models import XauDailyZoneSignalState, XauZone

from .domain.columnar import ColumnarMarket
from .domain.robust import pullback_allowed


def _breakouts(
    data: pd.DataFrame, bars: pd.DataFrame, state: pd.DataFrame, market: ColumnarMarket, zones: list[XauZone]
) -> pd.DataFrame:
    parts = []
    old = {s.zone.id: s for s in market.zones}
    previous_trend = state.trend.groupby(data.bar_number, sort=False).last().shift().fillna(market.trend)
    previous_day = bars.day.shift().fillna(market.broker_day)
    first_changed = bool(bars.changed.iloc[0])
    for order, zone in enumerate(zones):
        prior = old.get(zone.id, XauDailyZoneSignalState(zone))
        for direction in XauDirection:
            buy = direction == XauDirection.BUY
            engaged = state[f"{'buy' if buy else 'sell'}_engaged:{zone.id}"]
            previous_engaged = engaged.groupby(data.bar_number, sort=False).last().shift()
            previous_engaged.iloc[0] = prior.buy_engaged if buy else prior.sell_engaged
            eligible = previous_engaged.fillna(False).astype(bool) & previous_trend.eq(1 if buy else -1)
            eligible &= (
                bars.previous_close.gt(zone.high + market.inputs.breakout_buffer)
                if buy
                else bars.previous_close.lt(zone.low - market.inputs.breakout_buffer)
            )
            eligible.iloc[0] &= market.bar is not None and first_changed and bars.day.iloc[0] == market.broker_day
            event = bars.loc[eligible, ["position", "day", "bar_number"]]
            if event.empty:
                continue
            event["event_day"] = previous_day.loc[eligible]
            event["bar_id"] = bars.bar_time.shift().loc[eligible].astype("str")
            if eligible.iloc[0]:
                event.loc[event.index[0], "bar_id"] = str(market.bar)
            event["entry_price"] = bars.previous_close.loc[eligible]
            event["zone_id"] = zone.id
            event["zone_low"] = float(zone.low)
            event["zone_high"] = float(zone.high)
            event["priority"] = zone.priority
            event["direction"] = int(direction)
            event["zone_order"] = order
            fresh_allowed = pullback_allowed(zones, XauDailyZoneSignalState(zone), buy, market.inputs)
            old_allowed = pullback_allowed([s.zone for s in market.zones], prior, buy, market.inputs)
            event["allowed"] = fresh_allowed
            event.loc[event.event_day.eq(market.broker_day), "allowed"] = old_allowed
            parts.append(event)
    # The outgoing day is evaluated before the new day's zones replace it.
    if market.bar is not None and first_changed and bars.day.iloc[0] != market.broker_day:
        for order, prior in enumerate(market.zones):
            zone = prior.zone
            close = float(bars.previous_close.iloc[0])
            buy = prior.buy_engaged and market.trend == 1 and close > zone.high + market.inputs.breakout_buffer
            sell = prior.sell_engaged and market.trend == -1 and close < zone.low - market.inputs.breakout_buffer
            if buy or sell:
                parts.append(
                    pd.DataFrame(
                        {
                            "position": [int(bars.position.iloc[0])],
                            "day": [bars.day.iloc[0]],
                            "bar_number": [int(bars.bar_number.iloc[0])],
                            "event_day": [market.broker_day],
                            "bar_id": [str(market.bar)],
                            "entry_price": [close],
                            "zone_id": [zone.id],
                            "zone_low": [float(zone.low)],
                            "zone_high": [float(zone.high)],
                            "priority": [zone.priority],
                            "direction": [int(XauDirection.BUY if buy else XauDirection.SELL)],
                            "zone_order": [order],
                            "allowed": [pullback_allowed([s.zone for s in market.zones], prior, buy, market.inputs)],
                        }
                    )
                )
    columns = {
        "position": "int64",
        "day": "str",
        "bar_number": "int64",
        "event_day": "str",
        "bar_id": "str",
        "entry_price": "float64",
        "zone_id": "str",
        "zone_low": "float64",
        "zone_high": "float64",
        "priority": "int64",
        "direction": "int64",
        "zone_order": "int64",
        "allowed": "bool",
    }
    events = (
        pd.concat(parts).sort_values(["position", "zone_order"], kind="stable").reset_index(drop=True)
        if parts
        else pd.DataFrame({c: pd.Series(dtype=t) for c, t in columns.items()})
    )
    sequence = events.groupby("event_day", sort=False).cumcount() + 1
    sequence += events.event_day.eq(market.broker_day).astype("int64") * market.breakout_sequence
    events["candidate_id"] = "BO#" + sequence.astype("str").str.zfill(2)
    return events
