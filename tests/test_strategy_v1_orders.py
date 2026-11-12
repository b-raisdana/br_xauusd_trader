from datetime import UTC, datetime

import pandas as pd
import pytest

from domain.xau_usd.strategy_v1 import limit_price_is_ready, prepare_order_prices, stop_loss_distance_usd
from domain.xau_usd.strategy_v1.config import StrategyV1Config


def _zones(lower: list[float], upper: list[float]) -> pd.DataFrame:
    index = pd.MultiIndex.from_arrays(
        [
            pd.to_datetime(["2026-07-29T00:00Z"] * len(lower)).astype("datetime64[ns, UTC]"),
            [f"zone-{position}" for position in range(len(lower))],
        ],
        names=["date", "zone_id"],
    )
    return pd.DataFrame(
        {
            "lower": lower,
            "upper": upper,
            "importance_class": ["normal"] * len(lower),
            "direction": [0] * len(lower),
            "note": [None] * len(lower),
        },
        index=index,
    )


def test_stop_loss_uses_dst_aware_london_new_york_overlap():
    config = StrategyV1Config()

    assert stop_loss_distance_usd(datetime(2026, 7, 29, 13, tzinfo=UTC), config) == 10.0
    assert stop_loss_distance_usd(datetime(2026, 7, 29, 10, tzinfo=UTC), config) == 6.0
    assert stop_loss_distance_usd(datetime(2026, 3, 9, 12, tzinfo=UTC), config) == 10.0


def test_buy_uses_nearest_target_zone_and_fixed_limit_reference():
    result = prepare_order_prices(
        _zones([3015.0, 3035.0], [3017.0, 3037.0]),
        datetime(2026, 7, 29, 13, tzinfo=UTC),
        "buy",
        3004.0,
        3000.0,
        3002.0,
        StrategyV1Config(),
    )

    assert result.accepted
    assert result.target_zone_id == "zone-0"
    assert result.stop_loss == 2994.0
    assert result.take_profit == 3015.0
    assert result.take_profit_distance_worst == pytest.approx(10.9)


def test_buy_rejects_passed_or_too_close_zone_target_without_fallback():
    zones = _zones([3015.0], [3017.0])
    passed = prepare_order_prices(
        zones,
        datetime(2026, 7, 29, 13, tzinfo=UTC),
        "buy",
        3015.0,
        3000.0,
        3002.0,
        StrategyV1Config(),
    )
    too_close = prepare_order_prices(
        zones,
        datetime(2026, 7, 29, 13, tzinfo=UTC),
        "buy",
        3005.0,
        3000.0,
        3002.0,
        StrategyV1Config(),
    )

    assert passed.reason == "target_already_passed"
    assert too_close.reason == "take_profit_distance_not_greater_than_stop"


def test_missing_opposite_target_uses_fixed_five_r_fallback_and_limit_waits_for_band():
    result = prepare_order_prices(
        _zones([3000.0], [3002.0]),
        datetime(2026, 7, 29, 13, tzinfo=UTC),
        "buy",
        3004.0,
        3000.0,
        3002.0,
        StrategyV1Config(),
    )

    assert result.accepted
    assert result.target_zone_id is None
    assert result.take_profit == 3054.0
    assert not limit_price_is_ready(
        direction="buy",
        bid=3004.5,
        ask=3004.6,
        entry_reference=3004.0,
        config=StrategyV1Config(),
    )
    assert limit_price_is_ready(
        direction="buy",
        bid=3004.0,
        ask=3004.1,
        entry_reference=3004.0,
        config=StrategyV1Config(),
    )
