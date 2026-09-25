import pandas as pd
import pytest

from application.xauusd_trading_strategy_1_vector.backtest import _extract_signals
from domain.xau_usd.enums import XauExecutionStatus


@pytest.mark.parametrize("all_missing", [False, True])
def test_extract_signals_returns_boolean_masks_without_missing_values(all_missing):
    index = pd.date_range("2026-01-01", periods=5, freq="min", tz="UTC")
    result = pd.DataFrame(
        {
            "bid": [100.0] * 5,
            "position_id": pd.array([None, "p1", "p1", "p1", None], dtype="string"),
            "position_status": pd.array(
                [None] * 5
                if all_missing
                else [None, XauExecutionStatus.FILLED, XauExecutionStatus.FILLED, XauExecutionStatus.CLOSED, None],
                dtype="Int64",
            ),
        },
        index=index,
    )

    close, entries, exits = _extract_signals(result)

    assert entries.dtype == exits.dtype == bool
    assert entries.tolist() == ([False] * 5 if all_missing else [False, True, False, False, False])
    assert exits.tolist() == ([False] * 5 if all_missing else [False, False, False, True, False])
    pd.testing.assert_index_equal(entries.index, index)
    pd.testing.assert_index_equal(exits.index, index)
    pd.testing.assert_series_equal(close, result["bid"])
