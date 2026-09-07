from pathlib import Path

from scripts.generate_mql_zones import render


def test_generated_mql_zones_match_canonical_csv() -> None:
    root = Path(__file__).parents[1]
    expected = render(root / "data" / "ranges.csv")
    actual = (root / "src" / "mt5" / "generated" / "DailyZones.mqh").read_text(encoding="utf-8")
    assert actual == expected
    assert actual.count('if(broker_day == "') == 23
    assert actual.count(".priority=") == 444
