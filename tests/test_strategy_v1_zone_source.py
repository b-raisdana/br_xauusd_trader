import pytest

from infrastructure.strategy_v1.zone_source import CsvZoneSource


def write_zones(path, rows: str) -> None:
    path.write_text("date,lower,upper,priority,enabled,note\n" + rows, encoding="utf-8")


def test_csv_zone_source_returns_enabled_zones_as_utc_neutral_inputs(tmp_path):
    path = tmp_path / "ranges.csv"
    write_zones(
        path,
        "2026.07.29,100,102,normal,true,first\n"
        "2026.07.29,101,103,high,true,overlap\n"
        "bad-date,bad,0,bad,false,disabled\n",
    )
    zones = CsvZoneSource().load_zones(path)
    assert zones.index.names == ["date", "zone_id"]
    assert str(zones.index.get_level_values("date").dtype) == "datetime64[ns, UTC]"
    assert zones.importance_class.tolist() == ["normal", "high"]
    assert zones.direction.tolist() == [0, 0]
    assert zones.lower.tolist() == [100.0, 101.0]


@pytest.mark.parametrize(
    "row",
    [
        "2026.07.29,102,100,normal,true,bad-bounds",
        "2026.07.29,100,102,invalid,true,bad-priority",
        "2026.07.29,0,102,normal,true,bad-low",
        "invalid-date,100,102,normal,true,bad-date",
    ],
)
def test_csv_zone_source_rejects_invalid_enabled_rows(tmp_path, row):
    path = tmp_path / "ranges.csv"
    write_zones(path, row + "\n")
    with pytest.raises(ValueError, match="invalid enabled rows"):
        CsvZoneSource().load_zones(path)


def test_csv_zone_source_rejects_unknown_enabled_value(tmp_path):
    path = tmp_path / "ranges.csv"
    write_zones(path, "2026.07.29,100,102,normal,unknown,bad-enabled\n")
    with pytest.raises(ValueError, match="invalid enabled value"):
        CsvZoneSource().load_zones(path)
