import base64
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
import pytz
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_PATH = Path(__file__).resolve().parent.parent.parent


class Config(BaseSettings):
    """Runtime settings. Any field can be overridden via a `DLF_<FIELD_NAME>` env var
    (or a `.env` file), validated against its declared type/bounds on load and on
    every later `app_config.<field> = ...` assignment."""

    model_config = SettingsConfigDict(
        env_prefix="DLF_",
        env_file=".env",
        extra="ignore",
        validate_assignment=True,
    )

    root_path: Path = _ROOT_PATH

    timeframe_shifter: dict[str, int] = {
        "structure": 0,
        "pattern": -1,
        "trigger": -2,
        "double": -4,
        "hat_trick": -6,
    }
    timeframes: tuple[str, ...] = (
        "1min",
        "5min",
        "15min",
        "1h",
        "4h",
        "1D",
        "1W",
    )
    hat_trick_index: int = 0
    trigger_dept: int = Field(default=16, gt=0)

    INFINITY_TIME_DELTA: timedelta = timedelta(days=10 * 365)
    EPSILON_TIME_DELTA: timedelta = timedelta(seconds=1)

    path_of_data: Path = Field(
        default=_ROOT_PATH.parent / "data",
        validation_alias="DLF_DATA_ROOT",
    )
    path_of_logs: Path = Field(
        default=_ROOT_PATH / "logs",
        validation_alias="DLF_LOGS_ROOT",
    )

    # infrastructure.disk_cache windowing (see app/infrastructure/ohlcv/README.md): default
    # calendar-window size for any data_frame_type without an entry in cache_window_freq_overrides,
    # as a pandas period freq alias ("M" calendar month, "D" calendar day, ...).
    # NOTE: These fields are now consumed only by the legacy disk_cache path. duckdb_cache uses
    # precise gap detection and no longer reads them. Flagged for eventual removal.
    default_cache_window_freq: str = "M"
    cache_window_freq_overrides: dict[str, str] = {
        "ohlcv": "D",
        "multi_timeframe_ohlcv": "D",
        "multi_timeframe_ohlcva": "D",
    }
    # infrastructure.datastore_engine.parquet_housekeeping compaction: target on-disk size (MB) when
    # merging adjacent per-window Parquet files into one larger file.
    parquet_target_chunk_size_mb: int = Field(default=100, gt=0)
    # Floor for default (no --time-range) OHLCV gap-fill backfill: how far back
    # presentation.market_data.fetch_ohlcv_cli walks before reporting "all up to date" and stopping.
    # Same single-timestamp format as one half of a time_range_str ("%y-%m-%d.%H-%M").
    ohlcv_oldest_fetch_date: str = "17-01-01.00-00"
    # Warn if a data_frame_type's cache-file generation rate, extrapolated to 24h, exceeds this many
    # bytes; re-evaluated at most once per cache_generation_monitor_interval_minutes per prefix.
    cache_generation_warn_bytes_per_day: int = Field(default=1_000_000_000, gt=0)
    cache_generation_monitor_interval_minutes: int = Field(default=30, gt=0)

    momentum_trend_strength_factor: float = Field(default=0.70, gt=0)  # CandleSize.Standard.value[0]

    load_data_to_meta_trader: bool = False

    atr_timeperiod: int = Field(default=14, gt=0)
    atr_safe_start_expand_multipliers: int = Field(default=1, gt=0)

    base_pattern_ttl: int = Field(default=4 * 4 * 4 * 4, gt=0)
    base_pattern_number_of_spinning_candles: int = Field(default=2, ge=0)
    base_pattern_candle_min_backward_coverage: float = Field(default=0.8, gt=0, le=1)
    # >1 means make sure the last candle is closed
    base_pattern_index_shift_after_last_candle_in_the_sequence: int = 1
    base_pattern_order_limit_price_margin_percentage: float = Field(default=0.05, ge=0, le=1)  # 5%
    base_pattern_risk_reward_rate: float = Field(default=5, gt=0)  # 500% = average rate of looses to achieve a win.

    ftc_price_range_percentage: float = Field(
        default=0.38, gt=0, le=1
    )  # the FTC will be in the last 38% of the movement.
    # 300% = we expect the profit to be 300% of trading fee to consider the trade profitable.
    trading_fee_safe_side_multiplier: float = Field(default=3, gt=0)
    # base patterns with size of less than n * atr (of base time frame) are not enough big to be back tested.
    base_pattern_small_to_trace_in_base_candles_atr_factor: float = Field(default=3, gt=0)
    initial_cash: float = Field(default=1000.0, gt=0)
    risk_per_order_percent: float = Field(default=0.01, gt=0, le=1)  # 1%
    capital_max_total_risk_percentage: float = Field(default=0.1, gt=0, le=1)  # 10%

    figure_width: int = Field(default=1500, gt=0)
    figure_height: int = Field(default=1000, gt=0)
    figure_font_size: int = Field(default=7, gt=0)

    pivot_number_of_active_hits: int = Field(default=2, gt=0)

    environment: Literal["development", "production"] = "development"

    @property
    def check_assertions(self) -> bool:
        return self.environment == "development"

    id: str = ""
    GLOBAL_CACHE: dict[str, object] = Field(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def structure_timeframes(self) -> tuple[str, ...]:
        return self.timeframes[2:]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pattern_timeframes(self) -> tuple[str, ...]:
        return self.timeframes[1:]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def trigger_timeframes(self) -> tuple[str, ...]:
        return self.timeframes[:-2]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def base_time_delta(self) -> timedelta:
        return pd.to_timedelta(self.timeframes[0])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def path_of_plots(self) -> Path:
        return self.path_of_data / "plots"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def path_of_models(self) -> Path:
        """Final trained model artifacts (.keras saves, TF CheckpointManager dirs under
        path_of_models/"artifacts"/<run_key>/) — see data/README.md."""
        return self.path_of_data / "models"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def path_of_scratch(self) -> Path:
        """Ephemeral, regenerable training-batch caches (npz/zip-pkl feeders) — see data/README.md."""
        return self.path_of_data / "scratch"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ohlcv_oldest_fetch_datetime(self) -> datetime:
        return datetime.strptime(self.ohlcv_oldest_fetch_date, "%y-%m-%d.%H-%M").replace(tzinfo=pytz.UTC)


app_config = Config()

config_as_json = app_config.model_dump_json()

config_digest = str.translate(
    base64.b64encode(hashlib.md5(config_as_json.encode("utf-8")).digest()).decode("ascii"),
    {
        ord("+"): "",
        ord("/"): "",
        ord("="): "",
    },
)

config_log_dir = app_config.path_of_logs / "config"
config_log_dir.mkdir(parents=True, exist_ok=True)

dump_filename = config_log_dir / f"Config.{config_digest}.json"

if not dump_filename.exists():
    dump_filename.write_text(config_as_json, encoding="utf-8")

app_config.id = config_digest
BASE_TIMEFRAME = app_config.timeframes[0]
