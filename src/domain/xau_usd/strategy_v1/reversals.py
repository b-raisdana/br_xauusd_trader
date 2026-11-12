from datetime import UTC, datetime

import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.common.ohlcv import MultiTimeframeTicksSpreadOHLC
from domain.schemas.tick import Tick
from domain.schemas.xau_usd.strategy_v1 import SignalCandidateRows
from domain.schemas.xau_usd.zones import StrategyZoneRows
from helper.importer import pt

from ._time_index import utc_times
from .config import StrategyV1Config
from .signals import indicator_confirmations
from .trend import m15_trend
from .zones import unique_zone_membership


@pandera_validate
def reversal_signal_candidates(
    ticks: pt.DataFrame[Tick],
    candles: pt.DataFrame[MultiTimeframeTicksSpreadOHLC],
    zones: pt.DataFrame[StrategyZoneRows],
    startup_time: datetime,
    as_of: datetime,
    config: StrategyV1Config,
) -> pt.DataFrame[SignalCandidateRows]:
    _require_utc(startup_time, "startup_time")
    _require_utc(as_of, "as_of")
    if startup_time > as_of:
        raise ValueError("startup_time must not be after as_of")

    precise_times = ticks.index.get_level_values("precise_time")
    if precise_times.tz is None or str(precise_times.tz) != "UTC":
        raise ValueError("tick precise_time must be UTC-aware")
    if not precise_times.is_monotonic_increasing:
        raise ValueError("tick precise_time values must be ordered")

    trading_day = pd.Timestamp(startup_time.date(), tz=UTC)
    daily_ticks = ticks.loc[(precise_times <= as_of) & (precise_times.floor("D") == trading_day)]
    current_times = daily_ticks.index.get_level_values("precise_time")
    if daily_ticks.empty:
        return _empty_signals()
    zone_dates = zones.index.get_level_values("date")
    day_zones = zones.loc[zone_dates == pd.Timestamp(startup_time.date(), tz=UTC)]
    if day_zones.empty:
        return _empty_signals()
    zone_ids = day_zones.index.get_level_values("zone_id")
    if not zone_ids.is_unique:
        raise ValueError("zone_id values must be unique within the signal day")

    timeframe_names = candles.index.get_level_values("timeframe").astype("string")
    m5 = candles.loc[timeframe_names.eq(f"{config.m5_timeframe_minutes}min")]
    m15 = candles.loc[timeframe_names.eq(f"{config.m15_timeframe_minutes}min")]
    if m5.empty or m15.empty:
        raise ValueError("signal calculation requires both M5 and M15 candles")

    trend = m15_trend(m15[["high", "low"]], config)
    m15_times = utc_times(trend.index)
    trend_by_close = pd.Series(
        trend["trend"].array,
        index=m15_times + pd.Timedelta(minutes=config.m15_timeframe_minutes),
    )
    trend_at_tick = trend_by_close.reindex(current_times, method="ffill")

    closes = m5["close"]
    confirmations = indicator_confirmations(closes, config)
    m5_times = utc_times(confirmations.index)
    confirmation_by_close = confirmations.copy()
    confirmation_by_close.index = m5_times + pd.Timedelta(minutes=config.m5_timeframe_minutes)
    confirmation_at_tick = confirmation_by_close.reindex(current_times, method="ffill")
    invalidations = _zone_exit_rows(
        close_times=m5_times + pd.Timedelta(minutes=config.m5_timeframe_minutes),
        close_prices=closes.reset_index(drop=True),
        zone_bounds=day_zones.reset_index()[["zone_id", "lower", "upper"]],
        buffer_usd=config.reversal_exit_buffer_usd,
    )

    buy_zone = unique_zone_membership(daily_ticks["ask"], day_zones).reset_index(drop=True)
    sell_zone = unique_zone_membership(daily_ticks["bid"], day_zones).reset_index(drop=True)
    tick_frame = pd.DataFrame(
        {
            "time": current_times,
            "bid": daily_ticks["bid"].reset_index(drop=True),
            "ask": daily_ticks["ask"].reset_index(drop=True),
            "buy_zone_id": buy_zone,
            "sell_zone_id": sell_zone,
            "trend": trend_at_tick.reset_index(drop=True),
            "rsi_buy_ready": confirmation_at_tick["rsi_buy_ready"].reset_index(drop=True),
            "rsi_sell_ready": confirmation_at_tick["rsi_sell_ready"].reset_index(drop=True),
            "macd_buy_confirmed": confirmation_at_tick["macd_buy_confirmed"].reset_index(drop=True),
            "macd_sell_confirmed": confirmation_at_tick["macd_sell_confirmed"].reset_index(drop=True),
        },
    )
    prior_buy_zone = tick_frame["buy_zone_id"].shift()
    prior_sell_zone = tick_frame["sell_zone_id"].shift()
    prior_ask = tick_frame["ask"].shift()
    prior_bid = tick_frame["bid"].shift()
    prior_time = tick_frame["time"].shift()
    fresh_tick = tick_frame["time"].gt(startup_time) & prior_time.ge(startup_time)

    buy_entry = (
        tick_frame["buy_zone_id"].notna()
        & tick_frame["buy_zone_id"].ne(prior_buy_zone)
        & tick_frame["ask"].lt(prior_ask)
        & tick_frame["trend"].eq(-1)
        & tick_frame["rsi_buy_ready"]
        & fresh_tick
    )
    sell_entry = (
        tick_frame["sell_zone_id"].notna()
        & tick_frame["sell_zone_id"].ne(prior_sell_zone)
        & tick_frame["bid"].gt(prior_bid)
        & tick_frame["trend"].eq(1)
        & tick_frame["rsi_sell_ready"]
        & fresh_tick
    )

    buy_setups = _setup_rows(tick_frame, buy_entry, "buy", config)
    sell_setups = _setup_rows(tick_frame, sell_entry, "sell", config)
    buy_results = _confirm_setups(
        tick_frame.loc[tick_frame["macd_buy_confirmed"], ["time", "ask", "buy_zone_id"]].rename(
            columns={"time": "confirmation_time", "ask": "entry_reference", "buy_zone_id": "zone_id"},
        ),
        buy_setups,
        invalidations,
    )
    sell_results = _confirm_setups(
        tick_frame.loc[tick_frame["macd_sell_confirmed"], ["time", "bid", "sell_zone_id"]].rename(
            columns={"time": "confirmation_time", "bid": "entry_reference", "sell_zone_id": "zone_id"},
        ),
        sell_setups,
        invalidations,
    )
    return _combine_results(buy_results, sell_results)


def _setup_rows(
    ticks: pd.DataFrame,
    selected: pd.Series,
    direction: str,
    config: StrategyV1Config,
) -> pd.DataFrame:
    zone_column = "buy_zone_id" if direction == "buy" else "sell_zone_id"
    setups = ticks.loc[selected, ["time", zone_column]].rename(columns={"time": "setup_time", zone_column: "zone_id"})
    if setups.empty:
        return pd.DataFrame(columns=["setup_time", "zone_id", "setup_id", "expires_at"])
    candle_open = setups["setup_time"].dt.floor(pd.Timedelta(minutes=config.m5_timeframe_minutes))
    setups["expires_at"] = candle_open + pd.Timedelta(
        minutes=config.confirmation_window_m5 * config.m5_timeframe_minutes,
    )
    setups["setup_id"] = (
        setups["setup_time"].astype("string") + "|" + setups["zone_id"].astype("string") + f"|{direction}"
    )
    return setups.sort_values("setup_time", kind="stable")


def _confirm_setups(
    confirmations: pd.DataFrame,
    setups: pd.DataFrame,
    invalidations: pd.DataFrame,
) -> pd.DataFrame:
    if confirmations.empty or setups.empty:
        return pd.DataFrame(columns=["confirmation_time", "zone_id", "entry_reference", "setup_id", "expires_at"])
    matched = pd.merge_asof(
        confirmations.sort_values("confirmation_time", kind="stable"),
        setups.sort_values("setup_time", kind="stable"),
        left_on="confirmation_time",
        right_on="setup_time",
        by="zone_id",
        direction="backward",
        allow_exact_matches=True,
    )
    matched = pd.merge_asof(
        matched.sort_values("confirmation_time", kind="stable"),
        invalidations.sort_values("invalidation_time", kind="stable"),
        left_on="confirmation_time",
        right_on="invalidation_time",
        by="zone_id",
        direction="backward",
        allow_exact_matches=True,
    )
    valid = matched["setup_id"].notna() & matched["confirmation_time"].lt(matched["expires_at"])
    invalidated_after_setup = matched["invalidation_time"].gt(matched["setup_time"])
    valid &= ~invalidated_after_setup
    return matched.loc[valid].sort_values("confirmation_time", kind="stable").drop_duplicates("setup_id")


def _zone_exit_rows(
    *,
    close_times: pd.DatetimeIndex,
    close_prices: pd.Series,
    zone_bounds: pd.DataFrame,
    buffer_usd: float,
) -> pd.DataFrame:
    closed_bars = pd.DataFrame(
        {
            "invalidation_time": close_times,
            "close": close_prices,
            "join_key": 1,
        },
    )
    bounds = zone_bounds.assign(join_key=1)
    zone_closes = closed_bars.merge(bounds, on="join_key", how="inner", sort=False)
    outside = zone_closes["close"].lt(zone_closes["lower"] - buffer_usd) | zone_closes["close"].gt(
        zone_closes["upper"] + buffer_usd,
    )
    return zone_closes.loc[outside, ["invalidation_time", "zone_id"]].sort_values(
        "invalidation_time",
        kind="stable",
    )


def _combine_results(
    buys: pd.DataFrame,
    sells: pd.DataFrame,
) -> pt.DataFrame[SignalCandidateRows]:
    buy_rows = buys.assign(setup_type="reversal", direction="buy")
    sell_rows = sells.assign(setup_type="reversal", direction="sell")
    candidates = pd.concat([buy_rows, sell_rows], ignore_index=True)
    if candidates.empty:
        return _empty_signals()

    candidate_count_at_time = candidates.groupby("confirmation_time", sort=False)["setup_id"].transform("size")
    candidates = candidates.loc[candidate_count_at_time.eq(1)].copy()
    if candidates.empty:
        return _empty_signals()
    candidates["signal_id"] = candidates["setup_id"] + "|" + candidates["confirmation_time"].astype("string")
    candidates = candidates.set_index("confirmation_time").rename_axis("date")
    result = candidates[["signal_id", "setup_type", "direction", "zone_id", "entry_reference", "expires_at"]]
    result.index = result.index.astype("datetime64[ns, UTC]")
    return SignalCandidateRows.validate(result, lazy=True)


@pandera_validate
def _empty_signals() -> pt.DataFrame[SignalCandidateRows]:
    index = pd.DatetimeIndex([], tz="UTC", name="date").astype("datetime64[ns, UTC]")
    return pd.DataFrame(
        {
            "signal_id": pd.Series([], dtype="object"),
            "setup_type": pd.Series([], dtype="object"),
            "direction": pd.Series([], dtype="object"),
            "zone_id": pd.Series([], dtype="object"),
            "entry_reference": pd.Series([], dtype="float64"),
            "expires_at": pd.Series([], dtype="datetime64[ns, UTC]"),
        },
        index=index,
    )


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{name} must be UTC-aware")
