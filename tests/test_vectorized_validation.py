import numpy as np
import pandas as pd
import pytest
from pandera.errors import SchemaErrors
from vectorized_fixtures import candles_from_ticks

from application.xauusd_trading_strategy_1_vector.engagement import update_zone_engagement
from application.xauusd_trading_strategy_1_vector.trend import compute_references
from application.xauusd_trading_strategy_1_vector.vectorized_strategy import VectorizedXauUsdStrategy
from domain.schemas.xauusd_vector_strategy import EngagementResult, ReferenceResult, StrategyResult
from helper.importer import pt
from helper.pandera import pandera_validate


class EmptyZones:
    def get_zones_for_day(self, day):
        return []


def market_frame():
    times = pd.date_range("2026-09-18", periods=2, freq="15min", tz="UTC").as_unit("ns")
    index = pd.MultiIndex.from_arrays(
        [["test"] * 2, ["XAUUSD"] * 2, times, times.normalize()],
        names=["broker", "symbol", "datetime", "date"],
    )
    return pd.DataFrame({"bid": [100.0, 101.0], "ask": [100.2, 101.2]}, index=index)


@pytest.mark.parametrize("defect", ["missing_column", "wrong_dtype", "missing_index"])
def test_strategy_rejects_invalid_ticks(defect):
    ticks = market_frame()
    candles = candles_from_ticks(ticks)
    if defect == "missing_column":
        ticks = ticks.drop(columns="ask")
    elif defect == "wrong_dtype":
        ticks["bid"] = "invalid"
    else:
        ticks = ticks.droplevel("broker")
    with pytest.raises(SchemaErrors):
        VectorizedXauUsdStrategy(EmptyZones()).process_tick_data(ticks, candles)


@pytest.mark.parametrize("defect", ["missing_column", "wrong_dtype"])
def test_strategy_rejects_invalid_candles(defect):
    ticks = market_frame()
    candles = candles_from_ticks(ticks)
    if defect == "missing_column":
        candles = candles.drop(columns="high")
    else:
        candles["high"] = "invalid"
    with pytest.raises(SchemaErrors):
        VectorizedXauUsdStrategy(EmptyZones()).process_tick_data(ticks, candles)


@pytest.mark.parametrize("defect", ["missing_column", "wrong_index_precision"])
def test_strategy_output_rejects_broken_contract(defect):
    ticks = market_frame()
    result = VectorizedXauUsdStrategy(EmptyZones()).process_tick_data(ticks, candles_from_ticks(ticks))
    if defect == "missing_column":
        result = result.drop(columns="breakout_signals")
    else:
        result.index = result.index.set_levels(result.index.levels[2].as_unit("us"), level="datetime")
    with pytest.raises(SchemaErrors):
        StrategyResult.validate(result, lazy=True)


@pytest.mark.parametrize("operation", ["references", "engagement"])
@pytest.mark.parametrize("defect", ["missing_column", "wrong_dtype"])
def test_partial_state_operations_reject_invalid_inputs(operation, defect):
    if operation == "references":
        frame = pd.DataFrame({f"trend_{side}_{slot}": [1.0] for side in ("high", "low") for slot in range(3)})
        frame["trend_count"] = 1
        function, column = compute_references, "trend_high_0"
    else:
        frame = pd.DataFrame({"bid": [1.0], "bar_time": pd.date_range("2026-09-18", periods=1, tz="UTC")})
        function, column = lambda data: update_zone_engagement(data, []), "bid"
    frame = frame.drop(columns=column) if defect == "missing_column" else frame.assign(**{column: "invalid"})
    with pytest.raises(SchemaErrors):
        function(frame)


@pytest.mark.parametrize("inplace", [False, True])
def test_validation_preserves_explicit_mutation_policy(inplace):
    @pandera_validate(inplace=inplace)
    def mutate(frame: pt.DataFrame[EngagementResult]) -> pt.DataFrame[EngagementResult]:
        frame["buy_engaged"] = True
        return frame

    frame = pd.DataFrame(
        {
            "bid": [1.0],
            "bar_time": pd.date_range("2026-09-18", periods=1, tz="UTC").as_unit("ns"),
            "buy_engaged": False,
            "sell_engaged": False,
            "multi_zone_tick_gap": False,
        }
    )
    result = mutate(frame)
    assert result.buy_engaged.all()
    assert bool(frame.buy_engaged.iloc[0]) == inplace
    assert (result is frame) == inplace


@pytest.mark.parametrize("defect", ["missing_column", "wrong_dtype"])
def test_inplace_validation_still_rejects_broken_outputs(defect):
    @pandera_validate(inplace=True)
    def broken(frame: pt.DataFrame[ReferenceResult]) -> pt.DataFrame[ReferenceResult]:
        if defect == "missing_column":
            frame.drop(columns="reference_high", inplace=True)
        else:
            frame["reference_high"] = "invalid"
        return frame

    frame = pd.DataFrame({f"trend_{side}_{slot}": [1.0] for side in ("high", "low") for slot in range(3)})
    frame["trend_count"] = 1
    frame["reference_high"] = frame["reference_low"] = np.float64(1)
    with pytest.raises(SchemaErrors):
        broken(frame)
