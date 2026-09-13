"""cTrader Open API connection settings loaded from the environment.

The values are read from ``$PROJECT_ROOT/.env`` so that no secrets are ever
committed (``.env`` is covered by ``.gitignore``). Real environment variables
always take precedence over the file, which makes the configuration testable.

The cTrader Open API is OAuth2 based and requires an application
``client_id``/``client_secret`` plus a ``refresh_token`` that is obtained once
through the interactive web grant. See ``docs/ctrader.md``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .models import CTraderError

DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


@dataclass(frozen=True, slots=True)
class CTraderSettings:
    """Non-secret connection configuration for the cTrader Open API client."""

    client_id: str
    client_secret: str
    refresh_token: Optional[str]
    access_token: Optional[str]
    account_login: Optional[int]
    symbol: str = "XAUUSD"
    host: str = "demo.ctraderapi.com"
    port: int = 5035

    @property
    def is_live(self) -> bool:
        return self.host != "demo.ctraderapi.com"

    @property
    def has_token(self) -> bool:
        return bool(self.access_token or self.refresh_token)

    @classmethod
    def from_env(cls, env_path: Optional[os.PathLike] = DEFAULT_ENV_PATH) -> "CTraderSettings":
        """Build settings from ``*.env`` plus real environment variables."""
        if env_path is not None:
            load_dotenv(env_path, override=False)

        client_id = os.getenv("CTRADER_CLIENT_ID", "").strip()
        client_secret = os.getenv("CTRADER_CLIENT_SECRET", "").strip()
        if not client_id:
            raise CTraderError(
                "CTRADER_CLIENT_ID is not set. Register an application at "
                "https://openapi.ctrader.com/apps to obtain it.",
                code="CONFIG",
            )
        if not client_secret:
            raise CTraderError(
                "CTRADER_CLIENT_SECRET is not set. It is shown once when you "
                "register your Open API application.",
                code="CONFIG",
            )

        refresh_token = os.getenv("CTRADER_REFRESH_TOKEN") or None
        access_token = os.getenv("CTRADER_ACCESS_TOKEN") or None
        if not refresh_token and not access_token:
            raise CTraderError(
                "Neither CTRADER_REFRESH_TOKEN nor CTRADER_ACCESS_TOKEN is set. "
                "Complete the one-time OAuth grant; see docs/ctrader.md.",
                code="CONFIG",
            )

        login_raw = os.getenv("CTRADER_ACCOUNT_LOGIN") or os.getenv(
            "ctrader_demo_account_login_number"
        )
        account_login: Optional[int] = None
        if login_raw:
            account_login = int(login_raw.strip())

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            access_token=access_token,
            account_login=account_login,
            symbol=os.getenv("CTRADER_SYMBOL", "XAUUSD").strip() or "XAUUSD",
            host=os.getenv("CTRADER_HOST", "demo.ctraderapi.com").strip() or "demo.ctraderapi.com",
            port=int(os.getenv("CTRADER_PORT", "5035")),
        )
