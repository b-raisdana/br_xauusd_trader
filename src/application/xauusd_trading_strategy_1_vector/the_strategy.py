from __future__ import annotations

import numpy as np
import pandas as pd
from br_py_log_n_profile import log_w, profile_it
from br_py_log_n_profile.do_log.log_it import NOT_TESTED
from numpy.typing import NDArray

from application.xauusd_trading_strategy_1_vector.columnar_process.__main__ import process_columns
from application.xauusd_trading_strategy_1_vector.config.trend_points import (
    TREND_SIDES,
    trend_columns,
    trend_point_count,
    trend_row_columns,
)
from application.xauusd_trading_strategy_1_vector.domain.execution_schema import (
    CandidateEvents,
    StreamEvents,
    ZoneEvents,
)
from application.xauusd_trading_strategy_1_vector.domain.schema import (
    HasDay,
    PerCandleState,
    PerTickState,
    StrategyCandles,
    VectorizedTick,
    trend_schema_columns,
)
from br_pre_commit import pandera_validate
from domain.schemas.tick import Tick
from domain.xau_usd.enums import XauTrend
from domain.xau_usd.models import XauZone
from helper.importer import pt
from infrastructure.result_processing.io import ResultFilesManifest

from .domain.columnar import ColumnarMarket, ColumnarResult
from .domain.replay import ReplayConfig
from .domain.robust import RobustInputs
from .engagement import update_zone_engagement
from .signals import generate_breakout_signals, generate_pullback_signals, generate_reversal_signals
from .trend import compute_bar_time, update_trend
from .vectorized_replay import VectorizedExecutionReplay
from .zone_cache import ZoneCache

_STATE_COLUMNS = frozenset(trend_schema_columns(PerTickState))


def _assert_state_columns(per_tick_state: pd.DataFrame) -> pd.DataFrame:
    """Cheap O(columns) contract guard replacing O(rows) schema validation.

    The per-tick state is assembled from known constants, so value-level checks
    cannot fail; only a missing, extra or renamed column can. The full
    `PerTickState` validation stays covered by the state contract tests.
    """
    if frozenset(per_tick_state.columns) != _STATE_COLUMNS:
        missing = _STATE_COLUMNS - set(per_tick_state.columns)
        extra = set(per_tick_state.columns) - _STATE_COLUMNS
        raise ValueError(
            f"Per-tick state columns violate the contract: missing={sorted(missing)} extra={sorted(extra)}"
        )
    return per_tick_state


class VectorizedXauUsdStrategy:
    """Signals-only native columns over persisted market artifacts."""

    def __init__(
        self, zone_cache: ZoneCache, execution: ReplayConfig | None = None, inputs: RobustInputs | None = None
    ) -> None:
        if execution is not None:
            raise ValueError(
                "VectorizedXauUsdStrategy runs in signals-only mode; execution replay is not supported here."
            )
        self._zone_cache = zone_cache
        self.execution = None
        self.inputs = inputs or RobustInputs()

    @profile_it
    @pandera_validate(dump_output=True)
    def process_tick_data(self, manifest: ResultFilesManifest) -> ResultFilesManifest:
        """Read daily market artifacts and persist validated calculation states.

        When execution config is provided, runs execution replay on the generated signals
        and persists order/position artifacts.
        """
        markets: dict[tuple[str, str], ColumnarMarket] = {}
        for day in manifest.successful_days("ticks"):
            ticks = manifest.read_daily_ticks(day)
            candles = manifest.read_daily_candles(day)
            results: list[ColumnarResult] = []
            candle_states: list[pt.DataFrame[PerCandleState]] = []

            broker_symbol: tuple[str, str]
            for broker_symbol, instrument_ticks in ticks.groupby(level=["broker", "symbol"], sort=False):
                if not instrument_ticks.index.get_level_values("precise_time").is_monotonic_increasing:
                    raise ValueError("Ticks must be chronological within each broker/symbol")
                broker_symbol_candles = candles.loc[
                    (candles.index.get_level_values("broker") == broker_symbol[0])
                    & (candles.index.get_level_values("symbol") == broker_symbol[1])
                ]
                if broker_symbol not in markets:
                    markets[broker_symbol] = ColumnarMarket(self.inputs)
                result = self.process_native_stream(instrument_ticks, broker_symbol_candles, markets[broker_symbol])
                results.append(result)
                candle_states.append(result.candles)
            if results:
                manifest.save_daily_signal_state(
                    day, pd.concat([result.ticks for result in results]).sort_index(kind="stable")
                )
                manifest.save_daily_signals(day, pd.concat([result.signals for result in results]))
                manifest.save_daily_windows(day, pd.concat([result.windows for result in results]))
                manifest.save_daily_candles_temp_state(day, pd.concat(candle_states).sort_index(kind="stable"))

                # Run execution replay if config provided
                if self.execution is not None:
                    self._run_execution_replay(manifest, day, ticks, results)

        manifest.wait_for_writes()
        return manifest

    def _run_execution_replay(
        self,
        manifest: ResultFilesManifest,
        day: str,
        ticks: pt.DataFrame[VectorizedTick],
        results: list[ColumnarResult],
    ) -> None:
        """Run vectorized execution replay on generated signals."""
        # Convert day string to datetime for manifest methods
        day_dt = pd.Timestamp(day).to_pydatetime()

        # Convert ticks to StreamEvents format
        streams_list = []
        for (broker, symbol), broker_ticks in ticks.groupby(level=["broker", "symbol"], sort=False):
            stream_id = f"{broker}_{symbol}"
            stream_ticks = broker_ticks.reset_index()
            stream_ticks["stream_id"] = stream_id
            stream_ticks["stream_tick"] = range(len(stream_ticks))
            streams_list.append(
                stream_ticks[
                    [
                        "stream_id",
                        "stream_tick",
                        "precise_time",
                        "broker_day",
                        "bar_time",
                        "bid",
                        "ask",
                    ]
                ]
            )
        streams = pd.concat(streams_list, ignore_index=True)
        streams = StreamEvents.validate(streams)

        # Convert zones to ZoneEvents format
        zones_list = []
        day_zones = self._zone_cache.get_zones_for_day(day)
        for zone in day_zones:
            zones_list.append(
                {
                    "zone_id": zone.id,
                    "broker_day": day,
                    "high": zone.high,
                    "low": zone.low,
                    "priority": zone.priority,
                }
            )
        zones = pd.DataFrame(zones_list)
        if not zones.empty:
            zones = ZoneEvents.validate(zones)

        # Convert signals to CandidateEvents format
        candidates_list = []
        for result in results:
            # Extract candidate signals from the signal state
            # For now, skip candidate extraction - will be implemented with signal integration
            log_w(f"Candidate extraction is not implemented. the result:{result}")
            pass
        candidates = pd.DataFrame(candidates_list)
        if not candidates.empty:
            candidates = CandidateEvents.validate(candidates)

        # Run vectorized replay
        replay = VectorizedExecutionReplay(self.execution)
        orders, fills, closes, positions, events = replay.run(streams, zones, candidates)

        # Persist execution artifacts
        manifest.save_daily_orders(day_dt, orders)
        manifest.save_daily_positions(day_dt, positions)

    @pandera_validate(dump_output=True)
    def process_native_stream(
        self,
        ticks: pt.DataFrame[VectorizedTick],
        candles: pt.DataFrame[StrategyCandles],
        market: ColumnarMarket,
    ) -> ColumnarResult:
        zones = self._zone_cache.get_zones_for_day(ticks.broker_day.iloc[0]) if not ticks.empty else []
        return process_columns(ticks, candles, market, zones)

    @staticmethod
    @profile_it
    @pandera_validate
    def add_bar_time_n_broker_day(
        tick_df: pt.DataFrame[Tick], broker_timezone: str = "UTC"
    ) -> pt.DataFrame[VectorizedTick]:
        datetime_index = tick_df.index.get_level_values("precise_time")

        tick_df["bar_time"] = compute_bar_time(datetime_index)
        tick_df["broker_day"] = (
            datetime_index.tz_convert(broker_timezone).tz_localize(None).normalize().tz_localize("UTC")
        )

        return tick_df

    @profile_it
    def _initialize_per_tick_temp_state(self, tick_df: pt.DataFrame[VectorizedTick]) -> pt.DataFrame[PerTickState]:
        """Initialize tick inputs, intermediate fields and output columns."""
        index = tick_df.index
        n = tick_df.shape[0]

        object_values = np.empty(n, dtype=object)
        empty_tuple = ()
        object_values.fill(empty_tuple)

        # Keep the exact intended output-column order.
        new_columns: dict[str, int | float | bool | str | None | NDArray[np.object_]] = {
            # Trend state columns
            "trend": XauTrend.NONE.value,
            "trend_count": 0,
            **dict.fromkeys(trend_row_columns(), 0.0),
            # Bar state columns
            "bar_open": 0.0,
            "bar_active": False,
            "day_active": False,
            # Zone engagement state
            "buy_engaged": False,
            "sell_engaged": False,
            # Signal generation state
            "breakout_sequence": 0,
            "attempted_bars": "",
            # Pullback window state
            "pullback_active": False,
            "pullback_bar_offset": 0,
            "pullback_penetration_latched": False,
            "pullback_sequence": 0,
            # Intermediate calculations
            "reference_high": 0.0,
            "reference_low": 0.0,
            "multi_zone_tick_gap": False,
            # Output
            "action": None,
            "mt5_state": "{}",
            # Daily/account state
            "daily_net_realized_pnl": float("nan"),
            "daily_gross_loss": float("nan"),
            "account_balance": float("nan"),
            "daily_loss_locked": False,
            "operational_locked": False,
            "execution_mode": "replay" if self.execution else "signals_only",
            "reversal_signals": object_values,
            "pullback_signals": object_values,
            "actions": object_values,
            "execution_events": object_values,
            "orders": object_values,
            "positions": object_values,
            "pullback_feedback": object_values,
            "entry_rejections": object_values,
            "pullback_windows_opened": object_values,
            "breakout_signals": object_values,
        }

        initialized = pd.DataFrame(new_columns, index=index)
        return _assert_state_columns(initialized)  # pd.concat([per_tick_state, initialized])

    @profile_it
    def _process_day_boundaries(self, per_tick_state: pt.DataFrame[PerTickState]) -> pt.DataFrame[PerTickState]:
        # Each daily partition is initialized independently before processing.
        _assert_state_columns(per_tick_state)
        per_tick_state["day_active"] = True
        return per_tick_state

    @profile_it
    @pandera_validate
    def _get_ticks_bar_ids(self, ticks: pt.DataFrame[VectorizedTick]) -> tuple[NDArray[np.int64], pt.Series[bool]]:
        day_changed = ticks["broker_day"].ne(ticks["broker_day"].shift())
        bar_changed = day_changed | ticks["bar_time"].ne(ticks["bar_time"].shift())
        bar_ids = bar_changed.cumsum().to_numpy() - 1

        return bar_ids, bar_changed

    @profile_it
    @pandera_validate
    def _process_bar_boundaries(
        self,
        ticks: pt.DataFrame[VectorizedTick],
        per_tick_state: pt.DataFrame[PerTickState],
        candle_15min_df: pt.DataFrame[StrategyCandles],
    ) -> tuple[pt.DataFrame[PerTickState], pt.DataFrame[PerCandleState]]:
        """Use observed bars only; completed ranges enter history at the next bar."""
        if ticks.empty:
            empty_candles = candle_15min_df.iloc[:0].copy()
            for column, field in trend_schema_columns().items():
                empty_candles[column] = pd.Series(index=empty_candles.index, dtype=str(field.dtype))
            return per_tick_state, PerCandleState.validate(empty_candles, lazy=True)

        bar_ids, bar_changed = self._get_ticks_bar_ids(ticks)

        candles = candle_15min_df.loc[candle_15min_df.index.get_level_values("timeframe") == "15min"]
        bar_times = candles.index.get_level_values("bar_time")
        if bar_times.duplicated().any():
            raise ValueError("M15 candles must be unique per broker/symbol/bar_time")
        observed = pd.DatetimeIndex(ticks.loc[bar_changed, "bar_time"])
        locations = bar_times.get_indexer(observed)
        if (locations < 0).any():
            raise ValueError("M15 candles must cover every observed tick bar")
        per_candle_state = candles.iloc[locations].copy()
        days = ticks.loc[bar_changed, "broker_day"].to_numpy()

        counts = per_candle_state.groupby(days, sort=False).cumcount().to_numpy()
        points = trend_point_count()
        available = np.minimum(counts, points)
        per_candle_state["trend_count"] = available
        per_tick_state["trend_count"] = available[bar_ids]

        # Gather only preceding bars. Unavailable bootstrap slots remain zero.
        slots = np.arange(points)
        positions = np.arange(len(per_candle_state))[:, None] - available[:, None] + slots
        valid = slots < available[:, None]

        # Pull high/low for valid slots, zero-pad missing
        high = np.where(valid, per_candle_state["high"].to_numpy()[positions.clip(0, len(per_candle_state) - 1)], 0.0)
        low = np.where(valid, per_candle_state["low"].to_numpy()[positions.clip(0, len(per_candle_state) - 1)], 0.0)
        for side, extrema in zip(TREND_SIDES, (high, low), strict=True):
            columns = trend_columns(side)
            per_candle_state[columns] = extrema
            # Broadcast back to original tick rows via bar_ids
            per_tick_state[columns] = extrema[bar_ids]
        per_tick_state["bar_open"] = per_candle_state["open"].to_numpy()[bar_ids]
        per_tick_state["bar_active"] = per_tick_state["day_active"]
        return per_tick_state, per_candle_state

    @profile_it
    @pandera_validate()
    def _process_tick_operations(
        self,
        ticks: pt.DataFrame[VectorizedTick],
        per_tick_state: pt.DataFrame[PerTickState],
    ) -> pt.DataFrame[PerTickState]:
        zones = self._zone_cache.get_zones_for_day(ticks["broker_day"].iloc[0])
        per_tick_state = update_trend(ticks, per_tick_state)
        per_tick_state = update_zone_engagement(ticks, per_tick_state, zones)
        per_tick_state = generate_breakout_signals(ticks, per_tick_state, zones)
        per_tick_state = generate_reversal_signals(ticks, per_tick_state, zones)
        if self.execution is None:
            per_tick_state = generate_pullback_signals(ticks, per_tick_state)

        return per_tick_state

    @profile_it
    @pandera_validate(allow_pandas_dataframe=True)
    def _get_zones_for_group(self, ticks: pt.DataFrame[HasDay]) -> list[XauZone]:
        log_w(NOT_TESTED)
        zones = self._zone_cache.get_zones_for_day(ticks["broker_day"].iloc[0])
        return zones
