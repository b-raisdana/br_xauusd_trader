"""Signals-only market transitions expressed as whole-stream pandas operations."""

from copy import deepcopy

import pandas as pd
from br_py_log_n_profile import log_e

from application.xauusd_trading_strategy_1_vector.columnar_process.breakouts import _breakouts
from application.xauusd_trading_strategy_1_vector.columnar_process.helpers import _signal_rows, _take, empty_table
from application.xauusd_trading_strategy_1_vector.columnar_process.windows import _windows
from application.xauusd_trading_strategy_1_vector.domain.columnar import (
    ColumnarMarket,
    ColumnarResult,
    SignalTable,
    SignalTickState,
    WindowTable,
)
from application.xauusd_trading_strategy_1_vector.domain.schema import PerCandleState, StrategyCandles, VectorizedTick
from br_pre_commit import pandera_validate
from domain.xau_usd.enums import XauDirection, XauSignalFamily
from domain.xau_usd.models import XauDailyZoneSignalState, XauZone
from helper.importer import pt


@pandera_validate
def process_columns(
    ticks: pt.DataFrame[VectorizedTick],
    candles: pt.DataFrame[StrategyCandles],
    market: ColumnarMarket,
    zones: list[XauZone],
) -> ColumnarResult:
    precise = ticks.index.get_level_values("precise_time")
    if not precise.is_monotonic_increasing or not ticks.bar_time.is_monotonic_increasing:
        log_e("Ticks and bar times must be chronological within each broker/symbol")
        raise ValueError("Ticks and bar times must be chronological within each broker/symbol")
    if len(ticks.index.droplevel(["date", "precise_time"]).unique()) > 1:
        log_e("Native stream must contain exactly one broker/symbol")
        raise ValueError("Native stream must contain exactly one broker/symbol")
    candles = candles.loc[candles.index.get_level_values("timeframe") == "15min"].sort_index(level="bar_time")
    candle_times = candles.index.get_level_values("bar_time")
    if candle_times.duplicated().any():
        log_e("M15 candles must be unique per broker/symbol/bar_time")
        raise ValueError("M15 candles must be unique per broker/symbol/bar_time")
    locations = candle_times.get_indexer(ticks.bar_time)
    if (locations < 0).any():
        log_e("M15 candles must cover every observed tick bar")
        raise ValueError("M15 candles must cover every observed tick bar")
    if (locations < 3).any():
        log_e("MT5 startup requires three native closed M15 candles")
        raise ValueError("MT5 startup requires three native closed M15 candles")
    observed = pd.unique(locations)
    per_candle = candles.iloc[observed]
    per_candle["trend_count"] = 3
    reference = pd.DataFrame(index=candle_times)
    for slot in range(3):
        for side in ("high", "low"):
            column = f"trend_{side}_{slot}"
            closed = candles[side].shift(3 - slot)
            per_candle[column] = closed.iloc[observed]
            reference[column] = closed.array
    if ticks.empty:
        state = empty_table(SignalTickState, ticks.index)
        for column in reference:
            state[column] = pd.Series(index=ticks.index, dtype="float64")
        return ColumnarResult(
            SignalTickState.validate(state, lazy=True),
            PerCandleState.validate(per_candle, lazy=True),
            SignalTable.validate(empty_table(SignalTable, ticks.index), lazy=True),
            WindowTable.validate(empty_table(WindowTable, ticks.index), lazy=True),
        )
    if (
        market.last_time is not None
        and precise[0] < market.last_time
        or market.bar is not None
        and ticks.bar_time.iloc[0] < market.bar
    ):
        log_e("Native stream cannot resume before its current tick/bar")
        raise ValueError("Native stream cannot resume before its current tick/bar")
    data = ticks[["bid", "ask", "bar_time"]].reset_index(drop=True)
    data["day"] = ticks.broker_day.dt.strftime("%Y-%m-%d").array
    data["signal_time"] = pd.Series(precise, index=data.index)
    data["stream_tick"] = pd.RangeIndex(market.processed_ticks, market.processed_ticks + len(ticks))
    changes = data.bar_time.ne(data.bar_time.shift())
    changes.iloc[0] = market.bar != data.bar_time.iloc[0]
    data["bar_number"] = changes.cumsum() + market.bar_number
    bars = (
        data.assign(position=data.index)
        .groupby("bar_number", sort=False)
        .agg(position=("position", "first"), day=("day", "first"), bar_time=("bar_time", "first"))
    )
    bars["bar_number"] = bars.index
    bars["changed"] = _take(changes, bars.position)
    bars["previous_close"] = candles.close.shift().set_axis(candle_times).reindex(bars.bar_time).set_axis(bars.index)
    data["day"] = _take(bars.day, data.bar_number)
    state = reference.reindex(data.bar_time).set_axis(data.index)
    if not changes.iloc[0]:
        for column, value in market.references.items():
            state.loc[data.bar_number.eq(market.bar_number), column] = value
    state["reference_high"] = state[[f"trend_high_{slot}" for slot in range(3)]].max(axis=1)
    state["reference_low"] = state[[f"trend_low_{slot}" for slot in range(3)]].min(axis=1)
    state["stream_tick"] = data.stream_tick
    state["trend"] = (
        pd.Series(float("nan"), index=data.index)
        .mask(data.bid.lt(state.reference_low), -1)
        .mask(data.bid.gt(state.reference_high), 1)
        .ffill()
        .fillna(market.trend)
        .astype("int64")
    )
    state["trend_count"] = 3
    state["bar_open"] = candles.open.set_axis(candle_times).reindex(data.bar_time).set_axis(data.index)
    state["bar_active"] = True
    state["day_active"] = bool(zones)
    previous = data.bid.shift()
    previous.iloc[0] = market.previous_bid if market.bar is not None else data.bid.iloc[0]
    crossings = pd.Series(0, index=data.index, dtype="int64")
    for zone in zones:
        crossings += (previous.lt(zone.low) & data.bid.ge(zone.low)) | (previous.gt(zone.high) & data.bid.le(zone.high))
    multi = crossings.ge(2)
    state["multi_zone_tick_gap"] = multi
    state["buy_engaged"] = False
    state["sell_engaged"] = False
    signals = []
    old = {s.zone.id: s for s in market.zones}
    final_zones = []
    bar_ids = data.bar_time.astype("str")
    for zone in zones:
        prior = old.get(zone.id, XauDailyZoneSignalState(zone))
        current = deepcopy(prior) if data.day.iloc[-1] == market.broker_day else XauDailyZoneSignalState(deepcopy(zone))
        inside = multi & data.bid.between(zone.low, zone.high)
        up = previous.lt(zone.low) & data.bid.ge(zone.low)
        down = previous.gt(zone.high) & data.bid.le(zone.high)
        opening = state.bar_open.between(zone.low, zone.high)
        for direction in XauDirection:
            buy = direction == XauDirection.BUY
            column = f"{'buy' if buy else 'sell'}_engaged:{zone.id}"
            baseline = opening.copy(deep=False)
            if not changes.iloc[0]:
                baseline = baseline.mask(
                    data.bar_number.eq(market.bar_number), prior.buy_engaged if buy else prior.sell_engaged
                )
            engaged = (((up if buy else down) & ~multi) | inside).groupby(
                data.bar_number, sort=False
            ).cummax() | baseline
            state[column] = engaged
            state["buy_engaged" if buy else "sell_engaged"] |= engaged
            if buy:
                current.buy_engaged = bool(engaged.iloc[-1])
            else:
                current.sell_engaged = bool(engaged.iloc[-1])
            reversal_slot = "last_reversal_buy_signal_bar" if buy else "last_reversal_sell_signal_bar"
            eligible = ~multi & ((down & state.trend.eq(-1)) if buy else (up & state.trend.eq(1)))
            mask = eligible & eligible.groupby(data.bar_number, sort=False).cumsum().eq(1)
            if getattr(prior, reversal_slot) == data.bar_time.iloc[0]:
                mask &= data.bar_number.ne(market.bar_number)
            final = mask & data.day.eq(data.day.iloc[-1])
            if final.any():
                setattr(current, reversal_slot, data.loc[final, "bar_time"].iloc[-1])
            if mask.any():
                signals.append(
                    _signal_rows(
                        data,
                        mask,
                        zone.id,
                        int(direction),
                        int(XauSignalFamily.REVERSAL),
                        bar_ids + f":R:{zone.id}:{direction.value}",
                        bar_ids,
                        data.ask if buy else data.bid,
                    )
                )
        final_zones.append(current)
    events = _breakouts(data, bars, state, market, zones)
    counts = (
        events.loc[events.day.eq(events.event_day)]
        .groupby("position", sort=False)
        .size()
        .reindex(data.index, fill_value=0)
    )
    state["breakout_sequence"] = counts.groupby(data.day, sort=False).cumsum()
    state["breakout_sequence"] += data.day.eq(market.broker_day).astype("int64") * market.breakout_sequence
    if not events.empty:
        emitted = data.loc[events.position, ["stream_tick", "signal_time"]].reset_index(drop=True)
        for column in ("candidate_id", "bar_id", "zone_id", "direction", "entry_price"):
            emitted[column] = events[column].array
        emitted["parent_breakout_id"] = ""
        emitted["family"] = int(XauSignalFamily.BREAKOUT)
        emitted["order_type"] = 0
        emitted["_position"] = events.position.array
        signals.append(emitted)
    openings, terminal_windows, next_window_id = _windows(data, bars, state, events, market, zones, signals)
    signal_table = (
        pd.concat(signals, ignore_index=True).sort_values(["stream_tick", "family"], kind="stable")
        if signals
        else empty_table(SignalTable, ticks.index)
    )
    for table in (signal_table, openings):
        if "_position" in table:
            positions = table.pop("_position")
            table.index = ticks.index.take(positions)
    state.index = ticks.index
    if "_signal_order" in signal_table:
        signal_table["_signal_order"] = signal_table["_signal_order"].fillna(0)
        signal_table = signal_table.sort_values(["stream_tick", "family", "_signal_order"], kind="stable")
    signal_table = signal_table[list(SignalTable.to_schema().columns)]
    openings = (
        openings[list(WindowTable.to_schema().columns)] if not openings.empty else empty_table(WindowTable, ticks.index)
    )
    result = ColumnarResult(
        SignalTickState.validate(state, lazy=True),
        PerCandleState.validate(per_candle, lazy=True),
        SignalTable.validate(signal_table, lazy=True),
        WindowTable.validate(openings, lazy=True),
    )
    market.zones = final_zones
    market.windows = terminal_windows
    market.next_window_id = next_window_id
    market.bar = data.bar_time.iloc[-1]
    market.broker_day = data.day.iloc[-1]
    market.bar_number = int(data.bar_number.iloc[-1])
    if changes.any():
        market.bar_open = float(state.bar_open.iloc[-1])
    market.previous_bid = float(data.bid.iloc[-1])
    market.trend = int(state.trend.iloc[-1])
    market.breakout_sequence = int(state.breakout_sequence.iloc[-1])
    market.processed_ticks += len(ticks)
    market.last_time = precise[-1]
    market.references = {column: float(state[column].iloc[-1]) for column in reference}
    return result
