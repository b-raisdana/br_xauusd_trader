import pandas as pd
import pytest
from pandera.errors import SchemaErrors

from application.xauusd_trading_strategy_1_vector.domain import schema as vector
from domain.schemas.common.base_dataframe import Timeseries
from domain.schemas.price_action.CausalExtremum import CausalExtremumResult


@pytest.mark.parametrize(
    "model",
    [
        vector.VectorizedTickInput,
        vector.VectorizedCandleInput,
        vector.PerCandleState,
        vector.PerTickBaseState,
        vector.StrategyResult,
        vector.StrategyResultWithCandles,
        vector.OrderManagementResult,
        vector.PositionTrackingResult,
        Timeseries,
        CausalExtremumResult,
    ],
)
def test_datetime_schema_builds_with_ns_utc(model):
    schema = model.to_schema()
    indexes = schema.index.indexes if hasattr(schema.index, "indexes") else [schema.index]
    fields = [field for field in [*indexes, *schema.columns.values()] if field is not None]
    datetimes = [field for field in fields if isinstance(field.dtype.type, pd.DatetimeTZDtype)]
    assert datetimes
    assert all(field.dtype.type == pd.DatetimeTZDtype(tz="UTC", unit="ns") for field in datetimes)


@pytest.mark.parametrize("model", [Timeseries, CausalExtremumResult])
@pytest.mark.parametrize(
    "dtype", ["datetime64[ns, UTC]", "datetime64[us, UTC]", "datetime64[ns]", "datetime64[ns, Europe/London]"]
)
def test_datetime_schema_enforces_ns_utc(model, dtype):
    frame = pd.DataFrame(
        {
            "true_peak_reach_minutes": [1.0],
            "true_valley_reach_minutes": [1.0],
            "extremum_sign": [1],
            "true_extremum_tf_minutes": [1.0],
        },
        index=pd.DatetimeIndex(["2026-09-18"], dtype=dtype, name="date"),
    )
    if dtype == "datetime64[ns, UTC]":
        pd.testing.assert_frame_equal(model.validate(frame, lazy=True), frame)
    else:
        with pytest.raises(SchemaErrors):
            model.validate(frame, lazy=True)
