import asyncio

import pandas as pd
import pytest

from application.xauusd_trading_strategy_1_vector.zone_cache import ZoneCache
from application.xauusd_trading_strategy_1_vector.zone_loader import load_zones_from_file, normalize_mt5_zone_rows


def rows(values):
    return pd.DataFrame(values, columns=["date", "lower", "upper", "priority", "enabled", "note"], dtype=str)


@pytest.mark.parametrize("enabled", ["false", " FALSE ", "0", "no", "off"])
def test_disabled_rows_are_skipped_before_date_and_price_validation(enabled):
    result = normalize_mt5_zone_rows(rows([["bad-date", "bad", "0", "low", enabled, "ignored"]]))
    assert result.empty
    assert result.index.get_level_values("date").dtype == pd.DatetimeTZDtype(unit="ns", tz="UTC")


@pytest.mark.parametrize("enabled", ["true", "1", "yes", "on", "", "unrecognized"])
def test_enabled_matches_mt5_negative_list(enabled):
    result = normalize_mt5_zone_rows(rows([["2026.09.24", "102", "100", " HIGH ", enabled, "retained"]]))
    assert result.lower.tolist() == [100.0]
    assert result.upper.tolist() == [102.0]
    assert result.priority.tolist() == ["high"]
    assert result.note.tolist() == ["retained"]


@pytest.mark.parametrize(
    "date,low,high,priority",
    [
        ("2026-09-24", "100", "102", "high"),
        ("2026.9.24", "100", "102", "high"),
        ("2026.02.30", "100", "102", "high"),
        ("2026.09.24", "100", "102", "low"),
        ("2026.09.24", "0", "102", "normal"),
        ("2026.09.24", "100", "-1", "normal"),
        ("2026.09.24", "bad", "102", "normal"),
    ],
)
def test_invalid_enabled_row_does_not_discard_valid_neighbor(date, low, high, priority):
    result = normalize_mt5_zone_rows(
        rows(
            [
                [date, low, high, priority, "true", "invalid"],
                ["2026.09.24", "100", "100", "normal", "true", "zero-width-valid"],
            ]
        )
    )
    assert result.note.tolist() == ["zero-width-valid"]


@pytest.mark.parametrize("header", [True, False])
def test_csv_loader_normalizes_then_assigns_ids_before_chain_merge(tmp_path, header):
    path = tmp_path / "ranges.csv"
    content = "date,lower,upper,priority,enabled,note\n" if header else ""
    content += "2026.09.24,104,106,normal,true,third\n"
    content += "2026.09.24,102,100,normal,true,first\n"
    content += "2026.09.24,103,102.5,high,true,second\n"
    content += "2026.09.24,107.5,108,normal,true,separate\n"
    path.write_text(content, encoding="utf-8")
    result = asyncio.run(load_zones_from_file(path))
    zones = ZoneCache(result).get_zones_for_day("2026-09-24")
    assert [(z.id, z.low, z.high, z.priority) for z in zones] == [
        ("R1&R2&R3", 100, 106, 1),
        ("R4", 107.5, 108, 0),
    ]
