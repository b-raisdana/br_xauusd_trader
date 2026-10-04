"""Batched greedy pullback-window selection and penetration latches."""

import pandas as pd

from br_pre_commit import pandera_validate
from domain.xau_usd.enums import XauDirection, XauSignalFamily
from domain.xau_usd.models import XauZone
from helper.importer import pt

from .columnar_helpers import _signal_rows, _take
from .domain.columnar import ActiveWindows, ColumnarMarket


def _select_windows(events: pd.DataFrame, width: int) -> pd.DataFrame:
    """Find the greedy successor chain with batched binary lifting, O(events log events)."""
    if events.empty:
        return events
    keys = ["event_day", "zone_id", "direction"]
    events = events.reset_index(drop=True)
    events["node"] = events.index
    targets = events[[*keys, "node", "born_bar"]].assign(target=events.born_bar + width)
    successors = (
        pd.merge_asof(
            targets.sort_values("target"),
            events[[*keys, "born_bar", "node"]].rename(columns={"node": "successor"}).sort_values("born_bar"),
            left_on="target",
            right_on="born_bar",
            by=keys,
            direction="forward",
        )
        .set_index("node")
        .successor.reindex(events.index)
        .fillna(-1)
        .astype("int64")
    )
    jumps = [successors]
    distance = successors.ge(0).astype("int64")
    pointer = successors
    # Each round doubles the covered distance for every event simultaneously.
    for _ in range(len(events).bit_length()):
        distance = distance + _take(distance, pointer).fillna(0).astype("int64")
        pointer = _take(pointer, pointer).fillna(-1).astype("int64")
        jumps.append(pointer)
    roots = events.groupby(keys, sort=False).node.transform("first")
    steps = _take(distance, roots) - distance
    reached = roots
    for bit, jump in enumerate(jumps):
        reached = reached.where((steps // (1 << bit)) % 2 == 0, _take(jump, reached).fillna(-1).astype("int64"))
    return events.loc[steps.ge(0) & reached.eq(events.node)].drop(columns="node")


@pandera_validate(allow_pandas_dataframe=True)
def _windows(
    data: pd.DataFrame,
    bars: pd.DataFrame,
    state: pd.DataFrame,
    events: pd.DataFrame,
    market: ColumnarMarket,
    zones: list[XauZone],
    signals: list[pd.DataFrame],
) -> tuple[pd.DataFrame, pt.DataFrame[ActiveWindows], int]:
    width = market.inputs.window_bars
    candidates = events.loc[events.allowed & market.inputs.enable_pullback].rename(columns={"bar_number": "born_bar"})
    existing = market.windows
    if not existing.empty:
        active = existing.loc[existing.active]
        expiry = (
            active.groupby(["event_day", "zone_id", "direction"], sort=False).expiry_bar.max().rename("existing_expiry")
        )
        candidates = candidates.join(expiry, on=["event_day", "zone_id", "direction"])
        candidates = candidates.loc[candidates.born_bar.ge(candidates.existing_expiry.fillna(-1))].drop(
            columns="existing_expiry"
        )
    selected = _select_windows(candidates, width)
    selected["parent_breakout_id"] = selected.candidate_id
    selected["broker_day"] = selected.event_day
    selected["breakout_bar_time"] = pd.to_datetime(selected.bar_id, utc=True, format="mixed").astype(
        "datetime64[ns, UTC]"
    )
    selected["active"] = selected.event_day.eq(selected.day)
    selected["bar_offset"] = 1
    selected["penetration_latched"] = False
    selected["expiry_bar"] = selected.born_bar + width
    next_window_id = market.next_window_id + len(selected)
    selected["window_id"] = pd.RangeIndex(market.next_window_id, next_window_id)
    selected["stream_tick"] = _take(data.stream_tick, selected.position)
    all_windows = (
        pd.concat([existing, selected], ignore_index=True) if not existing.empty else selected.reset_index(drop=True)
    )
    state["pullback_active"] = False
    state["pullback_bar_offset"] = 0
    state["pullback_penetration_latched"] = False
    latches = []
    bar_ids = data.bar_time.astype("str")
    for zone in zones:
        for direction in XauDirection:
            prefix = f"pullback:{zone.id}:{direction.value}"
            state[f"{prefix}:parent"] = ""
            state[f"{prefix}:offset"] = 0
            if all_windows.empty:
                continue
            windows = all_windows.loc[
                all_windows.active & all_windows.zone_id.eq(zone.id) & all_windows.direction.eq(int(direction))
            ]
            if windows.empty:
                continue
            matched = pd.merge_asof(
                data[["bar_number", "day"]].assign(position=data.index),
                windows[
                    [
                        "born_bar",
                        "event_day",
                        "window_id",
                        "parent_breakout_id",
                        "zone_low",
                        "zone_high",
                        "penetration_latched",
                    ]
                ],
                left_on="bar_number",
                right_on="born_bar",
                left_by="day",
                right_by="event_day",
                direction="backward",
            ).set_index("position")
            offset = data.bar_number - matched.born_bar + 1
            active_mask = offset.between(1, width)
            buy = direction == XauDirection.BUY
            hit = (
                data.bid.le(matched.zone_high - market.inputs.penetration)
                if buy
                else data.bid.ge(matched.zone_low + market.inputs.penetration)
            )
            latched = (hit & active_mask).groupby(matched.window_id, sort=False).cummax().fillna(False).astype(bool)
            latched |= matched.penetration_latched.fillna(False).astype(bool)
            latched &= active_mask
            state["pullback_active"] |= active_mask
            state["pullback_bar_offset"] = state.pullback_bar_offset.where(
                state.pullback_bar_offset.ge(offset.where(active_mask, 0)), offset.where(active_mask, 0)
            ).astype("int64")
            state["pullback_penetration_latched"] |= latched
            state[f"{prefix}:parent"] = matched.parent_breakout_id.where(active_mask, "").astype("str")
            state[f"{prefix}:offset"] = offset.where(active_mask, 0).astype("int64")
            latches.append(latched.groupby(matched.window_id, sort=False).max())
            if latched.any():
                signals.append(
                    _signal_rows(
                        data,
                        latched,
                        zone.id,
                        int(direction),
                        int(XauSignalFamily.PULLBACK),
                        matched.parent_breakout_id + ":PB",
                        bar_ids,
                        matched.zone_high if buy else matched.zone_low,
                        matched.parent_breakout_id,
                    ).assign(_signal_order=matched.window_id.loc[latched])
                )
    # Opening snapshots are taken after the opening tick's penetration check.
    first_bid = _take(data.bid, selected.position)
    selected["penetration_latched"] = selected.active & (
        (selected.direction.eq(int(XauDirection.BUY)) & first_bid.le(selected.zone_high - market.inputs.penetration))
        | (selected.direction.eq(int(XauDirection.SELL)) & first_bid.ge(selected.zone_low + market.inputs.penetration))
    )
    selected["_position"] = selected.position
    if not all_windows.empty:
        if latches:
            latch = pd.concat(latches).groupby(level=0).max()
            all_windows["penetration_latched"] |= _take(latch, all_windows.window_id).fillna(False).astype(bool)
        day_end = bars.groupby("day", sort=False).bar_number.max() + 1
        day_end.loc[data.day.iloc[-1]] = int(data.bar_number.iloc[-1])
        stop_bar = _take(day_end, all_windows.event_day).fillna(int(data.bar_number.iloc[0]))
        all_windows["bar_offset"] = all_windows.bar_offset.where(
            ~all_windows.active, (stop_bar - all_windows.born_bar + 1).clip(upper=width)
        ).astype("int64")
        all_windows["active"] &= all_windows.event_day.eq(data.day.iloc[-1]) & all_windows.expiry_bar.gt(
            int(data.bar_number.iloc[-1])
        )
    terminal = all_windows.loc[all_windows.active, list(ActiveWindows.to_schema().columns)].reset_index(drop=True)
    return selected, ActiveWindows.validate(terminal, lazy=True), next_window_id
