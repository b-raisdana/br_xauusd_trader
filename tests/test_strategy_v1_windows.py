from datetime import UTC, datetime

import pytest

from domain.xau_usd.strategy_v1 import (
    confirmation_is_in_window,
    pullback_confirmation_expires_at,
    pullback_return_expires_at,
    resolve_reversal_confirmation,
    reversal_expires_at,
)
from domain.xau_usd.strategy_v1.config import StrategyV1Config


def test_reversal_and_pullback_confirmation_count_entry_candle_first_and_expire_exclusively():
    config = StrategyV1Config()
    expiry = reversal_expires_at(datetime(2026, 7, 29, 9, 43, tzinfo=UTC), config)

    assert expiry == datetime(2026, 7, 29, 10, 5, tzinfo=UTC)
    assert confirmation_is_in_window(datetime(2026, 7, 29, 10, 4, 59, tzinfo=UTC), expiry)
    assert not confirmation_is_in_window(expiry, expiry)
    assert pullback_confirmation_expires_at(datetime(2026, 7, 29, 10, 12, tzinfo=UTC), config) == datetime(
        2026,
        7,
        29,
        10,
        35,
        tzinfo=UTC,
    )


def test_pullback_return_allows_reentry_through_last_fifth_m5_candle():
    expiry = pullback_return_expires_at(datetime(2026, 7, 29, 10, tzinfo=UTC), StrategyV1Config())

    assert expiry == datetime(2026, 7, 29, 10, 30, tzinfo=UTC)
    assert confirmation_is_in_window(datetime(2026, 7, 29, 10, 29, 59, tzinfo=UTC), expiry)
    assert not confirmation_is_in_window(expiry, expiry)


def test_signal_windows_require_utc_timestamps():
    with pytest.raises(ValueError, match="UTC-aware"):
        reversal_expires_at(datetime(2026, 7, 29, 9, 43), StrategyV1Config())


def test_valid_exit_precedes_same_candle_macd_confirmation():
    expires_at = datetime(2026, 7, 29, 10, 5, tzinfo=UTC)

    assert (
        resolve_reversal_confirmation(
            exit_valid=True,
            macd_confirmed=True,
            confirmation_time=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
            expires_at=expires_at,
        )
        == "exit"
    )
    assert (
        resolve_reversal_confirmation(
            exit_valid=False,
            macd_confirmed=True,
            confirmation_time=expires_at,
            expires_at=expires_at,
        )
        == "expired"
    )
