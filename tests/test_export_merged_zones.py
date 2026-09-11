import csv
from pathlib import Path

import pytest

from scripts.export_merged_zones import export_merged_zones
from xauusd.zones import load_zone_csv


def test_export_matches_canonical_zone_merger_and_labels(tmp_path: Path) -> None:
    source = tmp_path / "raw.csv"
    target = tmp_path / "merged.csv"
    source.write_text(
        "date,lower,upper,priority,enabled,note\n"
        "2026.09.06,100,101,normal,true,a\n"
        "2026.09.06,102.49,103,high,true,b\n"
        "2026.09.06,104.50,105,normal,true,c\n"
        "2026.09.06,999,999,high,false,disabled\n"
        "2026.09.07,200,201,normal,true,d\n",
        encoding="utf-8",
    )

    exported_count = export_merged_zones(source, target)

    with target.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    canonical = [zone for zones in load_zone_csv(source).values() for zone in zones]

    assert exported_count == len(canonical) == 3
    assert [row["zone_id"] for row in rows] == [zone.zone_id for zone in canonical]
    assert rows == [
        {
            "date": "2026.09.06",
            "zone_id": "2026-09-06:R1",
            "lower": "100",
            "upper": "103",
            "priority": "high",
            "source_rows": "2;3",
            "source_count": "2",
        },
        {
            "date": "2026.09.06",
            "zone_id": "2026-09-06:R2",
            "lower": "104.50",
            "upper": "105",
            "priority": "normal",
            "source_rows": "4",
            "source_count": "1",
        },
        {
            "date": "2026.09.07",
            "zone_id": "2026-09-07:R1",
            "lower": "200",
            "upper": "201",
            "priority": "normal",
            "source_rows": "6",
            "source_count": "1",
        },
    ]


def test_export_refuses_to_overwrite_raw_input(tmp_path: Path) -> None:
    source = tmp_path / "raw.csv"
    source.write_text("date,lower,upper,priority,enabled\n", encoding="utf-8")

    with pytest.raises(ValueError, match="different"):
        export_merged_zones(source, source)
