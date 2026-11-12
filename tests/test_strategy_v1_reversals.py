import pandas as pd

from domain.xau_usd.strategy_v1.reversals import _confirm_setups, _zone_exit_rows


def test_reversal_zone_exit_is_strictly_more_than_one_dollar_on_either_side() -> None:
    close_times = pd.date_range("2026-07-29 10:00", periods=4, freq="5min", tz="UTC")
    close_prices = pd.Series([2998.99, 2999.0, 3003.0, 3003.01], dtype="float64")
    zone_bounds = pd.DataFrame({"zone_id": ["zone-a"], "lower": [3000.0], "upper": [3002.0]})

    invalidations = _zone_exit_rows(
        close_times=close_times,
        close_prices=close_prices,
        zone_bounds=zone_bounds,
        buffer_usd=1.0,
    )

    assert invalidations["invalidation_time"].tolist() == [close_times[0], close_times[3]]


def test_reversal_exit_cancels_a_setup_before_same_bar_macd_confirmation() -> None:
    setup_time = pd.Timestamp("2026-07-29 10:01", tz="UTC")
    confirmation_time = pd.Timestamp("2026-07-29 10:05", tz="UTC")
    confirmations = pd.DataFrame(
        {
            "confirmation_time": [confirmation_time],
            "zone_id": ["zone-a"],
            "entry_reference": [3001.0],
        },
    )
    setups = pd.DataFrame(
        {
            "setup_time": [setup_time],
            "zone_id": ["zone-a"],
            "setup_id": ["setup-a"],
            "expires_at": [pd.Timestamp("2026-07-29 10:25", tz="UTC")],
        },
    )
    invalidations = pd.DataFrame(
        {
            "invalidation_time": [confirmation_time],
            "zone_id": ["zone-a"],
        },
    )

    candidates = _confirm_setups(confirmations, setups, invalidations)

    assert candidates.empty


def test_reversal_zone_exit_before_setup_does_not_cancel_new_setup() -> None:
    setup_time = pd.Timestamp("2026-07-29 10:05", tz="UTC")
    confirmations = pd.DataFrame(
        {
            "confirmation_time": [pd.Timestamp("2026-07-29 10:10", tz="UTC")],
            "zone_id": ["zone-a"],
            "entry_reference": [3001.0],
        },
    )
    setups = pd.DataFrame(
        {
            "setup_time": [setup_time],
            "zone_id": ["zone-a"],
            "setup_id": ["setup-a"],
            "expires_at": [pd.Timestamp("2026-07-29 10:25", tz="UTC")],
        },
    )
    invalidations = pd.DataFrame(
        {
            "invalidation_time": [pd.Timestamp("2026-07-29 10:00", tz="UTC")],
            "zone_id": ["zone-a"],
        },
    )

    candidates = _confirm_setups(confirmations, setups, invalidations)

    assert candidates["setup_id"].tolist() == ["setup-a"]
