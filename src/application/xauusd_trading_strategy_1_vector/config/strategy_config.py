from pathlib import Path

from pydantic_settings import SettingsConfigDict

from config.base import BaseContextConfig

_ROOT_PATH = Path(__file__).resolve().parent.parent.parent


class StrategyConfig(BaseContextConfig):
    """Runtime settings. Any field can be overridden via a `DLF_<FIELD_NAME>` env var
    (or a `.env` file), validated against its declared type/bounds on load and on
    every later `app_config.<field> = ...` assignment."""

    model_config = SettingsConfigDict(
        env_prefix="DLF_",
        env_file=".env",
        extra="ignore",
        validate_assignment=True,
    )
    max_time_basis_probe: int = 5
    breakout_buffer_usd: float = 1.0


strategy_config = StrategyConfig().log()
