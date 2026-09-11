"""Export merged daily zones using the canonical project implementation."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xauusd.zones import load_zone_csv  # noqa: E402

FIELDNAMES = (
    "date",
    "zone_id",
    "lower",
    "upper",
    "priority",
    "source_rows",
    "source_count",
)


def export_merged_zones(source: Path, target: Path) -> int:
    """Load raw zones through the production merger and write a stable CSV export."""
    if source.resolve() == target.resolve():
        raise ValueError("Output path must be different from the raw input path")
    daily_zones = load_zone_csv(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for day, zones in daily_zones.items():
            for zone in zones:
                writer.writerow(
                    {
                        "date": day.strftime("%Y.%m.%d"),
                        "zone_id": zone.zone_id,
                        "lower": str(zone.low),
                        "upper": str(zone.high),
                        "priority": zone.priority.value,
                        "source_rows": ";".join(str(row) for row in zone.source_rows),
                        "source_count": len(zone.source_rows),
                    }
                )
                count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge a raw zone CSV with the exact rules and labels used by the project."
    )
    parser.add_argument("input", type=Path, help="Raw CSV containing zone rows")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV path (default: <input_stem>_merged.csv)",
    )
    args = parser.parse_args()

    source = args.input.resolve()
    target = (args.output or source.with_name(f"{source.stem}_merged.csv")).resolve()
    count = export_merged_zones(source, target)
    print(f"Exported {count} merged zones to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
